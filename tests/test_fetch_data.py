from pathlib import Path
from typing import Self

import httpx
import pytest
from pydantic import ValidationError

from gaffer import fetch_data, storage

# Setup


class FakeClient:
    """This stands in for FPLClient, i.e. returns bootstrap/fixtures and per-id
    summaries, raising for any id in fail_ids. It records what it was asked for."""

    def __init__(
        self,
        bootstrap: dict,
        fixtures: list | None = None,
        fail_ids: frozenset[int] = frozenset(),
    ) -> None:
        self._bootstrap = bootstrap
        self._fixtures = fixtures if fixtures is not None else []
        self._fail_ids = fail_ids
        self.player_summary_calls: list[int] = []
        self.fixtures_called = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    # Mocks the method that gets bootstrap_static
    def bootstrap_static(self) -> dict:
        return self._bootstrap

    # Mocks the method that gets fixtures
    def fixtures(self, event: int | None = None) -> list:
        self.fixtures_called = True
        return self._fixtures

    # Mocks the method that gets player summaries
    def element_summary(self, element_id: int) -> dict:
        self.player_summary_calls.append(element_id)
        if element_id in self._fail_ids:
            raise httpx.HTTPError(f"boom {element_id}")
        return {"history": [], "history_past": [], "fixtures": []}


def _valid_bootstrap(ids: list[int]) -> dict:
    return {
        "elements": [{"id": i, "web_name": f"p{i}", "team": 1, "element_type": 3} for i in ids],
        "teams": [{"id": 1, "name": "Team"}],
        "events": [{"id": 1}],
        "element_types": [{"id": 3, "singular_name": "Midfielder"}],
    }


@pytest.fixture
def use_fake(monkeypatch: pytest.MonkeyPatch):
    """Return a helper that installs a given FakeClient as fetch_data.FPLClient."""

    def _install(fake: FakeClient) -> FakeClient:
        monkeypatch.setattr(fetch_data, "FPLClient", lambda: fake)
        return fake

    return _install


# Start of actual tests


def test_partial_failure_collects_rest_and_records_failed(raw_dir: Path, no_sleep, use_fake) -> None:
    # This line makes sure that fetch_data.fetch_live_fpl_data is using the fake client
    # with one failed fetch (id 2).
    fake = use_fake(FakeClient(_valid_bootstrap([1, 2, 3]), fail_ids=frozenset({2})))

    # Fetch data
    report = fetch_data.fetch_live_fpl_data(delay=0.0)

    # Check what we expect for a partial failure
    assert report.n_ok == 2
    assert report.failed_ids == [2]
    assert fake.player_summary_calls == [1, 2, 3]  # check that loop continued past the failure
    saved = storage.load_raw("element_summaries")
    assert isinstance(saved, dict)
    assert set(saved) == {"1", "3"}  # check that only successes persisted (str keys)


def test_save_raw_before_validate_and_aborts_on_drift(raw_dir: Path, no_sleep, use_fake) -> None:
    bad_bootstrap = {"teams": [], "events": [], "element_types": []}  # 'elements' missing
    fake = use_fake(FakeClient(bad_bootstrap))

    with pytest.raises(ValidationError):
        fetch_data.fetch_live_fpl_data(delay=0.0)

    # snapshot was written BEFORE validation blew up i.e. we can inspect what broke
    assert storage.load_raw("bootstrap") == bad_bootstrap

    # validation aborted before the loop and before fixtures i.e. no wasted API calls
    assert fake.player_summary_calls == []
    assert fake.fixtures_called is False


def test_envelope_drift_wrong_type_is_caught(raw_dir: Path, no_sleep, use_fake) -> None:
    # 'elements' is present but the wrong shape (dict, not a list of objects)
    bad_bootstrap = {"elements": {"nope": 1}, "teams": [], "events": [], "element_types": []}
    use_fake(FakeClient(bad_bootstrap))

    with pytest.raises(ValidationError):
        fetch_data.fetch_live_fpl_data(delay=0.0)


def test_report_is_accurate_on_clean_run(raw_dir: Path, no_sleep, use_fake) -> None:
    use_fake(FakeClient(_valid_bootstrap([10, 20, 30, 40])))

    report = fetch_data.fetch_live_fpl_data(delay=0.0)

    assert report.n_ok == 4
    assert report.failed_ids == []
    assert report.fetched_at.tzinfo is not None

    # check that report was persisted
    raw = storage.load_raw("fetch_report")
    assert isinstance(raw, dict)
    assert raw["n_ok"] == 4

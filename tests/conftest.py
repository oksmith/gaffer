from pathlib import Path

import pytest

from gaffer import storage


@pytest.fixture
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "raw"
    monkeypatch.setattr(storage, "RAW_DIR", d)
    return d


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make time.sleep instant everywhere the code under test uses it."""
    import gaffer.fetch_data
    import gaffer.fpl_client

    monkeypatch.setattr(gaffer.fpl_client.time, "sleep", lambda _s: None)
    monkeypatch.setattr(gaffer.fetch_data.time, "sleep", lambda _s: None)

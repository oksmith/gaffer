import json
from pathlib import Path

import pytest

from gaffer import storage
from gaffer.fpl_client import JSON


def test_round_trip_returns_equal_object(raw_dir: Path) -> None:
    obj: JSON = {"a": [1, 2, 3], "b": {"nested": True}, "c": None}
    storage.save_raw("thing", obj)
    assert storage.load_raw("thing") == obj


def test_load_missing_raises_file_not_found(raw_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        storage.load_raw("never_written")


def test_int_keys_come_back_as_strings(raw_dir: Path) -> None:
    # int keys are intentionally passed to mirror the FPL API
    storage.save_raw("summaries", {1: {"x": 1}, 2: {"x": 2}})
    loaded = storage.load_raw("summaries")
    assert isinstance(loaded, dict)
    assert set(loaded) == {"1", "2"}  # NOTE: not {1, 2}
    assert all(isinstance(k, str) for k in loaded)


def test_write_is_atomic_on_failure(raw_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If serialisation stops/breaks mid-write, the previous good file survives."""

    # First, save a good version of the received data
    storage.save_raw("bootstrap", {"version": "good"})

    # Mock out json.dumps to run into some error
    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("serialisation failed mid-write")

    monkeypatch.setattr(json, "dumps", boom)

    # Now attempt to save a bad version
    with pytest.raises(RuntimeError):
        storage.save_raw("bootstrap", {"version": "new-but-doomed"})

    # the real file is untouched — still the old, complete contents
    assert storage.load_raw("bootstrap") == {"version": "good"}

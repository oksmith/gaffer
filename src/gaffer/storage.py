import json
import os
from pathlib import Path

from gaffer.config import DATA_DIR
from gaffer.fpl_client import JSON, ParsedJSON

RAW_DIR = DATA_DIR / "raw"


def save_raw(name: str, obj: JSON) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}.json"

    # In order to avoid ending up with a corrupted file, make sure that the data
    # is fully written to disk before replacing it with the real path.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_raw(name: str) -> ParsedJSON:
    return json.loads((RAW_DIR / f"{name}.json").read_text(encoding="utf-8"))

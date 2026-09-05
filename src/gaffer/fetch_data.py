from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel

from gaffer import storage
from gaffer.config import REQUEST_DELAY
from gaffer.fpl_client import FPLClient, JSONArray, JSONObject

logger = logging.getLogger(__name__)


class BootstrapStaticData(BaseModel):
    """Top-level shape of bootstrap-static — envelope only.

    Validates that the keys we depend on exist and are lists of objects.
    Contents stay unmodelled (JSONArray). We'll validate the shape in a later
    stage.
    """

    elements: JSONArray
    teams: JSONArray
    events: JSONArray
    element_types: JSONArray


class FetchReport(BaseModel):
    """
    Metadata on what we were (or weren't) able to fetch from the FPL API.
    """

    fetched_at: datetime
    n_ok: int
    failed_ids: list[int]


def fetch_live_fpl_data(delay: float = REQUEST_DELAY) -> FetchReport:
    with FPLClient() as fpl:
        bootstrap_static = fpl.bootstrap_static()
        storage.save_raw("bootstrap", bootstrap_static)  # snapshot FIRST
        bootstrap_static_validated = BootstrapStaticData.model_validate(bootstrap_static)

        fixtures = fpl.fixtures()
        storage.save_raw("fixtures", fixtures)

        element_ids = [e["id"] for e in bootstrap_static_validated.elements]
        summaries, failed = _fetch_summaries(fpl, element_ids, delay)
        storage.save_raw("element_summaries", summaries)  # one blob, keyed by id

    report = FetchReport(fetched_at=datetime.now(UTC), n_ok=len(summaries), failed_ids=failed)
    storage.save_raw("fetch_report", report.model_dump(mode="json"))
    return report


def _fetch_summaries(fpl: FPLClient, element_ids: list[int], delay: float) -> tuple[dict[int, JSONObject], list[int]]:
    summaries: dict[int, JSONObject] = {}
    failed: list[int] = []
    for i, eid in enumerate(element_ids):
        try:
            summaries[eid] = fpl.element_summary(eid)
        except httpx.HTTPError as exc:
            logger.warning(f"element_summary {eid} unrecoverable: {exc}")
            failed.append(eid)
        if i < len(element_ids) - 1:
            time.sleep(delay)
    return summaries, failed

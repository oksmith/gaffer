from __future__ import annotations

import logging
import time
from types import TracebackType
from typing import Any, Self

import httpx

from gaffer.config import BACKOFF_BASE, BACKOFF_CAP, BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT, RETRY_AFTER_CAP, USER_AGENT

logger = logging.getLogger(__name__)

# We keep these types generic on purpose, as we do stricter validation later on (when transforming
# the raw data into DataFrames. This layer is simply for getting things from the FPL API and storing.
JSONObject = dict[str, Any]
JSONArray = list[dict[str, Any]]

# Note: type JSON includes dicts with int keys because player summaries pass those in to be saved,
# but later on json.dumps stringifies the keys on the way out.
type JSON = dict[str, Any] | dict[int, Any] | list[Any] | str | int | float | bool | None

# This type represents what json.loads can actually produce.
type ParsedJSON = dict[str, Any] | list[Any] | str | int | float | bool | None


class FPLClient:
    """Client for requesting data from the FPL API. Fetches and returns parsed JSON.

    Retry policy:
    - connection-level failures    -> exponential backoff, retried
    - HTTP 429 (rate limited)      -> honour Retry-After, retried
    - HTTP 5xx (transient server)  -> exponential backoff, retried
    - HTTP 4xx (client error)      -> raise an error
    """

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._max_retries = MAX_RETRIES
        self._client = client or httpx.Client(
            base_url=BASE_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,  # redirects should be followed and not raised
        )

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff in seconds for the given attempt."""
        return min(BACKOFF_BASE * 2 ** (attempt - 1), BACKOFF_CAP)

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        """Seconds to wait after getting rate limited."""
        raw = response.headers.get("Retry-After")
        if raw is not None:
            try:
                return min(float(raw), RETRY_AFTER_CAP)
            except ValueError:
                # Apparently Retry-After can also be an HTTP date... in this case let's
                # fall back to self._backoff(...)
                pass
        return self._backoff(attempt)

    def _get(self, path: str, params: JSONObject | None = None) -> Any:
        """Do a GET request on `path` and return JSON. Transient failures are retried."""
        for attempt in range(self._max_retries + 1):
            is_last = attempt == self._max_retries
            try:
                response = self._client.get(path, params=params)
                response.raise_for_status()

            # Any error at the connection layer e.g. never got back valid HTTP response at all.
            except httpx.TransportError as exc:
                if is_last:
                    raise
                wait = self._backoff(attempt + 1)
                logger.warning(f"GET {path} failed ({exc}); retrying in {wait:.1f}s")
                time.sleep(wait)

            # Got back HTTP response but it contains an HTTP status code indicating error
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if is_last or (status != 429 and status < 500):
                    raise
                wait = self._retry_after(exc.response, attempt + 1) if status == 429 else self._backoff(attempt + 1)
                logger.warning(f"GET {path} -> {status}; retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                return response.json()

    def bootstrap_static(self) -> JSONObject:
        """Contains a summary of players, teams, gameweeks, element types. Used to get element summaries."""
        return self._get("bootstrap-static/")

    def element_summary(self, element_id: int) -> JSONObject:
        """Per-player details containing rich information e.g. past/current history and upcoming fixtures."""
        return self._get(f"element-summary/{element_id}/")

    def fixtures(self, event: int | None = None) -> JSONArray:
        """All fixtures (or a single gameweek's when event is supplied)."""
        params = {"event": event} if event is not None else None
        return self._get("fixtures/", params=params)

    # Add some context-manager methods that allow us to use `with FPLClient()`.
    # Closes the connection(s) gracefully.

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

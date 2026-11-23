"""Bounded, auditable full-pagination transport for EVE private structure markets.

Single-page transient network failures are retried without dropping previously
fetched pages. Incomplete/changed pagination fails closed: never mix partial
private-structure orders with a successful public-market proof census.
No credentials, URLs containing credentials, or individual order contents in
diagnostic output. This module deliberately has no pandas dependency.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable

PAGE_ATTEMPTS = 5
PACE_SECONDS = 0.25
MAX_PAGES = 2000
RETRYABLE_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})


class StructurePageError(RuntimeError):
    def __init__(self, category: str, page: int, attempts: int,
                 *, http_status: int | None = None,
                 transient_retries: int = 0,
                 exception_class: str | None = None,
                 page_count_changed: bool = False):
        self.category = category
        self.page = page
        self.attempts = attempts
        self.transient_retries = transient_retries
        # Exception class only, never exception text (which may contain a URL or token).
        self.exception_class = exception_class[:70] if exception_class else None
        self.page_count_changed = page_count_changed
        # Safe status code only. Never log URLs, headers, response bodies
        # or bearer tokens from the underlying HTTP exception.
        self.http_status = http_status if isinstance(http_status, int) and 100 <= http_status <= 599 else None
        super().__init__(f"{category}:page={page}:attempts={attempts}")


def _transient(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return status in RETRYABLE_HTTP
    # requests.ConnectionError and requests.Timeout descend from OSError.
    return isinstance(exc, (OSError, TimeoutError))


def _fetch_page(fetch: Callable, url: str, params: dict, header: dict, *,
                attempts: int, sleep: Callable, jitter: Callable) -> tuple[dict, int]:
    retries = 0
    for n in range(1, attempts + 1):
        try:
            payload, _ = fetch(url, params=params, headers=header, timeout=(10, 55))
            if not isinstance(payload, dict):
                raise StructurePageError("MALFORMED_RESPONSE", params["page"], n)
            return payload, retries
        except StructurePageError:
            raise
        except Exception as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if not _transient(exc):
                raise StructurePageError("NONRETRYABLE_REQUEST", params["page"], n,
                                         http_status=status, transient_retries=retries,
                                         exception_class=type(exc).__name__) from None
            if n >= attempts:
                raise StructurePageError("TRANSIENT_EXHAUSTED", params["page"], n,
                                         http_status=status, transient_retries=retries,
                                         exception_class=type(exc).__name__) from None
            retries += 1
            sleep(min(12.0, 1.5 * (2 ** (n - 1))) + jitter() * 0.5)
    raise AssertionError("unreachable")


def all_structure_orders(api_key: str, *, structures: dict, worker: str,
                         fetch: Callable, sleep: Callable = time.sleep,
                         jitter: Callable = random.random,
                         page_attempts: int = PAGE_ATTEMPTS,
                         pace_seconds: float = PACE_SECONDS,
                         pagination_restart_limit: int = 1) -> tuple[list, dict]:
    """Return only complete lane books; restart a lane once if page count moves.

    The current ESI/Worker book can gain or lose a page during the 54-page
    C-J traversal. Retrying only the changed page could mix two snapshots,
    so discard ALL pages from that lane and start again at page 1.
    A second drift, invalid response, or transport failure still fails closed.
    """
    if not isinstance(page_attempts, int) or not 1 <= page_attempts <= 10:
        raise ValueError("BAD_RETRY_LIMIT")
    if (not isinstance(pagination_restart_limit, int)
            or not 0 <= pagination_restart_limit <= 2):
        raise ValueError("BAD_PAGINATION_RESTART_LIMIT")
    out, health = [], {}
    for lane, (location, profile) in structures.items():
        if not api_key:
            health[lane] = {"status": "FAILED", "reason": "missing_api_key"}
            continue
        headers = {"Authorization": "Bearer " + api_key}
        retries = 0
        restarts = 0
        current = 1
        pages_done = 0
        try:
            while True:
                # Never carry previous-attempt orders or a mutable page cursor
                # into a new pagination epoch.
                params = {"structure_id": location, "auth_profile": profile, "page": 1}
                current, pages_done = 1, 0
                try:
                    first, count = _fetch_page(
                        fetch, worker + "/api/structure-market", params, headers,
                        attempts=page_attempts, sleep=sleep, jitter=jitter)
                    retries += count
                    if (first.get("ok") is not True or
                            int(first.get("structure_id") or 0) != location or
                            int(first.get("page") or 0) != 1):
                        raise StructurePageError("FIRST_PAGE_NOT_VERIFIED", 1, 1)
                    pages = int(first.get("pages") or 0)
                    if (pages < 1 or pages > MAX_PAGES
                            or not isinstance(first.get("orders"), list)):
                        raise StructurePageError("FIRST_PAGE_METADATA_INVALID", 1, 1)
                    results = list(first["orders"])
                    pages_done = 1
                    for current in range(2, pages + 1):
                        if pace_seconds:
                            sleep(pace_seconds + jitter() * 0.1)
                        params["page"] = current
                        extra, count = _fetch_page(
                            fetch, worker + "/api/structure-market", params, headers,
                            attempts=page_attempts, sleep=sleep, jitter=jitter)
                        retries += count
                        # Malformed or unauthorized response is never repaired
                        # by re-fetching one page or restarting the full lane.
                        if (extra.get("ok") is not True or
                                int(extra.get("structure_id") or 0) != location or
                                int(extra.get("page") or 0) != current or
                                not isinstance(extra.get("orders"), list)):
                            raise StructurePageError("PAGINATION_DRIFT_OR_INVALID", current, 1)
                        remote_pages = int(extra.get("pages") or 0)
                        if remote_pages != pages:
                            raise StructurePageError(
                                "PAGINATION_DRIFT_OR_INVALID", current, 1,
                                page_count_changed=True)
                        results.extend(extra["orders"])
                        pages_done += 1
                    # No partial results are ever appended after a failed epoch.
                    out.extend(results)
                    health[lane] = {
                        "status": "COMPLETE", "orders": len(results), "pages": pages,
                        "location": location, "pages_fetched": pages_done,
                        "transient_retries": retries,
                        "pagination_restarts": restarts}
                    break
                except StructurePageError as exc:
                    if exc.page_count_changed and restarts < pagination_restart_limit:
                        retries += exc.transient_retries
                        restarts += 1
                        continue
                    raise
        except StructurePageError as exc:
            retries += exc.transient_retries
            health[lane] = {
                "status": "FAILED", "reason": exc.category, "failed_page": exc.page,
                "attempts_on_failed_page": exc.attempts,
                "http_status": exc.http_status,
                "pages_fetched": pages_done, "transient_retries": retries,
                "pagination_restarts": restarts,
                "request_exception_class": exc.exception_class,
                "page_count_changed": exc.page_count_changed}
        except Exception as exc:
            health[lane] = {
                "status": "FAILED", "reason": "UNEXPECTED_" + type(exc).__name__,
                "failed_page": current, "pages_fetched": pages_done,
                "transient_retries": retries, "pagination_restarts": restarts}
    return out, health

"""Safe read-only first-page diagnostic for BANESTAR and working controls.

Check 74L2-U with BOTH existing accessible SSO roles, and independently test
known-good C-J and O4T. Successful page-1 responses are never read. For errors,
only the finite HTTP status, bounded fixed Worker error name, and ESI upstream
HTTP status are extracted from at most 4096 bytes of JSON. No raw response
body, token, private order or EVE character metadata is logged or persisted.
"""
from __future__ import annotations

import json
import sys

import requests

from v4.candidate_station_probe import STATION_ID
from v4.deep_scan import WORKER, UA
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key

CHECKS = (
    ("banestar_cj", STATION_ID, "cj"),
    ("banestar_dc", STATION_ID, "dc"),
    ("control_cj", 1049588174021, "cj"),
    ("control_o4t", 1040804972352, "dc"),
)
SAFE_ERRORS = frozenset({
    "esi_error",
    "missing_scope_or_structure_access",
    "token_refresh_failed",
    "invalid_structure_id_or_page",
    "invalid_auth_profile",
})


def _safe_http(value):
    # Ignore potentially untrusted strings, dictionaries and tokens.
    return value if type(value) is int and 100 <= value <= 599 else None


def _classify(worker_status, esi_status):
    if worker_status == 200:
        return "FIRST_PAGE_OK"
    if worker_status == 401:
        return "BRIDGE_OR_SSO_AUTH_FAILURE"
    if worker_status == 403:
        return "ESI_STRUCTURE_ACCESS_FORBIDDEN"
    if worker_status == 502 and esi_status == 404:
        return "ESI_STRUCTURE_NOT_FOUND_OR_NOT_VISIBLE"
    if worker_status == 502 and esi_status == 401:
        return "ESI_UPSTREAM_AUTH_FAILURE"
    if worker_status == 502 and esi_status == 403:
        return "ESI_UPSTREAM_ACCESS_FORBIDDEN"
    if worker_status == 502 and esi_status in (420, 429):
        return "ESI_THROTTLED"
    if worker_status == 502 and esi_status in (500, 502, 503, 504):
        return "ESI_TEMPORARY_UPSTREAM_FAILURE"
    if worker_status == 502:
        return "WORKER_WRAPPED_ESI_ERROR_OR_BAD_RESPONSE"
    if worker_status in (420, 429, 500, 503, 504):
        return "WORKER_OR_NETWORK_TEMPORARY_FAILURE"
    return "OTHER_HTTP_RESULT"


def _inspect_response(response):
    worker_status = _safe_http(response.status_code)
    result = {"worker_http_status": worker_status}
    if worker_status not in (None, 200):
        # Only error JSON, never download the potentially large 200 order book.
        content_type = str(response.headers.get("Content-Type", ""))
        if "application/json" in content_type.lower():
            try:
                # One bounded chunk and no echoing of raw data / "detail".
                chunks = response.iter_content(chunk_size=4096)
                raw = next(iter(chunks), b"")
                obj = json.loads(raw.decode("utf-8"))
                if isinstance(obj, dict):
                    error = obj.get("error")
                    if isinstance(error, str) and error in SAFE_ERRORS:
                        result["worker_error"] = error
                    esi_status = _safe_http(obj.get("status"))
                    if esi_status is not None:
                        result["esi_upstream_http_status"] = esi_status
            except (ValueError, UnicodeError, StopIteration,
                    requests.RequestException, TypeError):
                result["error_metadata"] = "UNAVAILABLE"
    result["diagnosis"] = _classify(
        worker_status, result.get("esi_upstream_http_status"))
    return result


def probe(*, key=None, get=None):
    secret = get_bridge_key() if key is None else key
    report = {
        "status": "SAFE_STRUCTURE_DIAGNOSTIC",
        "station_id": STATION_ID,
        "production_sources_unchanged": True,
        "orders_saved": False,
        "secret_displayed": False,
        "enrolled": False,
        "checks": {},
    }
    if not valid_bridge_key(secret):
        report["status"] = "BRIDGE_CREDENTIAL_MISSING_OR_INVALID"
        return report
    fetch = get or requests.get
    for label, location, profile in CHECKS:
        try:
            with fetch(
                WORKER + "/api/structure-market",
                params={
                    "structure_id": location,
                    "auth_profile": profile,
                    "page": 1,
                },
                headers={
                    "Authorization": "Bearer " + secret,
                    "User-Agent": UA,
                },
                timeout=(10, 25),
                stream=True,
            ) as response:
                report["checks"][label] = _inspect_response(response)
        except requests.Timeout:
            report["checks"][label] = {"diagnosis": "REQUEST_TIMEOUT"}
        except requests.ConnectionError:
            report["checks"][label] = {"diagnosis": "NETWORK_CONNECT_FAILED"}
        except requests.RequestException:
            report["checks"][label] = {"diagnosis": "OTHER_REQUEST_ERROR"}
    return report


def main():
    try:
        result = probe()
    except Exception:
        result = {
            "status": "SAFE_DIAGNOSTIC_FAILED",
            "secret_displayed": False,
            "orders_saved": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "SAFE_STRUCTURE_DIAGNOSTIC" else 2


if __name__ == "__main__":
    sys.exit(main())

"""Minimal read-only Worker health probe for three authorized structure profiles.

Makes ONE page-1 request per approved structure. Does not download or
persist orders, secrets, 401 response bodies, or HTTP request headers.
Designed for troubleshooting NONRETRYABLE_REQUEST without a full scan.
"""
from __future__ import annotations

import json
import sys

import requests

from v4.deep_scan import STRUCTURES, WORKER, UA
from v4.local_bridge_auth import get_bridge_key, valid_bridge_key


def _safe_oauth_failure_reason(response) -> str:
    """Decode ONLY a bounded 401 error reply, NEVER a 200 market order body.

    Only hard-coded classes are returned; response details, tokens, user
    identifiers, request headers and even raw error snippets stay private.
    """
    try:
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=1024):
            raw.extend(chunk)
            if len(raw) > 4096:
                return "UNKNOWN_REFRESH_FAILURE"
        outer = json.loads(raw.decode("utf-8"))
        if not isinstance(outer, dict) or outer.get("error") != "token_refresh_failed":
            return "UNEXPECTED_401_JSON"
        detail = outer.get("detail")
        if isinstance(detail, (int, float)) and detail == 401:
            return "OAUTH_TOKEN_ENDPOINT_401"
        if not isinstance(detail, str):
            return "UNKNOWN_REFRESH_FAILURE"
        lower = detail.strip().lower()
        if "no refresh token" in lower or "no c-j refresh token" in lower or "no dc refresh token" in lower:
            return "WORKER_REFRESH_TOKEN_MISSING"
        if lower.startswith("token request exception"):
            return "OAUTH_ENDPOINT_REQUEST_EXCEPTION"
        if lower.startswith("{"):
            try:
                embedded = json.loads(detail)
                error_code = embedded.get("error") if isinstance(embedded, dict) else None
            except (ValueError, TypeError):
                error_code = None
            if error_code == "invalid_client":
                return "OAUTH_SHARED_CLIENT_CREDENTIALS_REJECTED"
            if error_code == "invalid_grant":
                return "OAUTH_SAVED_REFRESH_TOKEN_REJECTED"
            if error_code == "temporarily_unavailable":
                return "OAUTH_ENDPOINT_UNAVAILABLE"
        return "UNKNOWN_REFRESH_FAILURE"
    except (ValueError, UnicodeError, TypeError, AttributeError, OSError):
        return "UNKNOWN_REFRESH_FAILURE"


def probe(*, key=None, get=None) -> dict:
    key = get_bridge_key() if key is None else key
    if not valid_bridge_key(key):
        return {"status": "BRIDGE_CREDENTIAL_MISSING_OR_INVALID",
                "profiles": {}}
    fetch = get or requests.get
    rows = {}
    for name, (structure_id, profile) in STRUCTURES.items():
        # No credentials in URL, diagnostic JSON, or exception text.
        try:
            with fetch(
                WORKER + "/api/structure-market",
                params={"structure_id": structure_id, "auth_profile": profile,
                        "page": 1},
                headers={"Authorization": "Bearer " + key, "User-Agent": UA},
                timeout=(10, 25),
                stream=True,
            ) as response:
                code = response.status_code
                # The Worker has two distinct 401 paths:
                # text/plain Unauthorized = shared MAIL_API_KEY rejected;
                # application/json token_refresh_failed = authenticated
                # Worker could not refresh that EVE SSO character token.
                # Only on application/json 401 read a bounded error body,
                # classify with a fixed whitelist, and never echo its content.
                content_type = (response.headers.get("Content-Type", "")
                                .split(";", 1)[0].strip().lower())
                if code == 401:
                    origin = (
                        "WORKER_BRIDGE_KEY_REJECTED" if content_type == "text/plain" else
                        "EVE_SSO_REFRESH_FAILED" if content_type == "application/json" else
                        "UNKNOWN_401_SOURCE"
                    )
                else:
                    origin = None
                detail_class = (
                    _safe_oauth_failure_reason(response)
                    if code == 401 and origin == "EVE_SSO_REFRESH_FAILED"
                    else None
                )
                rows[name] = {"http_status": code,
                              "category": (
                                  "OK" if code == 200 else
                                  "AUTH_OR_ACCESS_DENIED" if code in (401, 403) else
                                  "ROUTE_NOT_FOUND" if code in (404, 405) else
                                  "RATE_LIMITED" if code == 429 else
                                  "UPSTREAM_OR_WORKER_FAILURE" if 500 <= code <= 599 else
                                  "OTHER_HTTP_ERROR"),
                              "auth_failure_layer": origin,
                              "refresh_failure_reason": detail_class}
        except requests.Timeout:
            rows[name] = {"category": "TIMEOUT"}
        except requests.ConnectionError:
            rows[name] = {"category": "CONNECTION_FAILURE"}
        except requests.RequestException:
            rows[name] = {"category": "OTHER_REQUEST_ERROR"}
    return {"status": "PROBED_THREE_FIRST_PAGES_NO_ORDERS_STORED",
            "profiles": rows,
            "secret_displayed": False,
            "orders_saved": False}


def main() -> int:
    try:
        result = probe()
    except Exception:
        # Unexpected local Credential Manager errors must never print a
        # traceback containing a credential, URL or untrusted response.
        result = {"status": "LOCAL_PROBE_ERROR", "secret_displayed": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PROBED_THREE_FIRST_PAGES_NO_ORDERS_STORED" else 2


if __name__ == "__main__":
    sys.exit(main())

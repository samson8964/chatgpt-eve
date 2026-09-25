#!/usr/bin/env python3
"""
Authorize one EVE character with EVE SSO (PKCE) and export skill data locally.

Usage:
    python eve_skill_auth.py --client-id YOUR_CLIENT_ID --character MikeChong

EVE developer app callback URL must be exactly:
    http://127.0.0.1:8765/callback

Requested scopes:
    esi-skills.read_skills.v1
    esi-skills.read_skillqueue.v1

Outputs are written under private/ and are intentionally gitignored.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

AUTHORIZE_URL = "https://login.eveonline.com/v2/oauth/authorize"
TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net"
CALLBACK = "http://127.0.0.1:8765/callback"
SCOPES = ["esi-skills.read_skills.v1", "esi-skills.read_skillqueue.v1"]
OUT_DIR = Path("private")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise RuntimeError("Unexpected access token format")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode()))


def build_pkce():
    verifier = b64url(secrets.token_bytes(48))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def get_type_name(type_id: int, headers: dict, session: requests.Session, cache: dict) -> str:
    key = str(type_id)
    if key in cache:
        return cache[key]
    r = session.get(f"{ESI_BASE}/universe/types/{type_id}", headers=headers, timeout=30)
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", "2")))
        r = session.get(f"{ESI_BASE}/universe/types/{type_id}", headers=headers, timeout=30)
    r.raise_for_status()
    name = r.json().get("name", key)
    cache[key] = name
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--character", default="MikeChong")
    args = ap.parse_args()

    verifier, challenge = build_pkce()
    state = secrets.token_urlsafe(24)
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            result["code"] = qs.get("code", [None])[0]
            result["state"] = qs.get("state", [None])[0]
            result["error"] = qs.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h2>EVE authorization received.</h2><p>You can close this browser tab and return to the terminal.</p>".encode()
            )

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("127.0.0.1", 8765), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    params = {
        "response_type": "code",
        "client_id": args.client_id,
        "redirect_uri": CALLBACK,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    print("\nOpening official EVE SSO in your browser...")
    print("Select the character:", args.character)
    print("If the browser does not open, copy this URL:\n", url, "\n")
    webbrowser.open(url)

    deadline = time.time() + 300
    while "code" not in result and "error" not in result and time.time() < deadline:
        time.sleep(0.25)
    server.shutdown()

    if result.get("error"):
        raise RuntimeError(f"Authorization failed: {result['error']}")
    if not result.get("code"):
        raise RuntimeError("Timed out waiting for EVE SSO callback")
    if result.get("state") != state:
        raise RuntimeError("OAuth state mismatch")

    token_resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": result["code"],
            "client_id": args.client_id,
            "code_verifier": verifier,
            "redirect_uri": CALLBACK,
        },
        timeout=30,
    )
    token_resp.raise_for_status()
    token = token_resp.json()

    claims = decode_jwt_payload(token["access_token"])
    char_name = claims.get("name", "")
    sub = claims.get("sub", "")
    try:
        character_id = int(sub.rsplit(":", 1)[1])
    except Exception as e:
        raise RuntimeError(f"Could not read character id from token: {sub}") from e

    if char_name.casefold() != args.character.casefold():
        raise RuntimeError(
            f"Authorized {char_name!r}, but expected {args.character!r}. "
            "Run again and select the correct character."
        )

    OUT_DIR.mkdir(exist_ok=True)
    token_file = OUT_DIR / "eve_mikechong_token.json"
    token_file.write_text(
        json.dumps(
            {
                "character_id": character_id,
                "character_name": char_name,
                "client_id": args.client_id,
                "refresh_token": token.get("refresh_token"),
                "scopes": claims.get("scp", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    compat = (date.today() - timedelta(days=1)).isoformat()
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Accept": "application/json",
        "X-Compatibility-Date": compat,
        "User-Agent": "samson8964-chatgpt-eve-skill-audit/1.0",
    }
    s = requests.Session()

    skills_r = s.get(f"{ESI_BASE}/characters/{character_id}/skills", headers=headers, timeout=30)
    skills_r.raise_for_status()
    queue_r = s.get(f"{ESI_BASE}/characters/{character_id}/skillqueue", headers=headers, timeout=30)
    queue_r.raise_for_status()

    skills = skills_r.json()
    queue = queue_r.json()

    name_cache = {}
    unique_ids = sorted(
        {int(x["skill_id"]) for x in skills.get("skills", [])}
        | {int(x["skill_id"]) for x in queue}
    )
    print(f"Resolving {len(unique_ids)} skill names...")
    for i, skill_id in enumerate(unique_ids, 1):
        get_type_name(skill_id, headers, s, name_cache)
        if i % 50 == 0:
            print(f"  {i}/{len(unique_ids)}")
        time.sleep(0.03)

    for row in skills.get("skills", []):
        row["skill_name"] = name_cache.get(str(row["skill_id"]), str(row["skill_id"]))
    for row in queue:
        row["skill_name"] = name_cache.get(str(row["skill_id"]), str(row["skill_id"]))

    skill_file = OUT_DIR / "mikechong_skills.json"
    queue_file = OUT_DIR / "mikechong_skillqueue.json"
    skill_file.write_text(json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8")
    queue_file.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nAuthorization succeeded:", char_name, character_id)
    print("Total SP:", skills.get("total_sp"))
    print("Unallocated SP:", skills.get("unallocated_sp", 0))
    print("Saved:")
    print(" ", skill_file)
    print(" ", queue_file)
    print("Private refresh token saved locally in:", token_file)
    print("Do NOT upload or paste the token file. Upload only the two skill JSON files if you want them analyzed.")


if __name__ == "__main__":
    main()

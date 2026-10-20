"""Single authoritative V4 player-structure registry with staged 74L2-U enrollment.

Default approved structures are unchanged. BANESTAR can be activated ONLY by
an explicit local, exact-match sentinel file after first-page and full-book
access have passed. All independent scheduled Python processes read the same
file at startup; no new SSO profile or Cloudflare deployment is needed.
"""
from __future__ import annotations

from pathlib import Path

BASE_LANES = (
    ("four_h", "4-H", 1053970513596, "main"),
    ("cj", "C-J", 1049588174021, "cj"),
    ("o4t", "O4T", 1040804972352, "dc"),
)
BANESTAR_LANE = ("banestar", "74L2-U", 1050474463169, "dc")
ENABLE_FILE = Path.home() / "EVE-V4-Data" / "config" / "banestar-market.enabled"
ENABLE_CONTENT = "APPROVED_1050474463169"


def banestar_enabled() -> bool:
    try:
        return (ENABLE_FILE.is_file()
                and ENABLE_FILE.read_text(encoding="utf-8").strip() == ENABLE_CONTENT)
    except (OSError, UnicodeError):
        return False


ACTIVE_LANES = BASE_LANES + ((BANESTAR_LANE,) if banestar_enabled() else ())
STRUCTURES = {lane: (location, profile)
              for lane, _, location, profile in ACTIVE_LANES}
STATIONS = {label: location
            for _, label, location, _ in ACTIVE_LANES}
LANE_TO_LABEL = {lane: label
                 for lane, label, _, _ in ACTIVE_LANES}
LABEL_TO_LANE = {label: lane
                 for lane, label, _, _ in ACTIVE_LANES}

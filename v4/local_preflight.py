"""Read-only Windows V4 migration preflight; uses only Python's stdlib.

Does not write files, make network requests, or inspect/print API secrets.
The output is only machine capabilities and dependency availability.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sqlite3
import sys
from pathlib import Path


PACKAGES = ("pandas", "numpy", "requests")


def assess(version: tuple[int, ...], system: str, free_bytes: int, packages: dict[str, bool]) -> dict:
    """Pure readiness summary: disk target remains advisory until real scan sizing."""
    missing = sorted(name for name, present in packages.items() if not present)
    return {
        "python_311_or_newer": version >= (3, 11),
        "windows": system.lower() == "windows",
        "dependencies_present": not missing,
        "missing_dependencies": missing,
        "disk_free_gib": round(free_bytes / (1024 ** 3), 2),
        "disk_capacity_not_yet_sized": True,
        "safe_to_activate_mail": False,
        "ready_to_attempt_shadow": version >= (3, 11) and not missing,
    }


def inspect(base: Path) -> dict:
    """Read-only inspection; path may not exist yet, so walk to existing ancestor."""
    probe = base.resolve()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    storage = shutil.disk_usage(probe)
    packages = {name: importlib.util.find_spec(name) is not None for name in PACKAGES}
    result = assess(sys.version_info[:3], platform.system(), storage.free, packages)
    result.update({
        "mode": "READ_ONLY_PREFLIGHT",
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "git_found": shutil.which("git") is not None,
        "codex_found": shutil.which("codex") is not None,
        "data_root_candidate": str(base),
        "storage_device_checked": str(probe.anchor),
        "api_tokens_inspected": False,
        "network_touched": False,
        "files_written": False,
        "production_changed": False,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="EVE V4 safe local readiness check")
    parser.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data",
                        help="Planned data root; does not create it")
    args = parser.parse_args()
    print(json.dumps(inspect(args.data_root), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

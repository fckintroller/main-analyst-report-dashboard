"""Compatibility wrapper for Kiwoom preflight/session Discord alerts."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEALTH_PATH = PROJECT_ROOT / "data" / "raw" / "kiwoom" / "preflight" / "latest_kiwoom_preflight.json"
NOTIFY = PROJECT_ROOT / "scripts" / "05_notify" / "notify_kiwoom_prelight.py"


def read_health() -> dict[str, Any]:
    if not HEALTH_PATH.exists():
        return {"status": "missing", "connected": False, "message": "preflight health file not found"}
    try:
        return json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "connected": False, "message": f"health parse failed: {exc!r}"}


def call_notify(mode: str, detail: str = "", dry_run: bool = False, force: bool = False) -> int:
    cmd = [sys.executable, str(NOTIFY), "--mode", mode, "--detail", detail, "--cooldown-minutes", "0" if force else "30"]
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--always", action="store_true")
    args = parser.parse_args()

    if args.preflight:
        return call_notify("prelight", "Scheduled weekday 06:50 Kiwoom API login reminder", dry_run=args.dry_run, force=True)
    if args.health:
        health = read_health()
        connected = bool(health.get("connected")) or health.get("status") == "connected"
        if connected and not args.always:
            print("Kiwoom health ok; no Discord alert needed")
            return 0
        detail = json.dumps({"checked_at": datetime.now().isoformat(timespec="seconds"), **health}, ensure_ascii=False, indent=2)
        return call_notify("disconnected", detail, dry_run=args.dry_run, force=args.always)
    parser.error("choose --preflight or --health")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
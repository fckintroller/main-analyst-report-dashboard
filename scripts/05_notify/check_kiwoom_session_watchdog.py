"""Kiwoom session watchdog.

Checks recent Kiwoom collector logs/output during market hours. If disconnected or
failed, sends a Discord alert and starts the Kiwoom OpenAPI login preflight
program. This cannot alert while the PC is physically powered off; the paired
logon/startup task sends a recovery alert when Windows comes back.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
STATE_DIR = PROJECT_ROOT / "data" / "raw" / "kiwoom" / "session_watchdog"
STATE_FILE = STATE_DIR / "watchdog_state.json"
LOGIN_BAT = PROJECT_ROOT / "run_kiwoom_openapi_login.bat"
NOTIFY = PROJECT_ROOT / "scripts" / "05_notify" / "notify_kiwoom_prelight.py"

FAIL_PATTERNS = [
    "Kiwoom not connected",
    "kiwoom_not_connected",
    "not_connected",
    "FAILED rc=2",
    "CONNECT_TEST: failed",
    "opening login dialog",
]
OK_PATTERNS = [
    "CONNECT_TEST: ok",
    "connected\": true",
    "Kiwoom intraday market flow OK",
    "Kiwoom candidate stock flow OK",
]


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def in_watch_window() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return time(6, 45) <= now.time() <= time(15, 40)


def latest_logs(limit: int = 12) -> list[Path]:
    pats = ["kiwoom_intraday_market_flow_*.log", "kiwoom_candidate_stock_flow_*.log", "kiwoom_openapi_login_*.log"]
    files: list[Path] = []
    for pat in pats:
        files.extend(LOG_DIR.glob(pat))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def classify_recent() -> tuple[str, str]:
    files = latest_logs()
    if not files:
        return "unknown", "no recent Kiwoom logs"
    snippets = []
    saw_fail = False
    saw_ok = False
    for path in files[:8]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[-4000:]
        except Exception as exc:
            snippets.append(f"{path.name}: read error {exc}")
            continue
        tail = " | ".join([line.strip() for line in text.splitlines()[-4:] if line.strip()])
        snippets.append(f"{path.name}: {tail[:450]}")
        if any(p in text for p in FAIL_PATTERNS):
            saw_fail = True
        if any(p in text for p in OK_PATTERNS):
            saw_ok = True
    if saw_fail:
        return "disconnected", "\n".join(snippets[:5])
    if saw_ok:
        return "ok", "\n".join(snippets[:5])
    return "unknown", "\n".join(snippets[:5])


def start_login_program(dry_run: bool = False) -> None:
    if dry_run:
        print(f"DRY_RUN_START={LOGIN_BAT}")
        return
    subprocess.Popen([str(LOGIN_BAT), "--from-watchdog"], cwd=str(PROJECT_ROOT), creationflags=subprocess.CREATE_NEW_CONSOLE)
    print(f"started login program: {LOGIN_BAT}")


def notify(mode: str, detail: str, dry_run: bool = False) -> int:
    cmd = [sys.executable, str(NOTIFY), "--mode", mode, "--detail", detail, "--cooldown-minutes", "30"]
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiwoom session watchdog")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="ignore market-hour window")
    args = parser.parse_args(argv)

    if not args.force and not in_watch_window():
        print("[skip] outside Kiwoom watchdog window")
        return 0
    status, detail = classify_recent()
    state = load_state()
    prev = state.get("last_status")
    state["last_status"] = status
    state["last_checked_at"] = datetime.now().isoformat(timespec="seconds")
    state["detail"] = detail[:2000]
    save_state(state)
    print(f"KIWOOM_WATCHDOG status={status} prev={prev}")
    if detail:
        print(detail)
    if status == "disconnected":
        rc = notify("disconnected", detail, dry_run=args.dry_run)
        start_login_program(dry_run=args.dry_run)
        return rc
    if status == "ok" and prev == "disconnected":
        return notify("recovered", detail, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

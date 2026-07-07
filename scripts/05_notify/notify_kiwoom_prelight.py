"""Discord notifications for Kiwoom login/session automation.

Modes:
- prelight: weekday 06:50 login reminder and keeper launch notice
- startup: Windows logon/startup recovery notice
- disconnected: Kiwoom session/collector failure notice
- recovered: session recovered notice
- test: smoke-test payload

Secrets stay in C:\claude cowork\05_skills\discord-webhook\config.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(r"C:\claude cowork\05_skills\discord-webhook\config.json")
STATE_DIR = PROJECT_ROOT / "data" / "raw" / "kiwoom" / "session_watchdog"
STATE_FILE = STATE_DIR / "alert_state.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"[error] Discord config missing: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def post_webhook(url: str, payload: dict[str, Any], dry_run: bool = False) -> bool:
    if dry_run:
        print("DRY_RUN_DISCORD_PAYLOAD=" + json.dumps(payload, ensure_ascii=False, indent=2))
        return True
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                print(f"Discord sent: {resp.status_code}")
                return True
            if resp.status_code == 429:
                wait = float(resp.json().get("retry_after", 2))
                print(f"[rate-limit] wait {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[error] HTTP {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            return False
        except requests.RequestException as exc:
            print(f"[retry {attempt + 1}] {exc}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return False


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


def should_send(mode: str, cooldown_minutes: int, force: bool) -> bool:
    if force or cooldown_minutes <= 0:
        return True
    state = load_state()
    last = state.get(f"last_{mode}")
    if not last:
        return True
    try:
        delta = datetime.now() - datetime.fromisoformat(last)
        return delta.total_seconds() >= cooldown_minutes * 60
    except Exception:
        return True


def mark_sent(mode: str) -> None:
    state = load_state()
    state[f"last_{mode}"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)


def build_embed(mode: str, detail: str = "") -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    titles = {
        "prelight": "Kiwoom API login check - 06:50",
        "startup": "Windows session started - Kiwoom recovery",
        "disconnected": "Kiwoom API disconnected or collector failed",
        "recovered": "Kiwoom API session recovered",
        "test": "Kiwoom API notification test",
    }
    descriptions = {
        "prelight": (
            "Weekday 06:50 login reminder. The OpenAPI keeper will start after this alert.\n\n"
            "Please confirm the PC is on, Windows is logged in, and complete the Kiwoom login dialog if it appears. "
            "Market/candidate flow collection starts from 09:05 and feeds the Decision panel."
        ),
        "startup": "Windows logon/startup was detected. The Kiwoom keeper/login recovery flow is being launched.",
        "disconnected": "A Kiwoom collector or session check reported disconnected/failure. The guarded login flow is being launched.",
        "recovered": "Kiwoom session or collector health appears recovered.",
        "test": "Smoke-test message for Discord webhook, batch files, and scheduled-task wiring.",
    }
    colors = {
        "prelight": 0x5865F2,
        "startup": 0xFEE75C,
        "disconnected": 0xED4245,
        "recovered": 0x57F287,
        "test": 0x00B4D8,
    }
    desc = descriptions.get(mode, descriptions["test"])
    if detail:
        desc += f"\n\n```\n{detail[:1200]}\n```"
    return {
        "title": titles.get(mode, titles["test"]),
        "description": desc,
        "color": colors.get(mode, colors["test"]),
        "fields": [
            {"name": "Time", "value": now, "inline": True},
            {"name": "Trading", "value": "Live orders disabled; data collection/decision support only", "inline": False},
            {"name": "Automation", "value": "06:50 prelight + market-hours watchdog + guarded login", "inline": False},
        ],
        "footer": {"text": "Anal_reports Kiwoom Session Watchdog"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send Kiwoom login/session Discord notification")
    parser.add_argument("--mode", choices=["prelight", "startup", "disconnected", "recovered", "test"], default="test")
    parser.add_argument("--detail", default="")
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not should_send(args.mode, args.cooldown_minutes, args.force):
        print(f"[skip] cooldown active for mode={args.mode}")
        return 0
    cfg = load_config()
    url = cfg.get("collect_webhook_url") or cfg.get("report_webhook_url") or cfg.get("webhook_url")
    if not url:
        raise SystemExit("[error] Discord webhook_url missing")
    payload = {"username": cfg.get("username", "QuantBot"), "embeds": [build_embed(args.mode, args.detail)]}
    ok = post_webhook(url, payload, dry_run=args.dry_run)
    if ok:
        mark_sent(args.mode)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
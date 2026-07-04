"""
관세청+ECOS 수출입 신규 데이터 수집 완료 시 Discord 알림
run_trade_import_export.bat에서 신규 월 감지 후 호출
  python notify_trade_import_export.py --prev-month 202605 --new-month 202606
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH    = PROJECT_ROOT / "data" / "raw" / "trade_import_export" / "latest_trade_import_export_analysis.json"
SKILL_DIR    = Path(r"C:\claude cowork\05_skills\discord-webhook")
CONFIG_PATH  = SKILL_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"[error] config.json 없음: {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def post_webhook(url: str, payload: dict, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code in (200, 204):
                return True
            if r.status_code == 429:
                wait = r.json().get("retry_after", 2)
                time.sleep(wait)
                continue
            print(f"[error] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
        except requests.RequestException as e:
            time.sleep(2 ** attempt)
    return False


def fmt_pct(v) -> str:
    if v is None: return "--"
    n = float(v)
    return f"{'+' if n >= 0 else ''}{n:.1f}%"


def fmt_usd(v) -> str:
    if v is None: return "--"
    n = float(v)
    if abs(n) >= 1e9: return f"${n/1e9:.1f}B"
    if abs(n) >= 1e6: return f"${n/1e6:.0f}M"
    return f"${n:,.0f}"


def pct_arrow(v) -> str:
    if v is None: return ""
    return "🟢" if float(v) >= 0 else "🔴"


def build_embed(data: dict, prev_month: str, new_month: str) -> dict:
    latest  = data.get("ecos", {}).get("latest") or data.get("ecos_latest") or {}
    verdict = data.get("verdict", {})
    customs = data.get("customs", {})
    stance  = str(verdict.get("stance", "UNKNOWN")).upper()

    stance_emoji = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "🟡"}.get(stance, "⚪")
    stance_label = {"POSITIVE": "긍정", "NEGATIVE": "부정", "NEUTRAL": "중립"}.get(stance, stance)

    def fmt_month(m: str) -> str:
        s = str(m or "")
        return f"{s[:4]}-{s[4:6]}" if len(s) == 6 else s

    prev_fmt = fmt_month(prev_month)
    new_fmt  = fmt_month(new_month)

    # 핵심 지표
    ex_yoy  = latest.get("exports_usd_yoy_pct")
    im_yoy  = latest.get("imports_usd_yoy_pct")
    bal     = latest.get("trade_balance_usd")
    ex_mom  = latest.get("exports_usd_mom_pct")
    vol_yoy = latest.get("export_volume_index_yoy_pct")
    ex_usd  = latest.get("exports_usd")

    fields = [
        {"name": "📦 수출금액",    "value": f"{fmt_usd(ex_usd)}\nYoY {pct_arrow(ex_yoy)} **{fmt_pct(ex_yoy)}**",  "inline": True},
        {"name": "⚖️ 무역수지",   "value": f"**{fmt_usd(bal)}**",                                                   "inline": True},
        {"name": "📈 수입 YoY",   "value": f"{pct_arrow(im_yoy)} {fmt_pct(im_yoy)}",                               "inline": True},
        {"name": "📉 수출 MoM",   "value": f"{pct_arrow(ex_mom)} {fmt_pct(ex_mom)}",                               "inline": True},
        {"name": "🚢 수출물량 YoY","value": f"{pct_arrow(vol_yoy)} {fmt_pct(vol_yoy)}",                            "inline": True},
    ]

    # 관세청 품목 요약 (상위 3개)
    items = (customs.get("summary") or [])[:3]
    if items:
        item_lines = []
        for it in items:
            sig = it.get("signal", "")
            sig_e = "🟢" if "개선" in sig or "상승" in sig else ("🔴" if "하락" in sig or "둔화" in sig else "🟡")
            item_lines.append(f"{sig_e} **{it['name']}** {fmt_pct(it.get('export_usd_yoy_pct'))} YoY")
        fields.append({"name": "🏭 주요 품목 (관세청)", "value": "\n".join(item_lines), "inline": False})

    # 결정 근거
    reasons = verdict.get("reasons", [])
    if reasons:
        fields.append({"name": "📋 판단 근거", "value": "\n".join(f"• {r}" for r in reasons[:3]), "inline": False})

    color = 0x10b981 if stance == "POSITIVE" else (0xef4444 if stance == "NEGATIVE" else 0xf59e0b)

    return {
        "title": f"{stance_emoji} 수출입 신규 데이터 수집 완료 — {new_fmt}",
        "description": f"**{prev_fmt} → {new_fmt}** 신규 월 데이터 업데이트\n{stance_label} 스탠스: {verdict.get('title', '')}",
        "color": color,
        "fields": fields,
        "footer": {"text": f"ECOS + 관세청 Hybrid | {data.get('updated_at', '')[:16]}"},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prev-month", required=True)
    parser.add_argument("--new-month",  required=True)
    args = parser.parse_args()

    if not JSON_PATH.exists():
        sys.exit(f"[error] JSON 없음: {JSON_PATH}")

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    cfg   = load_config()
    url   = cfg.get("collect_webhook_url") or cfg.get("webhook_url")
    embed = build_embed(data, args.prev_month, args.new_month)

    ok = post_webhook(url, {"username": "퀀트봇", "embeds": [embed]})
    if ok:
        print(f"[Discord] 수출입 {args.new_month} 알림 전송 완료")
    else:
        print(f"[Discord] 전송 실패", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

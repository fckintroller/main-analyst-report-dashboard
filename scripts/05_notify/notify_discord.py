"""
Anal_reports → Discord 알림 스크립트
pipeline.py 5단계 또는 단독 실행(run_notify.bat / Task Scheduler) 양쪽 지원

읽는 파일:
  - web/quant_data.js                            (stock_attractiveness, as_of, 각종 scores)
  - data/raw/factors/minute_tick_snapshot.csv    (당일 체결강도 — 일별)
  - data/raw/factors/news_sentiment_snapshot.csv (뉴스 감성 — 일별)
  - data/raw/factors/target_price_snapshot.csv   (애널리스트 타겟가 — 주기적 갱신)
  - data/database/quant_data.sqlite              (factor_news_sentiment_snapshot — 읽기 전용)

쓰는 파일: 없음

점수 산식 (score_daily_adjusted):
  0.60 × score_base_5factor  (월간 종합: 밸류/모멘텀/사이즈/유동성/ROE)
+ 0.15 × minute_tick_score   (당일 체결강도)
+ 0.15 × target_price_score  (애널리스트 타겟가 괴리)
+ 0.10 × news_sentiment_score (뉴스 감성)
"""

import json
import math
import os
import re
import sys
import sqlite3
import time
from pathlib import Path

import requests

# ── 경로 설정 ───────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_DIR  = SCRIPT_DIR.parents[1]          # Anal_reports/
WEB_JS       = PROJECT_DIR / "web" / "quant_data.js"
DB_PATH      = PROJECT_DIR / "data" / "database" / "quant_data.sqlite"
FACTORS_DIR  = PROJECT_DIR / "data" / "raw" / "factors"
SKILL_DIR    = Path(r"C:\claude cowork\05_skills\discord-webhook")
CONFIG_PATH  = SKILL_DIR / "config.json"

# 일별 팩터 가중치
W_BASE      = 0.60   # score_base_5factor (월간)
W_TICK      = 0.15   # minute_tick_score  (당일 체결강도)
W_TP        = 0.15   # target_price_score (타겟가격 괴리)
W_NEWS      = 0.10   # news_sentiment_score (뉴스 감성)


# ── 유틸 ────────────────────────────────────────────────────
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
                print(f"[rate-limit] {wait}s 대기", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"[error] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
        except requests.RequestException as e:
            time.sleep(2 ** attempt)
            print(f"[retry {attempt+1}] {e}", file=sys.stderr)
    return False


def send_embed(url: str, embed: dict, username: str = "퀀트봇") -> bool:
    time.sleep(0.5)   # Discord rate limit 여유
    return post_webhook(url, {"username": username, "embeds": [embed]})


# ── quant_data.js 파싱 ──────────────────────────────────────
def load_quant_data() -> dict:
    if not WEB_JS.exists():
        sys.exit(f"[error] quant_data.js 없음: {WEB_JS}")
    raw = WEB_JS.read_text(encoding="utf-8")
    prefix = "window.QUANT_DATA = "
    idx = raw.find(prefix)
    if idx == -1:
        sys.exit("[error] quant_data.js 형식 파싱 실패 — 'window.QUANT_DATA' 없음")
    json_str = raw[idx + len(prefix):].rstrip().rstrip(";").strip()
    return json.loads(json_str)


# ── 일별 스냅샷 팩터 로드 ────────────────────────────────────
def _load_csv_as_dict(path: Path, key_col: str, val_col: str) -> dict:
    """CSV → {ticker: float} 딕셔너리. 파일 없으면 빈 dict."""
    if not path.exists():
        print(f"[warn] 파일 없음 (스킵): {path.name}", file=sys.stderr)
        return {}
    try:
        import csv
        result = {}
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tk = str(row.get(key_col, "")).strip()
                raw = row.get(val_col, "")
                if tk and raw not in ("", None):
                    try:
                        result[tk] = float(raw)
                    except ValueError:
                        pass
        return result
    except Exception as e:
        print(f"[warn] {path.name} 읽기 실패: {e}", file=sys.stderr)
        return {}


def load_daily_factors() -> tuple[dict, dict, dict]:
    """(tick_map, tp_map, news_map) — 각각 {ticker: 0~1 score}"""
    tick_map = _load_csv_as_dict(
        FACTORS_DIR / "minute_tick_snapshot.csv", "ticker", "minute_tick_score")
    tp_map   = _load_csv_as_dict(
        FACTORS_DIR / "target_price_snapshot.csv", "ticker", "target_price_score")
    news_map = _load_csv_as_dict(
        FACTORS_DIR / "news_sentiment_snapshot.csv", "ticker", "news_sentiment_score")

    print(f"[daily_factors] 체결강도={len(tick_map)}종목  타겟가격={len(tp_map)}종목  뉴스감성={len(news_map)}종목")
    return tick_map, tp_map, news_map


def compute_daily_score(row: dict, tick_map: dict, tp_map: dict, news_map: dict) -> float:
    """일별 가중 종합점수 산출."""
    tk = str(row.get("ticker", "")).zfill(6)
    base = row.get("score_base_5factor")
    if base is None or (isinstance(base, float) and math.isnan(base)):
        return 0.0

    tick  = tick_map.get(tk)
    tp    = tp_map.get(tk)
    news  = news_map.get(tk)

    score  = W_BASE * float(base)
    w_used = W_BASE

    # 일별 팩터가 있는 경우에만 반영, 없으면 해당 가중치를 base에 재배분
    if tick is not None:
        score  += W_TICK * tick
        w_used += W_TICK
    if tp is not None:
        score  += W_TP * tp
        w_used += W_TP
    if news is not None:
        score  += W_NEWS * news
        w_used += W_NEWS

    # 가중치 합이 1이 안 될 때 정규화
    return score / w_used if w_used > 0 else 0.0


# ── 종목 선택 ────────────────────────────────────────────────
def get_top_candidates(rows: list, tick_map: dict, tp_map: dict, news_map: dict,
                       universe: str = "B", top_n: int = 5) -> list:
    """일별 가중 점수 기준 B 유니버스 Top N 종목."""
    universe_key = {"A": "kospi200_proxy", "B": "project_universe_b",
                    "C": "all_listed_screenable"}.get(universe, "project_universe_b")
    filtered = [r for r in rows if r.get(universe_key)]

    for r in filtered:
        r["_daily_score"] = compute_daily_score(r, tick_map, tp_map, news_map)

    filtered.sort(key=lambda r: r["_daily_score"], reverse=True)
    return filtered[:top_n]


# ── 뉴스 감성 (DB 읽기 전용) ─────────────────────────────────
def get_top_sentiment(top_n: int = 3) -> list:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT ticker, news_sentiment_score, news_sentiment_bucket,
                   positive_count, negative_count, article_count, latest_headline_date
            FROM factor_news_sentiment_snapshot
            ORDER BY news_sentiment_score DESC
            LIMIT ?
        """, (top_n,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[warn] 뉴스 감성 DB 조회 실패: {e}", file=sys.stderr)
        return []


# ── Embed 빌더 ──────────────────────────────────────────────
def _clean_row(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            result[k] = None
        else:
            result[k] = v
    return result


def _pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{v*100:.1f}%"

def _num(v, fmt=".1f") -> str:
    if v is None:
        return "N/A"
    try:
        return format(float(v), fmt)
    except Exception:
        return str(v)

def _score_bar(score) -> str:
    if score is None:
        return "─"
    filled = round(float(score) * 10)
    return "█" * filled + "░" * (10 - filled)


def build_header_embed(as_of: str, candidate_count: int, universe: str,
                       tick_count: int, tp_count: int, news_count: int) -> dict:
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    daily_note = f"체결강도 {tick_count}종 · 타겟가격 {tp_count}종 · 뉴스감성 {news_count}종 반영"
    return {
        "title": "📊 Anal_reports 일일 퀀트 브리핑",
        "description": (
            f"**기준일**: {as_of}  |  **전송**: {now}\n"
            f"**유니버스**: {universe} ({candidate_count}종목 중 Top 5 선정)\n"
            f"**점수**: 월간 60% + {daily_note}"
        ),
        "color": 0x5865F2,
        "footer": {"text": "Anal_reports 퀀트봇 • score_daily_adjusted 기준"},
    }


def build_stock_embed(rank: int, r: dict, tick_map: dict, tp_map: dict) -> dict:
    r = _clean_row(r)
    ticker  = str(r.get("ticker", "")).zfill(6)
    score   = r.get("_daily_score")
    base    = r.get("score_base_5factor")
    ret3m   = r.get("ret_3m")
    ret1m   = r.get("ret_1m")
    price   = r.get("price")
    per     = r.get("per")
    roe     = r.get("roe")
    risk    = r.get("risk_flags") or []

    color = 0x57F287 if (ret1m or 0) >= 0 else 0xED4245

    fields = [
        {"name": "종합 점수 (일별조정)", "value": f"`{_score_bar(score)}` {_pct(score)}", "inline": False},
        {"name": "월간 기본점수", "value": _pct(base), "inline": True},
        {"name": "1M 수익률",     "value": _pct(ret1m), "inline": True},
        {"name": "3M 수익률",     "value": _pct(ret3m), "inline": True},
        {"name": "현재가",        "value": f"{price:,.0f}원" if price else "N/A", "inline": True},
        {"name": "PER",           "value": _num(per), "inline": True},
        {"name": "ROE",           "value": _pct(roe) if roe else "N/A", "inline": True},
        {"name": "섹터",          "value": r.get("sector") or "─", "inline": True},
    ]

    # 당일 일별 팩터 현황
    daily_parts = []
    tick_v = tick_map.get(ticker)
    tp_v   = tp_map.get(ticker)
    if tick_v is not None:
        daily_parts.append(f"체결강도 {_pct(tick_v)}")
    if tp_v is not None:
        daily_parts.append(f"타겟가격 {_pct(tp_v)}")
    if daily_parts:
        fields.append({"name": "⚡ 오늘 일별 팩터", "value": " | ".join(daily_parts), "inline": False})

    # 세부 팩터
    sub_scores = []
    for key, label in [
        ("valuation_score", "밸류"), ("momentum_score", "모멘텀"),
        ("flow_score", "수급"), ("roe_score", "ROE"),
        ("liquidity_score", "유동성"),
    ]:
        v = r.get(key)
        if v is not None:
            sub_scores.append(f"{label} {_pct(v)}")
    if sub_scores:
        fields.append({"name": "세부 팩터", "value": " | ".join(sub_scores), "inline": False})

    if risk:
        fields.append({"name": "⚠️ 리스크", "value": "\n".join(f"• {f}" for f in risk[:3]), "inline": False})

    return {
        "title": f"#{rank}  {r.get('name', '')} ({r.get('ticker', '')})",
        "color": color,
        "fields": fields,
        "footer": {"text": r.get("market", "") + " • " + r.get("universe_primary", "")},
    }


def build_sentiment_embed(news_rows: list) -> dict:
    if not news_rows:
        return None
    lines = []
    for n in news_rows:
        score = n.get("news_sentiment_score") or 0
        bucket = n.get("news_sentiment_bucket") or ""
        icon  = "🟢" if score > 0 else ("🔴" if score < 0 else "⚪")
        lines.append(
            f"{icon} **{n.get('ticker')}** "
            f"(점수 {score:+.3f}, {bucket}, 기사 {n.get('article_count', 0)}건)"
        )
    return {
        "title": "📰 오늘의 뉴스 감성 상위 종목",
        "description": "\n".join(lines),
        "color": 0xFEE75C,
        "footer": {"text": "factor_news_sentiment_snapshot 기준"},
    }


def build_footer_embed(success_count: int, total: int) -> dict:
    import datetime
    return {
        "title": "✅ 파이프라인 완료",
        "description": f"전송 성공: {success_count}/{total}개 카드",
        "color": 0x57F287,
        "footer": {"text": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    }


# ── 메인 ────────────────────────────────────────────────────
def main():
    cfg = load_config()
    url = cfg.get("webhook_url")
    username = cfg.get("username", "퀀트봇")
    if not url:
        sys.exit("[error] config.json에 webhook_url 없음")

    print("[notify] quant_data.js 로드 중...")
    qd = load_quant_data()
    sa = qd.get("stock_attractiveness", {})
    rows  = sa.get("rows", [])
    as_of = sa.get("as_of", "unknown")
    print(f"[notify] 종목 {len(rows)}개 로드 완료 (기준일: {as_of})")

    # 일별 팩터 로드
    tick_map, tp_map, news_map = load_daily_factors()

    candidates = get_top_candidates(rows, tick_map, tp_map, news_map, universe="B", top_n=5)
    news_rows  = get_top_sentiment(top_n=3)

    total_cards = 1 + len(candidates) + (1 if news_rows else 0) + 1
    sent = 0

    # 헤더
    b_count = len([r for r in rows if r.get("project_universe_b")])
    if send_embed(url, build_header_embed(as_of, b_count, "B (KOSPI200+KOSDAQ150)",
                                         len(tick_map), len(tp_map), len(news_map)), username):
        sent += 1

    # Top 5 종목
    for i, r in enumerate(candidates, 1):
        embed = build_stock_embed(i, r, tick_map, tp_map)
        if send_embed(url, embed, username):
            sent += 1
        print(f"[notify] #{i} {r.get('name')} ({r.get('ticker')})  daily={r['_daily_score']:.3f}")

    # 뉴스 감성
    if news_rows:
        embed = build_sentiment_embed(news_rows)
        if embed and send_embed(url, embed, username):
            sent += 1

    # 마무리
    if send_embed(url, build_footer_embed(sent, total_cards), username):
        sent += 1

    print(f"[notify] 완료 - {sent}/{total_cards} 전송 성공")


if __name__ == "__main__":
    main()

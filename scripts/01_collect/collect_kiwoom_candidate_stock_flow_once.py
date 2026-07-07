"""Kiwoom candidate stock-flow snapshot collector.

Collect one snapshot of foreign/institution/program flow for a bounded candidate
universe: model BUY, top WATCH, current holdings, and optional manual tickers.

Outputs
-------
- data/raw/kiwoom/candidate_stock_flow/candidate_flow_YYYYMMDD.csv
- data/raw/kiwoom/candidate_stock_flow/latest_candidate_flow.json

Run
---
  .venv-kiwoom32/Scripts/python.exe scripts/01_collect/collect_kiwoom_candidate_stock_flow_once.py --max-tickers 80
  python scripts/01_collect/collect_kiwoom_candidate_stock_flow_once.py --demo --max-tickers 5
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_PAYLOAD = PROJECT_ROOT / "web" / "quant_data.js"
HOLDINGS_CSV = PROJECT_ROOT / "data" / "raw" / "kiwoom" / "latest_holdings.csv"
OUT_DIR = PROJECT_ROOT / "data" / "raw" / "kiwoom" / "candidate_stock_flow"
LOG_FILE = OUT_DIR / "candidate_flow_error.log"

CSV_COLS = [
    "collected_at",
    "trade_date",
    "ticker",
    "name",
    "candidate_source",
    "model_decision",
    "model_score",
    "foreign_net",
    "institution_net",
    "individual_net",
    "program_buy",
    "program_sell",
    "program_net",
    "source",
    "source_tr",
    "status",
    "raw_columns",
]


def _setup_logging() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )


def _to_int(val: Any) -> int | None:
    try:
        s = str(val).replace(",", "").replace("+", "").strip()
        if not s or s in {"-", "--", "nan", "NaN", "None"}:
            return None
        return int(float(s))
    except Exception:
        return None


def _to_float(val: Any) -> float | None:
    try:
        s = str(val).replace(",", "").replace("+", "").strip()
        if not s or s in {"-", "--", "nan", "NaN", "None"}:
            return None
        return float(s)
    except Exception:
        return None


def _pick(row: Any, columns: list[str], *names: str) -> int | None:
    normalized = {str(c).replace(" ", "").replace("_", ""): c for c in columns}
    for name in names:
        key = name.replace(" ", "").replace("_", "")
        col = normalized.get(key)
        if col is not None:
            val = _to_int(row.get(col))
            if val is not None:
                return val
    for name in names:
        key = name.replace(" ", "").replace("_", "")
        for nkey, col in normalized.items():
            if key in nkey:
                val = _to_int(row.get(col))
                if val is not None:
                    return val
    return None


def _first_data_row(df: Any) -> Any | None:
    if df is None or getattr(df, "empty", True):
        return None
    for _, row in df.iterrows():
        values = [str(v).strip() for v in row.tolist()]
        if values and not all(v in {"", "nan", "None"} for v in values):
            if any(v in {"날짜", "일자", "종목명", "개인", "외국인", "기관"} for v in values):
                continue
            return row
    return df.iloc[0]


def _load_quant_payload() -> dict[str, Any]:
    if not WEB_PAYLOAD.exists():
        return {}
    text = WEB_PAYLOAD.read_text(encoding="utf-8-sig")
    prefix = "window.QUANT_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):].strip().rstrip(";")
    return json.loads(text)


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_candidate_universe(max_tickers: int, max_watch: int, manual_tickers: list[str]) -> list[dict[str, Any]]:
    payload = _load_quant_payload()
    rows = payload.get("stock_attractiveness", {}).get("rows", []) or []
    candidates: dict[str, dict[str, Any]] = {}

    def add(ticker: str, name: str = "", source: str = "", decision: str = "", score: Any = None) -> None:
        t = str(ticker).strip().lstrip("A").zfill(6)
        if not t or t == "000000":
            return
        prev = candidates.get(t, {})
        sources = set(filter(None, str(prev.get("candidate_source", "")).split("+")))
        if source:
            sources.add(source)
        candidates[t] = {
            "ticker": t,
            "name": name or prev.get("name", ""),
            "candidate_source": "+".join(sorted(sources)),
            "model_decision": decision or prev.get("model_decision", ""),
            "model_score": score if score is not None else prev.get("model_score"),
        }

    buy = [r for r in rows if str(r.get("model_decision", r.get("decision", ""))).upper() == "BUY"]
    watch = [r for r in rows if str(r.get("model_decision", r.get("decision", ""))).upper() == "WATCH"]

    def score_of(r: dict[str, Any]) -> float:
        for key in ["model_score", "composite_score", "attractiveness_score", "paper_signal_score"]:
            v = _to_float(r.get(key))
            if v is not None:
                return v
        return 0.0

    for r in sorted(buy, key=score_of, reverse=True):
        add(r.get("ticker") or r.get("stock_code"), r.get("name") or r.get("corp_name") or r.get("corp_name_kr") or "", "model_buy", "BUY", score_of(r))
    for r in sorted(watch, key=score_of, reverse=True)[:max_watch]:
        add(r.get("ticker") or r.get("stock_code"), r.get("name") or r.get("corp_name") or r.get("corp_name_kr") or "", "model_watch", "WATCH", score_of(r))

    for h in _read_csv_dicts(HOLDINGS_CSV):
        add(h.get("ticker") or h.get("stock_code"), h.get("name", ""), "holding", "", None)

    for t in manual_tickers:
        add(t, "", "manual", "", None)

    # BUY/holding first, then higher model score.
    ordered = sorted(
        candidates.values(),
        key=lambda x: (
            "model_buy" not in x.get("candidate_source", ""),
            "holding" not in x.get("candidate_source", ""),
            -(float(x.get("model_score") or 0)),
            x["ticker"],
        ),
    )
    return ordered[:max_tickers]


def _request_stock_investor(kw: Any, ticker: str, date_str: str) -> tuple[dict[str, Any], str]:
    try:
        df = kw.block_request(
            "opt10059",
            **{
                "종목코드": ticker,
                "기간구분": "1",
                "시작일자": date_str,
                "종료일자": date_str,
                "output": "종목별투자자",
                "next": 0,
            },
        )
        row = _first_data_row(df)
        if row is None:
            return {"source_tr": "opt10059", "raw_columns": ""}, "opt10059:empty"
        cols = [str(c) for c in df.columns]
        result = {
            "individual_net": _pick(row, cols, "개인순매수", "개인투자자", "개인"),
            "foreign_net": _pick(row, cols, "외국인순매수", "외국인합계", "외국인"),
            "institution_net": _pick(row, cols, "기관계순매수", "기관합계", "기관"),
            "source_tr": "opt10059",
            "raw_columns": ",".join(cols[:40]),
        }
        return result, "ok" if any(result[k] is not None for k in ["individual_net", "foreign_net", "institution_net"]) else "opt10059:columns_unmapped"
    except Exception as exc:
        return {"source_tr": "opt10059", "raw_columns": ""}, f"opt10059:error:{exc}"


def _request_stock_program(kw: Any, ticker: str) -> tuple[dict[str, Any], str]:
    # opt90008/13 variants differ by installed API. Try both and store status.
    statuses: list[str] = []
    for tr in ["opt90008", "opt90013"]:
        try:
            df = kw.block_request(
                tr,
                **{
                    "종목코드": ticker,
                    "output": "종목일별프로그램매매추이",
                    "next": 0,
                },
            )
            row = _first_data_row(df)
            if row is None:
                statuses.append(f"{tr}:empty")
                continue
            cols = [str(c) for c in df.columns]
            buy = _pick(row, cols, "프로그램매수금액", "매수금액", "매수")
            sell = _pick(row, cols, "프로그램매도금액", "매도금액", "매도")
            net = _pick(row, cols, "프로그램순매수금액", "순매수금액", "순매수")
            if net is None and buy is not None and sell is not None:
                net = buy - sell
            result = {"program_buy": buy, "program_sell": sell, "program_net": net, "source_tr": tr, "raw_columns": ",".join(cols[:40])}
            if any(v is not None for v in [buy, sell, net]):
                return result, "ok"
            statuses.append(f"{tr}:columns_unmapped")
        except Exception as exc:
            statuses.append(f"{tr}:error:{exc}")
        time.sleep(0.2)
    return {"source_tr": "opt90008+opt90013", "raw_columns": ""}, "; ".join(statuses)

def collect_once(kw: Any, candidates: list[dict[str, Any]], demo: bool = False, delay_sec: float = 0.45) -> list[dict[str, Any]]:
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    trade_date = now.strftime("%Y%m%d")
    rows: list[dict[str, Any]] = []
    for i, cand in enumerate(candidates):
        row = {c: None for c in CSV_COLS}
        row.update({"collected_at": ts, "trade_date": trade_date, **cand, "source": "demo" if demo else "kiwoom"})
        if demo:
            row.update({"foreign_net": 1000 - i * 10, "institution_net": 500 - i * 5, "individual_net": -1500 + i * 15, "program_buy": 10000 + i, "program_sell": 9500 + i, "program_net": 500, "source_tr": "demo", "status": "ok", "raw_columns": ""})
        elif kw is None:
            row.update({"source_tr": "kiwoom_not_connected", "status": "kiwoom_not_connected", "raw_columns": ""})
        else:
            inv, inv_status = _request_stock_investor(kw, cand["ticker"], trade_date)
            time.sleep(delay_sec)
            prog, prog_status = _request_stock_program(kw, cand["ticker"])
            inv_tr = inv.get("source_tr", "")
            prog_tr = prog.get("source_tr", "")
            row.update(inv)
            row.update(prog)
            row["source_tr"] = "+".join(x for x in [inv_tr, prog_tr] if x)
            row["raw_columns"] = " | ".join(x for x in [inv.get("raw_columns", ""), prog.get("raw_columns", "")] if x)
            row["status"] = f"investor={inv_status}; program={prog_status}"
            time.sleep(delay_sec)
        rows.append(row)
        logging.info("%s %s status=%s foreign=%s inst=%s program=%s", row.get("ticker"), row.get("name"), row.get("status"), row.get("foreign_net"), row.get("institution_net"), row.get("program_net"))
    return rows


def has_usable_candidate_flow(rows: list[dict[str, Any]]) -> bool:
    value_cols = ("foreign_net", "institution_net", "individual_net", "program_buy", "program_sell", "program_net")
    for row in rows:
        if str(row.get("status") or "") == "kiwoom_not_connected":
            continue
        if any(row.get(col) is not None for col in value_cols):
            return True
    return False


def append_rows(rows: list[dict[str, Any]], update_latest: bool = True) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = OUT_DIR / f"candidate_flow_{date_str}.csv"
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
    if update_latest:
        latest = OUT_DIR / "latest_candidate_flow.json"
        latest.write_text(json.dumps({"rows": rows, "updated_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        logging.warning("usable candidate flow missing; latest_candidate_flow.json not overwritten")
    return path


def connect_kiwoom(no_login: bool = False) -> Any | None:
    from PyQt5.QtWidgets import QApplication
    from pykiwoom.kiwoom import Kiwoom

    app = QApplication.instance() or QApplication(sys.argv)
    kw = Kiwoom()
    if kw.GetConnectState() != 1:
        if no_login:
            logging.warning("Kiwoom not connected; --no-login set, skipping login dialog")
            return None
        logging.info("Kiwoom not connected; opening login dialog")
        kw.CommConnect(block=True)
    if kw.GetConnectState() != 1:
        logging.warning("Kiwoom login did not establish a connected session")
        return None
    logging.info("Kiwoom connected")
    return kw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="write deterministic demo rows without Kiwoom")
    p.add_argument("--max-tickers", type=int, default=80)
    p.add_argument("--max-watch", type=int, default=40)
    p.add_argument("--ticker", action="append", default=[], help="manual ticker to include; can be repeated")
    p.add_argument("--delay-sec", type=float, default=0.45)
    p.add_argument("--no-login", action="store_true", help="do not open Kiwoom login dialog; write unavailable rows instead")
    p.add_argument("--fail-if-unavailable", action="store_true", help="exit non-zero when no usable Kiwoom values are collected")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    _setup_logging()
    candidates = build_candidate_universe(args.max_tickers, args.max_watch, args.ticker)
    if not candidates:
        raise SystemExit("no candidates found from quant_data.js/latest_holdings/manual tickers")
    logging.info("candidate universe size=%s", len(candidates))
    kw = None if args.demo else connect_kiwoom(no_login=args.no_login)
    rows = collect_once(kw, candidates, demo=args.demo, delay_sec=args.delay_sec)
    usable = args.demo or has_usable_candidate_flow(rows)
    path = append_rows(rows, update_latest=usable)
    logging.info("saved %s rows -> %s usable=%s", len(rows), path, usable)
    if args.fail_if_unavailable and not usable:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

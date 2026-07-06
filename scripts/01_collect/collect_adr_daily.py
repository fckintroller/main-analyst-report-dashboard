"""
ADR 일별 incremental 수집.
valuation_adrs_{name} 테이블의 최신 날짜 다음날부터 오늘까지 yfinance로 append.
DB 업데이트 후 data/raw/valuation/adrs/*.csv도 동기화 (load_to_db.py 덮어쓰기 방지).
"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
CSV_DIR = PROJECT_ROOT / "data" / "raw" / "valuation" / "adrs"

ADR_MAP = {
    "kbfinancial": ("KB",   "KBFinancial.csv"),
    "shinhan":     ("SHG",  "Shinhan.csv"),
    "woori":       ("WF",   "Woori.csv"),
    "posco":       ("PKX",  "Posco.csv"),
    "kt":          ("KT",   "KT.csv"),
    "sktelecom":   ("SKM",  "SKTelecom.csv"),
    "kepco":       ("KEP",  "KEPCO.csv"),
    "lgdisplay":   ("LPL",  "LGDisplay.csv"),
    "coupang":     ("CPNG", "Coupang.csv"),
}


def _sync_csv(conn: sqlite3.Connection, name: str, csv_name: str) -> None:
    """DB 테이블 전체를 CSV에 저장 (load_to_db.py 덮어쓰기 방지)."""
    tbl = f"valuation_adrs_{name}"
    try:
        df = pd.read_sql(
            f"SELECT * FROM [{tbl}] ORDER BY [Unnamed: 0]", conn
        )
        csv_path = CSV_DIR / csv_name
        df.to_csv(csv_path, index=False)
    except Exception as e:
        print(f"[WARN] CSV sync 실패 {csv_name}: {e}", file=sys.stderr)


def run():
    today = date.today().isoformat()
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    updated = 0
    synced = 0

    for name, (ticker, csv_name) in ADR_MAP.items():
        tbl = f"valuation_adrs_{name}"
        try:
            max_date = conn.execute(f"SELECT MAX([Unnamed: 0]) FROM [{tbl}]").fetchone()[0]
        except Exception:
            max_date = "2009-01-01"

        start = (pd.Timestamp(max_date) + pd.Timedelta(days=1)).date().isoformat()
        if start > today:
            print(f"[SKIP] {name}({ticker}): 최신 ({max_date})")
        else:
            try:
                df = yf.download(ticker, start=start, end=today, progress=False, auto_adjust=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                if df.empty:
                    print(f"[EMPTY] {name}({ticker}): 신규 데이터 없음")
                else:
                    df = df.reset_index()
                    df.columns = [str(c) for c in df.columns]
                    date_col = next(c for c in df.columns if c.lower() in ("date", "datetime"))
                    df = df.rename(columns={date_col: "Unnamed: 0"})
                    df["Unnamed: 0"] = pd.to_datetime(df["Unnamed: 0"]).dt.strftime("%Y-%m-%d")
                    df.to_sql(tbl, conn, if_exists="append", index=False)
                    print(f"[OK] {name}({ticker}): +{len(df)}행 ({df['Unnamed: 0'].min()} ~ {df['Unnamed: 0'].max()})")
                    updated += 1
            except Exception as e:
                print(f"[ERR] {name}({ticker}): {e}", file=sys.stderr)

        # CSV가 DB보다 오래됐으면 항상 동기화 (load_to_db.py 덮어쓰기 방지)
        csv_path = CSV_DIR / csv_name
        csv_max = None
        if csv_path.exists():
            try:
                csv_max = pd.read_csv(csv_path, usecols=[0]).iloc[:, 0].max()
            except Exception:
                pass
        db_max = conn.execute(f"SELECT MAX([Unnamed: 0]) FROM [{tbl}]").fetchone()[0]
        if csv_max != db_max:
            _sync_csv(conn, name, csv_name)
            synced += 1

    conn.close()
    print(f"ADR 갱신 완료: {updated}/{len(ADR_MAP)}종목 (CSV sync: {synced}건)")


if __name__ == "__main__":
    run()

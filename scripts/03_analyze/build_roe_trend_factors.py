"""
ROE 트렌드 팩터 구축 (pykrx fundamental 기반).

소스: stock_detail_{ticker}_fundamental (BPS, EPS 일별 스냅샷)
      BPS = 주당 순자산, EPS = 주당 순이익(trailing 12M)
      implied TTM ROE = EPS / BPS (단, BPS > 0 조건)

월말 리샘플 후 계산:
  roe_current        : 최신 ROE (%)
  roe_1y_ago         : 12개월 전 ROE
  roe_mom_1y         : YoY ROE 변화 (pp)
  roe_3m_trend       : 3개월 ROE 변화 (단기 방향성)
  roe_improving      : roe_3m_trend > 0 여부 (bool)
  roe_sector_pct     : 섹터 내 ROE 백분위
  roe_trend_score    : ROE 개선 추세 점수 (0~1)
  roe_composite_score: ROE 수준(50%) + 개선 추세(50%)

출력 DB 테이블:
  factor_roe_trend_snapshot  : 종목별 최신 스냅샷
  factor_roe_trend_month     : 종목×월간 시계열 (백테스트용)
  factor_roe_trend_catalog   : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"

MIN_ROWS = 3        # 최소 월 수 (ROE 계산용)
MIN_SECTOR_N = 5
SAVE_EVERY = 50

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_fundamental_tickers(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_detail_%_fundamental'"
    ).fetchall()
    tickers = []
    for (name,) in rows:
        parts = name.split("_")
        if len(parts) >= 4:
            tickers.append(parts[-2])
    return sorted(set(tickers))


def _load_sector_map(conn: sqlite3.Connection) -> dict[str, str]:
    if SECTOR_MAP_PATH.exists():
        try:
            sm = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
            return dict(zip(sm.iloc[:, 0].astype(str).str.zfill(6), sm.iloc[:, 1].astype(str)))
        except Exception:
            pass
    try:
        df = pd.read_sql("SELECT DISTINCT ticker, sector FROM factor_valuation_per_pbr_month", conn)
        return dict(zip(df["ticker"], df["sector"]))
    except Exception:
        return {}


def _process_ticker(conn: sqlite3.Connection, ticker: str) -> pd.DataFrame | None:
    tbl = f"stock_detail_{ticker}_fundamental"
    try:
        df = pd.read_sql(f"SELECT * FROM [{tbl}] ORDER BY 1", conn)
    except Exception:
        return None

    if len(df) < MIN_ROWS:
        return None

    # 컬럼: date(0), BPS(1), PER(2), PBR(3), EPS(4), DIV(5), DPS(6)
    date_col = df.columns[0]
    try:
        bps_col = "BPS"
        eps_col = "EPS"
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["BPS"] = pd.to_numeric(df[bps_col], errors="coerce")
        df["EPS"] = pd.to_numeric(df[eps_col], errors="coerce")
    except KeyError:
        return None

    df = df.dropna(subset=[date_col, "BPS", "EPS"]).sort_values(date_col)
    df = df[df["BPS"] > 0]   # BPS=0 또는 음수 제외 (무의미)

    if len(df) < MIN_ROWS:
        return None

    df["roe"] = df["EPS"] / df["BPS"]   # 단위 없음 (e.g. 0.103 = 10.3%)

    # 월말 리샘플 (마지막 영업일 값)
    monthly = (df.set_index(date_col)["roe"]
                 .resample("ME").last()
                 .dropna())

    if len(monthly) < MIN_ROWS:
        return None

    result = pd.DataFrame({"period": monthly.index, "roe": monthly.values, "ticker": ticker})
    result["period"] = result["period"].dt.strftime("%Y-%m-01")
    return result


def _compute_trend_features(df_ticker: pd.DataFrame) -> dict | None:
    """단일 종목의 월별 ROE 시계열에서 트렌드 피처 추출 (최신 기준)."""
    df = df_ticker.sort_values("period")
    if len(df) < 1:
        return None

    roe_series = df["roe"].values
    n = len(roe_series)

    roe_current = float(roe_series[-1])
    roe_3m_ago  = float(roe_series[-4]) if n >= 4 else np.nan
    roe_6m_ago  = float(roe_series[-7]) if n >= 7 else np.nan
    roe_1y_ago  = float(roe_series[-13]) if n >= 13 else np.nan

    roe_mom_3m = roe_current - roe_3m_ago  if pd.notna(roe_3m_ago) else np.nan
    roe_mom_6m = roe_current - roe_6m_ago  if pd.notna(roe_6m_ago) else np.nan
    roe_mom_1y = roe_current - roe_1y_ago  if pd.notna(roe_1y_ago) else np.nan

    return {
        "ticker":         df["ticker"].iloc[0],
        "snapshot_date":  df["period"].iloc[-1],
        "roe_current":    roe_current,
        "roe_3m_ago":     roe_3m_ago,
        "roe_6m_ago":     roe_6m_ago,
        "roe_1y_ago":     roe_1y_ago,
        "roe_mom_3m":     roe_mom_3m,
        "roe_mom_6m":     roe_mom_6m,
        "roe_mom_1y":     roe_mom_1y,
        "roe_improving":  int(roe_mom_3m > 0) if pd.notna(roe_mom_3m) else np.nan,
    }


def _roe_bucket(roe: float) -> str:
    """ROE 수준 분류 (연율 기준)."""
    if pd.isna(roe):
        return "unknown"
    pct = roe * 100
    if pct >= 20:
        return "high_quality"
    if pct >= 12:
        return "quality"
    if pct >= 5:
        return "average"
    if pct >= 0:
        return "low"
    return "negative"


def build(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = _load_fundamental_tickers(conn)
    sector_map = _load_sector_map(conn)
    logger.info("%d개 종목 처리 시작", len(tickers))

    all_monthly: list[pd.DataFrame] = []
    records: list[dict] = []

    for i, ticker in enumerate(tickers, 1):
        monthly_df = _process_ticker(conn, ticker)
        if monthly_df is not None and len(monthly_df) >= MIN_ROWS:
            all_monthly.append(monthly_df)
            feat = _compute_trend_features(monthly_df)
            if feat:
                records.append(feat)

        if i % 100 == 0:
            logger.info("  %d/%d 완료", i, len(tickers))

    # ── 스냅샷 데이터프레임 ──────────────────────────────────────
    snap = pd.DataFrame(records)
    if snap.empty:
        logger.error("데이터 없음"); return snap, pd.DataFrame()

    snap["sector"] = snap["ticker"].map(sector_map).fillna("unknown")

    # 섹터 내 ROE 수준 백분위
    snap["roe_sector_pct"] = snap.groupby("sector")["roe_current"].rank(pct=True)
    small_sectors = snap.groupby("sector")["roe_current"].count()
    small_sectors = small_sectors[small_sectors < MIN_SECTOR_N].index
    snap.loc[snap["sector"].isin(small_sectors), "roe_sector_pct"] = np.nan

    # ROE 개선 추세 점수 (6M z-score 기반 → 0~1)
    roe_mom_mean = snap["roe_mom_6m"].mean()
    roe_mom_std  = snap["roe_mom_6m"].std()
    if roe_mom_std and roe_mom_std > 0:
        snap["roe_trend_z"] = (snap["roe_mom_6m"] - roe_mom_mean) / roe_mom_std
        snap["roe_trend_score"] = (snap["roe_trend_z"].clip(-3, 3) / 6 + 0.5).clip(0, 1)
    else:
        snap["roe_trend_score"] = 0.5

    # 복합 점수
    def _composite(row: pd.Series) -> float:
        parts, weights = [], []
        if pd.notna(row["roe_sector_pct"]):
            parts.append(row["roe_sector_pct"]); weights.append(0.5)
        if pd.notna(row["roe_trend_score"]):
            parts.append(row["roe_trend_score"]); weights.append(0.5)
        if not parts:
            return np.nan
        return sum(p * w for p, w in zip(parts, weights)) / sum(weights)

    snap["roe_composite_score"] = snap.apply(_composite, axis=1)
    snap["roe_bucket"] = snap["roe_current"].apply(_roe_bucket)

    snap_out = snap[[
        "ticker", "snapshot_date", "sector",
        "roe_current", "roe_3m_ago", "roe_6m_ago", "roe_1y_ago",
        "roe_mom_3m", "roe_mom_6m", "roe_mom_1y",
        "roe_improving",
        "roe_sector_pct", "roe_trend_score", "roe_composite_score",
        "roe_bucket",
    ]]

    # ── 월간 시계열 데이터프레임 (백테스트용) ─────────────────────
    if all_monthly:
        ts = pd.concat(all_monthly, ignore_index=True)
        ts["sector"] = ts["ticker"].map(sector_map).fillna("unknown")
        # 월×섹터 ROE 백분위
        ts["roe_sector_pct_ts"] = ts.groupby(["period", "sector"])["roe"].rank(pct=True)
    else:
        ts = pd.DataFrame()

    logger.info("스냅샷: %d종목, 시계열: %d행", len(snap_out), len(ts))
    return snap_out, ts


CATALOG = [
    ("roe_current",         "최신 ROE (TTM)",         "소수점, 예: 0.103 = 10.3%",           "snapshot"),
    ("roe_mom_3m",          "3개월 ROE 변화",          "pp 단위 (0.02 = +2pp)",                "snapshot"),
    ("roe_mom_1y",          "YoY ROE 변화",            "pp 단위",                              "snapshot"),
    ("roe_improving",       "ROE 단기 개선 여부",       "1=3M 전 대비 상승, 0=하락",            "snapshot"),
    ("roe_sector_pct",      "섹터 내 ROE 백분위",       "0~1, 높을수록 섹터 내 고ROE",          "snapshot"),
    ("roe_trend_score",     "ROE 개선 추세 점수",       "0~1, 6M 변화율 z-score 기반",          "snapshot"),
    ("roe_composite_score", "ROE 복합 점수",            "0~1 = 섹터수준(50%) + 추세(50%)",      "snapshot"),
    ("roe_bucket",          "ROE 버킷",                 "high_quality≥20%/quality≥12%/average≥5%/low≥0%/negative", "snapshot"),
]


def run():
    logger.info("roe_trend 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        snap, ts = build(conn)

        snap.to_sql("factor_roe_trend_snapshot", conn, if_exists="replace", index=False)
        logger.info("  → factor_roe_trend_snapshot 적재: %d행", len(snap))

        if not ts.empty:
            ts.to_sql("factor_roe_trend_month", conn, if_exists="replace", index=False)
            logger.info("  → factor_roe_trend_month 적재: %d행", len(ts))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_roe_trend_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_roe_trend_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return snap, ts


if __name__ == "__main__":
    snap, ts = run()
    print("\n=== ROE 우량 Top 20 ===")
    print(snap.nlargest(20, "roe_composite_score")[
        ["ticker", "sector", "roe_current", "roe_mom_1y", "roe_composite_score", "roe_bucket"]
    ].assign(roe_pct=lambda d: (d["roe_current"] * 100).round(1)).to_string())

"""
선행(Forward) PER 밸류에이션 팩터 생성.

목적:
- 애널리스트 컨센서스 기반 선행 EPS(Forward EPS)로 "지금 이 종목이
  미래 이익 대비 섹터 내에서 싼가 비싼가"를 1차 팩터 후보군으로 정리한다.
- 기존 factor_valuation_per_pbr_month 은 현재까지의 실적(trailing) 기반이라
  이익 턴어라운드 또는 고성장 구간에서 왜곡된다.
  선행 PER은 그 왜곡을 보완하는 보조 팩터로 사용한다.

입력 raw:
- data/raw/valuation/earnings_consensus.csv  (ticker, consensus_raw JSON)
  * consensus_raw JSON row 9 = EPS(원), row 10 = PER(배)
  * 컬럼 키에 연간 예상: *.12(E)  /  직전 실적: *.12 (E 없음)
- data/raw/stock_detail/sector_map.csv  (ticker → 업종명)
- SQLite: stock_market_snapshot_kospi/kosdaq_market_cap_by_ticker_*  (최신 종가)

출력 CSV:
- data/raw/factors/forward_per_snapshot.csv
- data/raw/factors/forward_per_factor_catalog.csv

출력 SQLite 테이블:
- factor_forward_per_snapshot   (스냅샷 단면, period 컬럼은 스냅샷 기준일)
- factor_forward_per_catalog

Caveats:
- 스냅샷 데이터 — 컨센서스는 2026-06-05 수집 기준, 시계열 backtest 불가
- 애널리스트 커버리지 있는 종목만 (~710/2742) → 중소형주 커버리지 낮음
- 컨센서스 EPS는 구조적 낙관 편향(analyst optimism bias) 존재
- forward_eps <= 0 (적자 전망) 종목은 PER 계산 제외, NaN 처리
- 섹터 내 종목 수 MIN_SECTOR_N 미만이면 섹터 백분위 NaN 처리
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
CONSENSUS_PATH = PROJECT_ROOT / "data" / "raw" / "valuation" / "earnings_consensus.csv"
SECTOR_MAP_PATH = PROJECT_ROOT / "data" / "raw" / "stock_detail" / "sector_map.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors"

SNAPSHOT_DATE = "2026-06-05"
MIN_SECTOR_N = 3   # 섹터 내 forward PER 백분위 산출 최소 종목 수

# consensus_raw JSON에서 행 인덱스 의미
IDX_EPS = "9"
IDX_PER = "10"


# ──────────────────────────────────────────────────────────────
# 1. 종가 로드 (KRX 스냅샷)
# ──────────────────────────────────────────────────────────────
def load_price_map(conn: sqlite3.Connection) -> pd.Series:
    frames = []
    for market in ("kospi", "kosdaq"):
        try:
            df = pd.read_sql(
                f"SELECT * FROM stock_market_snapshot_{market}_market_cap_by_ticker_20260605",
                conn,
            )
            df.columns = ["ticker", "close", "market_cap", "volume", "trading_value", "shares"]
            frames.append(df[["ticker", "close"]])
        except Exception:
            pass
    if not frames:
        return pd.Series(dtype=float)
    combined = pd.concat(frames, ignore_index=True)
    combined["close"] = pd.to_numeric(combined["close"], errors="coerce")
    return combined.set_index("ticker")["close"]


# ──────────────────────────────────────────────────────────────
# 2. 컨센서스 파싱
# ──────────────────────────────────────────────────────────────
def _best_forward_annual_col(data: dict) -> str | None:
    """JSON 키에서 가장 최근 연간 예상 컬럼(*.12(E))을 반환."""
    candidates = [
        c for c in data
        if re.search(r"\d{4}\.12\(E\)", c)
    ]
    return sorted(candidates)[-1] if candidates else None


def _best_trailing_annual_col(data: dict) -> str | None:
    """JSON 키에서 가장 최근 실적 연간 컬럼(*.12, E 없음)을 반환."""
    candidates = [
        c for c in data
        if re.search(r"\d{4}\.12", c) and "(E)" not in c
    ]
    return sorted(candidates)[-1] if candidates else None


def _safe_float(v) -> float | None:
    try:
        val = float(v)
        return val if not (val != val) else None  # nan guard
    except (TypeError, ValueError):
        return None


def parse_consensus(df_raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df_raw.iterrows():
        ticker = str(row["ticker"])
        try:
            data = json.loads(row["consensus_raw"])
        except Exception:
            continue

        fwd_col = _best_forward_annual_col(data)
        trail_col = _best_trailing_annual_col(data)
        if fwd_col is None:
            continue

        m = re.search(r"(\d{4})\.12\(E\)", fwd_col)
        forward_year = int(m.group(1)) if m else None

        fwd = data[fwd_col]
        trail = data[trail_col] if trail_col else {}

        forward_eps = _safe_float(fwd.get(IDX_EPS))
        forward_per_consensus = _safe_float(fwd.get(IDX_PER))
        trailing_eps = _safe_float(trail.get(IDX_EPS)) if trail else None
        trailing_per_consensus = _safe_float(trail.get(IDX_PER)) if trail else None

        records.append(
            {
                "ticker": ticker,
                "forward_year": forward_year,
                "forward_eps": forward_eps,
                "forward_per_consensus": forward_per_consensus,
                "trailing_eps": trailing_eps,
                "trailing_per_consensus": trailing_per_consensus,
            }
        )
    return pd.DataFrame(records)


# ──────────────────────────────────────────────────────────────
# 3. 파생 지표 계산
# ──────────────────────────────────────────────────────────────
def compute_derived(df: pd.DataFrame, price_map: pd.Series) -> pd.DataFrame:
    out = df.copy()

    # 현재 종가 기준 선행 PER (메인 팩터)
    out["close_price"] = out["ticker"].map(price_map)
    out["forward_per"] = np.where(
        (out["forward_eps"] > 0) & out["close_price"].notna(),
        out["close_price"] / out["forward_eps"],
        np.nan,
    )

    # EPS 성장 기대율
    out["eps_growth_expected"] = np.where(
        (out["trailing_eps"].notna()) & (out["trailing_eps"].abs() > 1),
        out["forward_eps"] / out["trailing_eps"] - 1,
        np.nan,
    )

    # 선행 PER 할인율 대비 후행 (음수 = 이익 성장으로 선행이 저렴)
    out["per_discount_vs_trailing"] = np.where(
        (out["trailing_per_consensus"].notna()) & (out["trailing_per_consensus"] > 0)
        & (out["forward_per"].notna()),
        out["forward_per"] / out["trailing_per_consensus"] - 1,
        np.nan,
    )

    return out


# ──────────────────────────────────────────────────────────────
# 4. 섹터 내 백분위
# ──────────────────────────────────────────────────────────────
def load_sector_map() -> pd.DataFrame:
    df = pd.read_csv(SECTOR_MAP_PATH, encoding="utf-8-sig")
    df.columns = ["ticker", "name", "sector", "price", "change", "pct", "mktcap", "market"]
    return df[["ticker", "sector"]].drop_duplicates("ticker")


def _sector_rank(group: pd.Series) -> pd.Series:
    valid = group.dropna()
    if len(valid) < MIN_SECTOR_N:
        return pd.Series(np.nan, index=group.index)
    return group.rank(pct=True, na_option="keep")


def add_sector_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # 선행 PER 섹터 내 백분위 (낮을수록 섹터 내 저평가)
    out["forward_per_sector_pct"] = (
        out.groupby("sector")["forward_per"].transform(_sector_rank)
    )
    # 전 시장 백분위 (참고용)
    valid = out["forward_per"].dropna()
    if len(valid) >= 10:
        out["forward_per_mkt_pct"] = out["forward_per"].rank(pct=True, na_option="keep")
    else:
        out["forward_per_mkt_pct"] = np.nan
    return out


# ──────────────────────────────────────────────────────────────
# 5. 종합 점수
# ──────────────────────────────────────────────────────────────
def add_forward_valuation_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # 섹터 내 저평가(낮은 pct = 좋음) + 이익 성장(높은 eps_growth = 좋음)
    cheap_component = 1 - out["forward_per_sector_pct"]

    # eps_growth: clip 후 0~1 정규화 (-50%~+300% → 0~1)
    eps_norm = out["eps_growth_expected"].clip(-0.5, 3.0)
    eps_norm = (eps_norm - (-0.5)) / (3.0 - (-0.5))

    components = pd.concat([cheap_component, eps_norm], axis=1)
    out["forward_valuation_score"] = components.mean(axis=1, skipna=True)
    out.loc[components.isna().all(axis=1), "forward_valuation_score"] = np.nan

    conds = [
        out["forward_valuation_score"] >= 0.7,
        out["forward_valuation_score"] >= 0.55,
        out["forward_valuation_score"] <= 0.3,
        out["forward_valuation_score"] <= 0.45,
    ]
    choices = ["deep_value", "cheap", "expensive", "rich"]
    out["forward_valuation_bucket"] = np.select(conds, choices, default="neutral")
    out.loc[out["forward_valuation_score"].isna(), "forward_valuation_bucket"] = "N/A"

    return out


# ──────────────────────────────────────────────────────────────
# 6. 카탈로그
# ──────────────────────────────────────────────────────────────
def build_catalog() -> pd.DataFrame:
    rows = [
        (
            "forward_per",
            "선행 PER 기준 섹터 내 상대 저평가인가?",
            "forward_per / forward_per_sector_pct",
            "컨센서스 EPS",
            "현재가 / 선행EPS(컨센서스 연간 예상). 섹터 내 백분위(0=가장 쌈, 1=가장 비쌈)",
            "핵심",
        ),
        (
            "forward_per",
            "이익 성장으로 선행이 후행보다 얼마나 저렴한가?",
            "per_discount_vs_trailing",
            "컨센서스 EPS",
            "forward_per / trailing_per_consensus - 1. 음수 = 이익 성장 기대로 선행이 저렴",
            "핵심",
        ),
        (
            "forward_per",
            "컨센서스 기준 내년 이익 성장률 기대치는?",
            "eps_growth_expected",
            "컨센서스 EPS",
            "(forward_eps / trailing_eps) - 1. 양수 = 이익 성장 기대",
            "해석",
        ),
        (
            "forward_per",
            "선행 밸류에이션 종합 신호는?",
            "forward_valuation_score / forward_valuation_bucket",
            "forward_per + eps_growth 합성",
            "섹터내 저평가 + 이익성장 기대를 합성한 0~1 점수 (deep_value~expensive)",
            "핵심",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "factor_family", "question", "factor_name",
            "source_column", "interpretation", "preferred_use",
        ],
    )


# ──────────────────────────────────────────────────────────────
# 7. 저장
# ──────────────────────────────────────────────────────────────
def save_outputs(
    snap: pd.DataFrame,
    catalog: pd.DataFrame,
    conn: sqlite3.Connection,
) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snap_path = OUTPUT_DIR / "forward_per_snapshot.csv"
    cat_path = OUTPUT_DIR / "forward_per_factor_catalog.csv"

    snap.to_csv(snap_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(cat_path, index=False, encoding="utf-8-sig")

    snap.to_sql("factor_forward_per_snapshot", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_forward_per_catalog", conn, if_exists="replace", index=False)

    return {
        "snapshot_path": str(snap_path),
        "catalog_path": str(cat_path),
        "snapshot_rows": len(snap),
        "tickers_with_forward_per": int(snap["forward_per"].notna().sum()),
        "sectors": int(snap["sector"].nunique()),
        "catalog_rows": len(catalog),
    }


# ──────────────────────────────────────────────────────────────
# 8. main
# ──────────────────────────────────────────────────────────────
def build_outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(DB_PATH) as conn:
        price_map = load_price_map(conn)

    df_raw = pd.read_csv(CONSENSUS_PATH, encoding="utf-8-sig")
    parsed = parse_consensus(df_raw)

    sector_map = load_sector_map()
    parsed = parsed.merge(sector_map, on="ticker", how="left")

    parsed = compute_derived(parsed, price_map)
    parsed = add_sector_percentiles(parsed)
    parsed = add_forward_valuation_score(parsed)

    parsed["snapshot_date"] = SNAPSHOT_DATE
    catalog = build_catalog()
    return parsed, catalog


def main() -> None:
    snap, catalog = build_outputs()
    with sqlite3.connect(DB_PATH) as conn:
        result = save_outputs(snap, catalog, conn)
    print(result)


if __name__ == "__main__":
    main()

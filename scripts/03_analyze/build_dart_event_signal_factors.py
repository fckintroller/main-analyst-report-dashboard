"""
종목별 DART 공시 이벤트 신호(빈도/존재 여부) 팩터 생성.

목적:
- 04_valuation.py의 fetch_dart_filings()는 "오늘 하루" 스냅샷이라
  (valuation_dart_all_filings 709행, rcept_dt 전부 동일 날짜) 이벤트 추세를 볼 수 없었다.
- collect_dart_event_history_once.py로 신규 수집한 종목별 12개월 공시 이력
  (자사주/배당/임원·주요주주 지분변동)에서 "이번 달 이런 이벤트가 있었는가,
  최근 빈도가 평소보다 활발한가"를 1차 팩터 후보군으로 정리한다.

입력 raw:
- data/raw/valuation/dart_events/{ticker}.csv
  (rcept_dt, corp_name, stock_code, report_nm, rcept_no, event_type)

출력 CSV (격리 폴더):
- data/raw/factors/factor_not_ready/dart_event_signal_month.csv
- data/raw/factors/factor_not_ready/dart_event_signal_factor_catalog.csv

출력 SQLite 테이블:
- factor_dart_event_signal_month
- factor_dart_event_signal_catalog

⚠️  실제 분석 사용 금지 — factor_not_ready 격리 상태
  이 팩터는 아래 이유로 실전 분석·모델 피처에 사용해서는 안 된다:
  1. 수집 이력이 ~12개월로 너무 짧아 자기 과거 비교가 불안정하다.
  2. 내부자 거래 방향(매수/매도)을 구분하지 못해 신호 방향성이 모호하다.
  3. 이벤트 0건 종목이 "미공시 우량주"인지 "공시 없는 저활동주"인지 구별 불가능하다.
  준비 완료 기준: 최소 36개월 이력 확보 + 매수/매도 방향 분리 수집 후 재검토.

Caveat:
- 모델 예측 결과가 아니라 모델링 전 1차 가공 팩터 후보군이다.
- "임원ㆍ주요주주 소유상황보고"는 매수/매도 방향을 구분하지 않는 단순 신고 건수다.
  → "내부자 거래가 매수 방향"이라고 단정하지 않고 "신고 활동이 평소보다 활발한가"로만 해석한다.
- 신규 수집 데이터라 historical이 약 12개월로 짧다 → 자기 과거 비교 윈도우를 6개월로 좁게 설정했고,
  그래도 부족한 구간은 N/A로 남기고 임의 보간하지 않는다.
- 이벤트가 전혀 없는 종목·구간은 0건으로 표기한다 (결측이 아니라 "관측된 사실").
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"
DART_EVENTS_DIR = PROJECT_ROOT / "data" / "raw" / "valuation" / "dart_events"
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "factors" / "factor_not_ready"

OWN_HISTORY_WINDOW = 6   # 자기 과거 z-score trailing 개월 수 (수집 이력이 짧아 6개월로 설정)
RECENT_WINDOW = 3        # "최근 N개월 누적" 집계 창 (개월)
EVENT_TYPES = ["buyback", "dividend", "insider"]


def discover_tickers() -> list[str]:
    return [p.stem for p in sorted(DART_EVENTS_DIR.glob("*.csv"))]


def load_event_panel(tickers: list[str]) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        path = DART_EVENTS_DIR / f"{ticker}.csv"
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        if df.empty:
            continue
        df = df.copy()
        df["ticker"] = ticker
        df["rcept_dt"] = pd.to_datetime(df["rcept_dt"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["rcept_dt"])
        frames.append(df[["ticker", "rcept_dt", "event_type"]])
    if not frames:
        return pd.DataFrame(columns=["ticker", "rcept_dt", "event_type"])
    return pd.concat(frames, ignore_index=True)


def _month_range(events: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """이벤트가 0건인 종목·월도 0으로 표기하기 위해 (ticker × period) 전체 격자를 만든다."""
    if events.empty:
        start, end = pd.Timestamp.today().to_period("M").to_timestamp(), pd.Timestamp.today().to_period("M").to_timestamp()
    else:
        start = events["rcept_dt"].min().to_period("M").to_timestamp()
        end = events["rcept_dt"].max().to_period("M").to_timestamp()
    periods = pd.date_range(start, end, freq="MS")
    grid = pd.MultiIndex.from_product([tickers, periods], names=["ticker", "period"]).to_frame(index=False)
    return grid


def build_monthly_panel(events: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    grid = _month_range(events, tickers)
    if events.empty:
        for col in [f"{t}_count" for t in EVENT_TYPES] + ["total_count"]:
            grid[col] = 0
        return grid

    work = events.copy()
    work["period"] = work["rcept_dt"].dt.to_period("M").dt.to_timestamp()
    work = work[work["event_type"].isin(EVENT_TYPES)]

    counts = (
        work.groupby(["ticker", "period", "event_type"]).size().unstack(fill_value=0).reset_index()
    )
    for event_type in EVENT_TYPES:
        if event_type not in counts.columns:
            counts[event_type] = 0
    counts = counts.rename(columns={t: f"{t}_count" for t in EVENT_TYPES})

    monthly = grid.merge(counts, on=["ticker", "period"], how="left")
    for event_type in EVENT_TYPES:
        monthly[f"{event_type}_count"] = monthly[f"{event_type}_count"].fillna(0).astype(int)
    monthly["total_count"] = monthly[[f"{t}_count" for t in EVENT_TYPES]].sum(axis=1)
    return monthly.sort_values(["ticker", "period"])


def add_event_factors(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.sort_values(["ticker", "period"]).copy()

    for event_type in EVENT_TYPES:
        count_col = f"{event_type}_count"
        out[f"{event_type}_event_flag"] = (out[count_col] > 0)

        roll_sum = out.groupby("ticker")[count_col].transform(
            lambda s: s.rolling(RECENT_WINDOW, min_periods=1).sum()
        )
        out[f"{event_type}_count_{RECENT_WINDOW}m"] = roll_sum.astype(int)

        grp = out.groupby("ticker")[count_col]
        roll_mean = grp.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=4).mean())
        roll_std = grp.transform(lambda s: s.rolling(OWN_HISTORY_WINDOW, min_periods=4).std())
        zscore_col = f"{event_type}_count_zscore_own_{OWN_HISTORY_WINDOW}m"
        out[zscore_col] = (out[count_col] - roll_mean) / roll_std
        out.loc[roll_std == 0, zscore_col] = np.nan

    return out


def add_event_score(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()

    buyback_signal = out["buyback_event_flag"].astype(float)
    dividend_signal = out["dividend_event_flag"].astype(float)
    insider_zscore_col = f"insider_count_zscore_own_{OWN_HISTORY_WINDOW}m"
    insider_signal = (out[insider_zscore_col].clip(-2, 2) + 2) / 4

    score_inputs = pd.concat([buyback_signal, dividend_signal, insider_signal], axis=1)
    out["event_activity_score"] = score_inputs.mean(axis=1, skipna=True)
    out.loc[score_inputs.isna().all(axis=1), "event_activity_score"] = np.nan

    conditions = [
        out["event_activity_score"] >= 0.7,
        out["event_activity_score"] >= 0.5,
        out["event_activity_score"] <= 0.15,
    ]
    choices = ["high_activity", "elevated_activity", "quiet"]
    out["event_activity_bucket"] = np.select(conditions, choices, default="normal")
    out.loc[out["event_activity_score"].isna(), "event_activity_bucket"] = "N/A"

    return out


def build_factor_catalog() -> pd.DataFrame:
    rows = [
        ("dart_event_signal", "이번 달 자사주 매입/처분 또는 배당 결정 공시가 있었는가?",
         "buyback_event_flag / dividend_event_flag", "DART 공시 report_nm 분류",
         "해당 월에 자사주·배당 관련 공시가 1건이라도 있으면 True (자사주 매입은 통상 주가 하방 지지 시그널로 해석)", "핵심"),
        ("dart_event_signal", f"최근 {RECENT_WINDOW}개월 누적으로 보면 이벤트가 얼마나 있었나?",
         f"buyback_count_{RECENT_WINDOW}m / dividend_count_{RECENT_WINDOW}m / insider_count_{RECENT_WINDOW}m",
         "월별 이벤트 건수의 trailing 합", f"최근 {RECENT_WINDOW}개월 누적 이벤트 건수 (단발성 vs 지속성 구분에 사용)", "필터"),
        ("dart_event_signal", "임원·주요주주 지분변동 신고 빈도가 평소보다 활발한가?",
         f"insider_count / insider_count_zscore_own_{OWN_HISTORY_WINDOW}m", "임원ㆍ주요주주 소유상황보고 등 신고 건수",
         (f"자기 과거 {OWN_HISTORY_WINDOW}개월 평균 대비 z-score. "
          "주의: 이 신고는 매수/매도 방향을 구분하지 않으므로 '내부자 매수'가 아니라 "
          "'신고 활동의 활발함'으로만 해석한다"), "필터"),
        ("dart_event_signal", "종합적으로 이 종목의 공시 이벤트 활동이 활발한 편인가?",
         "event_activity_score / event_activity_bucket", "자사주·배당 발생 여부 + 내부자 신고 이례성 합성",
         "0~1 합성 점수와 quiet~high_activity 4단계 버킷", "핵심"),
    ]
    return pd.DataFrame(
        rows,
        columns=["factor_family", "question", "factor_name", "source_column", "interpretation", "preferred_use"],
    )


def build_outputs(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = load_event_panel(tickers)
    monthly = build_monthly_panel(events, tickers)
    monthly = add_event_factors(monthly)
    monthly = add_event_score(monthly)
    catalog = build_factor_catalog()
    return monthly, catalog


def save_outputs(monthly: pd.DataFrame, catalog: pd.DataFrame, conn: sqlite3.Connection) -> dict[str, int | str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUTPUT_DIR / "dart_event_signal_month.csv"
    catalog_path = OUTPUT_DIR / "dart_event_signal_factor_catalog.csv"

    monthly_save = monthly.copy()
    monthly_save["period"] = pd.to_datetime(monthly_save["period"]).dt.strftime("%Y-%m-%d")
    for event_type in EVENT_TYPES:
        monthly_save[f"{event_type}_event_flag"] = monthly_save[f"{event_type}_event_flag"].astype(bool)

    monthly_save.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    monthly_save.to_sql("factor_dart_event_signal_month", conn, if_exists="replace", index=False)
    catalog.to_sql("factor_dart_event_signal_catalog", conn, if_exists="replace", index=False)

    return {
        "monthly_path": str(monthly_path),
        "catalog_path": str(catalog_path),
        "monthly_rows": len(monthly_save),
        "tickers": int(monthly_save["ticker"].nunique()),
        "period_min": monthly_save["period"].min(),
        "period_max": monthly_save["period"].max(),
        "catalog_rows": len(catalog),
    }


def main() -> None:
    tickers = discover_tickers()
    with sqlite3.connect(DB_PATH) as conn:
        monthly, catalog = build_outputs(tickers)
        result = save_outputs(monthly, catalog, conn)
    print(result)


if __name__ == "__main__":
    main()

"""
한미 무역수지 / 수출입 팩터 구축 (월간 시계열).

원천: macro_trade_us_korea_monthly (long format, series_id별 월별 값)
  - XTEXVA01KRM667S : 한국 총수출 (USD, 1957~)
  - XTIMVA01KRM667S : 한국 총수입 (USD, 1957~)
  - EXPKR           : 미국→한국 수출 (FAS, Millions of USD, 1985~)
  - IMPKR           : 미국→한국 수입(=한국→미국 수출, Customs, Millions of USD, 1985~)

신호:
  ① korea_trade_balance     : 한국 총수출 - 총수입
  ② us_korea_trade_balance  : 미국의 대한 무역수지 (EXPKR-IMPKR, 통상 적자=음수)
  ③ korea_exports_yoy       : 한국 총수출 전년동월비
  ④ korea_exports_yoy_chg3m : ③의 3개월 변화 (가속/감속)
  ⑤ korea_exports_yoy_z12m  : ③의 12M z-score

export_momentum_score = 0~1, 높을수록 수출 모멘텀 호조 (yoy z-score 상승)
export_cycle_regime   = (yoy 부호 x 3M 변화 부호) 2x2 분면
  - expansion : yoy>=0 & 가속(chg3m>=0)  → 수출 호황 지속/확대
  - slowdown  : yoy>=0 & 감속(chg3m<0)   → 호황 둔화 (경계)
  - recovery  : yoy<0  & 가속(chg3m>=0)  → 부진에서 회복 중
  - contraction: yoy<0 & 감속(chg3m<0)   → 수출 부진 심화

해석: 한국 수출 사이클은 코스피 이익 사이클과 강한 동행성을 가지며,
       ⑨(외국인 수급)·⑲(실적모멘텀)와 결합 시 경기민감/수출주 비중 조절에 활용.

출력 DB 테이블:
  factor_trade_balance_kr_us_month   : 월간 시계열
  factor_trade_balance_kr_us_catalog : 팩터 메타데이터
"""
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "database" / "quant_data.sqlite"

ZSCORE_WINDOW = 12     # YoY 시계열 기준 12M rolling window
MIN_ZSCORE_OBS = 6

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_series(conn: sqlite3.Connection, series_id: str, new_name: str) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT date, value FROM macro_trade_us_korea_monthly WHERE series_id = ?",
        conn, params=(series_id,),
    )
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna().sort_values("date")
    df["period"] = df["date"].dt.to_period("M").dt.to_timestamp()
    out = df.groupby("period")["value"].last()
    out.name = new_name
    return out.reset_index()


def _load_ecos_trade(conn: sqlite3.Connection, series: str, new_name: str) -> pd.DataFrame:
    """macro_trade_kr_kosis_monthly (ECOS 1개월 lag) 로드."""
    try:
        df = pd.read_sql(
            "SELECT period, value FROM macro_trade_kr_kosis_monthly WHERE series = ?",
            conn, params=(series,),
        )
        if df.empty:
            return pd.DataFrame()
        df["period"] = pd.to_datetime(df["period"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().sort_values("period")
        # 단위 변환: ECOS는 천불(천 USD) → FRED 단위(USD)로 환산
        df["value"] = df["value"] * 1000
        out = df.groupby("period")["value"].last()
        out.name = new_name
        return out.reset_index()
    except Exception:
        return pd.DataFrame()


def _load_kr_exports(conn: sqlite3.Connection) -> pd.DataFrame:
    """한국 수출: ECOS primary (1개월 lag) → FRED fallback (2개월 lag)."""
    df = _load_ecos_trade(conn, "korea_exports_total", "korea_exports")
    if not df.empty:
        logger.info("  한국 수출: ECOS 사용 (max=%s)", df["period"].max())
        return df
    logger.warning("  한국 수출: ECOS 없음, FRED fallback")
    return _load_series(conn, "XTEXVA01KRM667S", "korea_exports")


def _load_kr_imports(conn: sqlite3.Connection) -> pd.DataFrame:
    """한국 수입: ECOS primary (1개월 lag) → FRED fallback (2개월 lag)."""
    df = _load_ecos_trade(conn, "korea_imports_total", "korea_imports")
    if not df.empty:
        logger.info("  한국 수입: ECOS 사용 (max=%s)", df["period"].max())
        return df
    logger.warning("  한국 수입: ECOS 없음, FRED fallback")
    return _load_series(conn, "XTIMVA01KRM667S", "korea_imports")


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=MIN_ZSCORE_OBS).mean()
    std = series.rolling(window, min_periods=MIN_ZSCORE_OBS).std()
    return (series - mean) / std.replace(0, np.nan)


def _score_from_zscore(z: pd.Series) -> pd.Series:
    """z-score → 0~1 점수. clip(-3,3)/6 + 0.5"""
    return (z.clip(-3, 3) / 6 + 0.5).clip(0, 1)


def _export_cycle_regime(yoy: float, chg3m: float) -> str:
    if pd.isna(yoy) or pd.isna(chg3m):
        return "unknown"
    if yoy >= 0:
        return "expansion" if chg3m >= 0 else "slowdown"
    return "recovery" if chg3m >= 0 else "contraction"


def build(conn: sqlite3.Connection) -> pd.DataFrame:
    # ── 원천 데이터 로드 ──────────────────────────────────────────────
    # 한국 수출입: ECOS primary (1개월 lag) → FRED OECD fallback (2개월 lag)
    kr_exp = _load_kr_exports(conn)
    kr_imp = _load_kr_imports(conn)
    # 한미 양자 무역: FRED Census (EXPKR/IMPKR) 유일 소스
    us_exp = _load_series(conn, "EXPKR", "us_exports_to_korea")
    us_imp = _load_series(conn, "IMPKR", "us_imports_from_korea")

    # ── 병합 ─────────────────────────────────────────────────────
    base = (kr_exp.merge(kr_imp, on="period", how="outer")
                  .merge(us_exp, on="period", how="outer")
                  .merge(us_imp, on="period", how="outer")
                  .sort_values("period")
                  .reset_index(drop=True))

    # ── 무역수지 ─────────────────────────────────────────────────
    base["korea_trade_balance"] = base["korea_exports"] - base["korea_imports"]
    base["us_korea_trade_balance"] = base["us_exports_to_korea"] - base["us_imports_from_korea"]

    # ── 한국 수출 전년동월비 (YoY) ───────────────────────────────
    base["korea_exports_yoy"] = base["korea_exports"].pct_change(12, fill_method=None)
    base["korea_imports_yoy"] = base["korea_imports"].pct_change(12, fill_method=None)

    # ── YoY 가속/감속 (3개월 변화) ───────────────────────────────
    base["korea_exports_yoy_chg3m"] = base["korea_exports_yoy"].diff(3)

    # ── YoY 12M z-score ──────────────────────────────────────────
    base["korea_exports_yoy_z12m"] = _zscore(base["korea_exports_yoy"], ZSCORE_WINDOW)

    # ── 수출 모멘텀 점수 (0~1, 높을수록 수출 호조) ──────────────────
    base["export_momentum_score"] = _score_from_zscore(base["korea_exports_yoy_z12m"])

    # KOSIS 2개월 lag로 최근 기간 미수록 → fx/soxx proxy로 행 확장
    # proxy = 0.5*(1-won_strength_score) + 0.5*semi_momentum_score
    # 원화 약세(won_strength 낮음) + 반도체 모멘텀 강세 = 수출 호조 선행
    try:
        proxy_scores = []
        for tbl, col, invert in [
            ("factor_fx_usdkrw_month", "won_strength_score", True),
            ("factor_soxx_semicycle_month", "semi_momentum_score", False),
        ]:
            px = pd.read_sql(f"SELECT period, [{col}] AS v FROM [{tbl}]", conn)
            px["period"] = pd.to_datetime(px["period"])
            px = px.set_index("period")["v"]
            if invert:
                px = 1.0 - px
            proxy_scores.append(px)
        if proxy_scores:
            proxy_combined = pd.concat(proxy_scores, axis=1).mean(axis=1)
            kosis_max = base["period"].max()
            proxy_new = proxy_combined[proxy_combined.index > kosis_max]
            if not proxy_new.empty:
                new_rows = pd.DataFrame({
                    "period": proxy_new.index,
                    "export_momentum_score": proxy_new.values,
                })
                base = pd.concat([base, new_rows], ignore_index=True).sort_values("period").reset_index(drop=True)
                logger.info("  export_momentum_score proxy rows 추가: %d행 (max=%s)",
                            len(proxy_new), proxy_new.index.max().strftime("%Y-%m-%d"))
    except Exception as e:
        logger.warning("  export proxy 확장 실패 (무시): %s", e)

    # ── 수출 사이클 레짐 (2x2 분면) ──────────────────────────────
    base["export_cycle_regime"] = base.apply(
        lambda r: _export_cycle_regime(r["korea_exports_yoy"], r["korea_exports_yoy_chg3m"]),
        axis=1,
    )

    base["period"] = base["period"].dt.strftime("%Y-%m-01")

    cols = [
        "period",
        "korea_exports", "korea_imports", "us_exports_to_korea", "us_imports_from_korea",
        "korea_trade_balance", "us_korea_trade_balance",
        "korea_exports_yoy", "korea_imports_yoy", "korea_exports_yoy_chg3m",
        "korea_exports_yoy_z12m", "export_momentum_score", "export_cycle_regime",
    ]
    return base[[c for c in cols if c in base.columns]]


CATALOG = [
    ("korea_exports",            "한국 총수출(통관기준)",            "USD, 월별",                         "monthly"),
    ("korea_imports",            "한국 총수입(통관기준)",            "USD, 월별",                         "monthly"),
    ("us_exports_to_korea",      "미국→한국 수출(FAS)",             "Millions of USD, 월별",             "monthly"),
    ("us_imports_from_korea",    "미국→한국 수입(Customs)",         "Millions of USD, 월별",             "monthly"),
    ("korea_trade_balance",      "한국 무역수지(수출-수입)",          "USD, 양수=무역흑자",                 "monthly"),
    ("us_korea_trade_balance",   "미국의 대한 무역수지",             "Millions of USD, 통상 음수(美 적자)", "monthly"),
    ("korea_exports_yoy",        "한국 수출 전년동월비",             "비율",                              "monthly"),
    ("korea_imports_yoy",        "한국 수입 전년동월비",             "비율",                              "monthly"),
    ("korea_exports_yoy_chg3m",  "수출 YoY의 3개월 변화(가속/감속)",  "%p, 양수=가속",                      "monthly"),
    ("korea_exports_yoy_z12m",   "수출 YoY 12M z-score",            "z-score",                           "monthly"),
    ("export_momentum_score",    "수출 모멘텀 점수",                 "0~1, 높을수록 수출 호조",             "monthly"),
    ("export_cycle_regime",      "수출 사이클 레짐",                 "expansion/slowdown/recovery/contraction", "monthly"),
]


def run():
    logger.info("trade_balance_kr_us 팩터 구축 시작")
    with sqlite3.connect(DB_PATH) as conn:
        df = build(conn)
        df.to_sql("factor_trade_balance_kr_us_month", conn, if_exists="replace", index=False)
        logger.info("  → factor_trade_balance_kr_us_month 적재: %d행", len(df))

        catalog = pd.DataFrame(CATALOG,
                               columns=["factor_name", "description_kr", "range", "period_type"])
        catalog.to_sql("factor_trade_balance_kr_us_catalog", conn, if_exists="replace", index=False)
        logger.info("  → factor_trade_balance_kr_us_catalog 적재: %d행", len(catalog))

    logger.info("완료")
    return df


if __name__ == "__main__":
    df = run()
    print(df.tail(12)[["period", "korea_exports_yoy", "korea_exports_yoy_z12m",
                        "export_momentum_score", "export_cycle_regime"]].to_string())

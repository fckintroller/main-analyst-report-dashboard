"""
회귀 분석 3종 세트:
  시나리오 2 - KOSPI 시장 타이밍 (OLS + Ridge, 매크로 팩터)
  시나리오 1 - 종목 패널 알파 (Fama-MacBeth, 종목 팩터)
  시나리오 3 - 레짐 인터랙션 (레짐별 팩터 유효성 검증)

결과를 SQLite regression_* 테이블에 저장한다.
"""

import logging
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parents[2] / "data" / "database" / "quant_data.sqlite"
KOSPI_CSV = Path(__file__).parents[2] / "data" / "raw" / "macro" / "global_indices" / "yahoo_korea_kospi_daily.csv"


# ── 공통 유틸 ──────────────────────────────────────────────────────────────

def _winsorize(s: pd.Series, lo=0.01, hi=0.99) -> pd.Series:
    lb, ub = s.quantile(lo), s.quantile(hi)
    return s.clip(lb, ub)


def _zscore_cross(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """횡단면(행 방향) z-score 정규화."""
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = _winsorize(out[c])
            mu, sd = out[c].mean(), out[c].std()
            if sd > 1e-9:
                out[c] = (out[c] - mu) / sd
    return out


def _newey_west_t(series: pd.Series, lags: int = 3) -> float:
    """Newey-West 보정 t-stat (시계열 t-test)."""
    n = len(series.dropna())
    if n < 4:
        return float("nan")
    from statsmodels.stats.sandwich_covariance import cov_hac
    import statsmodels.api as sm
    y = series.dropna().values
    X = np.ones((len(y), 1))
    model = sm.OLS(y, X).fit()
    try:
        nw_cov = cov_hac(model, nlags=lags)
        se = np.sqrt(nw_cov[0, 0])
        return float(model.params[0] / se) if se > 1e-12 else float("nan")
    except Exception:
        return float(stats.ttest_1samp(y, 0).statistic)


# ── KOSPI 월간 수익률 로드 ──────────────────────────────────────────────────

def _load_kospi_monthly() -> pd.Series:
    """yahoo_korea_kospi_daily.csv → 월말 수익률 시리즈."""
    df = pd.read_csv(KOSPI_CSV, parse_dates=["date"])
    df = df.set_index("date")["close"].sort_index()
    monthly = df.resample("MS").last()          # 월 첫날 기준 (period=YYYY-MM-01)
    ret = monthly.pct_change().dropna()
    ret.index = ret.index.strftime("%Y-%m-01")
    return ret.rename("kospi_ret_1m")


# ── 시나리오 2: 시장 타이밍 회귀 ──────────────────────────────────────────

MACRO_FACTOR_SPECS = [
    # (table, column, label_kr, 방향설명)
    ("factor_macro_spread_month",        "macro_risk_score",        "매크로 리스크온",   "높을수록 위험선호"),
    ("factor_credit_spread_kr_month",    "credit_score",            "국내 신용환경",     "높을수록 신용 우호"),
    ("factor_fx_usdkrw_month",           "won_strength_score",      "원화 강세",         "높을수록 원화 강세"),
    ("factor_trade_balance_kr_us_month", "export_momentum_score",   "수출 모멘텀",       "높을수록 수출 호조"),
    ("factor_ppi_inflation_cycle_kr_month","inflation_momentum_score","인플레이션 압력", "높을수록 PPI 가속"),
    ("factor_commodity_momentum_month",  "commodity_cycle_score",   "원자재 수요",       "높을수록 원자재 강세"),
    ("factor_yield_curve_kr_month",      "yield_slope_pctile_3y",   "국채 수익률곡선",   "높을수록 커브 정상(스팁)"),
    ("factor_market_macro_regime_month", "vix_zscore_252d",         "VIX 충격(반전)",   "높을수록 공포(역방향 기대)"),
    ("factor_soxx_semicycle_month",      "semi_momentum_score",     "반도체 사이클",     "높을수록 SOXX 강세"),
]


def _load_macro_panel(conn) -> pd.DataFrame:
    """매크로 팩터들을 period 기준 wide 형태로 병합."""
    base = None
    for table, col, label, _ in MACRO_FACTOR_SPECS:
        try:
            df = pd.read_sql(f'SELECT period, "{col}" FROM "{table}"', conn)
            df["period"] = df["period"].astype(str)
            df = df.rename(columns={col: col})
            if base is None:
                base = df.set_index("period")
            else:
                base = base.join(df.set_index("period"), how="outer")
        except Exception as e:
            logger.warning("매크로 팩터 로드 실패 %s.%s: %s", table, col, e)
    return base.sort_index() if base is not None else pd.DataFrame()


def _build_market_timing(conn) -> dict:
    """시나리오 2: KOSPI 1개월 선행 수익률 예측 OLS + Ridge."""
    logger.info("[시나리오 2] 시장 타이밍 회귀 시작")

    kospi_ret = _load_kospi_monthly()
    macro_df = _load_macro_panel(conn)
    if macro_df.empty:
        logger.warning("매크로 패널 비어있음")
        return {}

    # Y: 다음 달 KOSPI 수익률 (1기간 선행)
    # X: 현재 달 매크로 팩터 (lag=1이 자동으로 적용됨: X(t) → Y(t+1))
    y_ser = kospi_ret.shift(-1)   # X의 period t에 대응하는 Y는 t+1
    panel = macro_df.copy()
    panel["kospi_ret_fwd_1m"] = y_ser

    # NaN이 많은 열부터 VIF 순으로 선택 (SOXX 있는 구간 vs 없는 구간 둘 다)
    factor_cols = [s[1] for s in MACRO_FACTOR_SPECS]
    panel = panel.dropna(subset=["kospi_ret_fwd_1m"])

    results_by_model = {}

    for model_name, drop_cols in [
        ("full",  []),                          # SOXX 포함 (2016~)
        ("base",  ["semi_momentum_score"]),     # SOXX 제외 (2010~)
    ]:
        use_cols = [c for c in factor_cols if c not in drop_cols]
        sub = panel[use_cols + ["kospi_ret_fwd_1m"]].dropna()

        if len(sub) < 30:
            logger.warning("[%s] 샘플 부족(%d)", model_name, len(sub))
            continue

        X = sub[use_cols].values
        y = sub["kospi_ret_fwd_1m"].values
        scaler = StandardScaler()
        X_sc = scaler.fit_transform(X)

        # OLS
        from statsmodels.api import OLS, add_constant
        res = OLS(y, add_constant(X_sc)).fit(cov_type="HC3")
        coefs = res.params[1:]     # intercept 제외
        tvals = res.tvalues[1:]
        pvals = res.pvalues[1:]

        # Ridge
        ridge = RidgeCV(alphas=np.logspace(-3, 3, 30), cv=5)
        ridge.fit(X_sc, y)

        # 현재(마지막) 시점 예측
        latest_period = macro_df.dropna(subset=use_cols).index.max()
        X_now = macro_df.loc[[latest_period], use_cols].values
        X_now_sc = scaler.transform(X_now)
        ols_pred = float(res.predict(np.hstack([[1], X_now_sc[0]]))[0])
        ridge_pred = float(ridge.predict(X_now_sc)[0])
        pred = (ols_pred + ridge_pred) / 2.0

        # 시그널 분류
        signal_threshold = sub["kospi_ret_fwd_1m"].std() * 0.4
        signal = "bullish" if pred > signal_threshold else ("bearish" if pred < -signal_threshold else "neutral")

        factor_results = []
        for i, col in enumerate(use_cols):
            spec = next((s for s in MACRO_FACTOR_SPECS if s[1] == col), None)
            label = spec[2] if spec else col
            factor_results.append({
                "key":         col,
                "label":       label,
                "coef_ols":    round(float(coefs[i]), 4),
                "t_stat":      round(float(tvals[i]), 3),
                "p_value":     round(float(pvals[i]), 4),
                "significant": bool(abs(tvals[i]) > 1.65),
                "coef_ridge":  round(float(ridge.coef_[i]), 4),
                "current_val": round(float(X_now[0, i]) if not np.isnan(X_now[0, i]) else 0.0, 4),
            })

        results_by_model[model_name] = {
            "periods":      int(len(sub)),
            "start_period": str(sub.index.min()),
            "end_period":   str(sub.index.max()),
            "pred_period":  str(latest_period),
            "ols_pred_pct": round(ols_pred * 100, 2),
            "ridge_pred_pct": round(ridge_pred * 100, 2),
            "pred_pct":     round(pred * 100, 2),
            "signal":       signal,
            "r2":           round(float(res.rsquared), 4),
            "adj_r2":       round(float(res.rsquared_adj), 4),
            "factors":      factor_results,
        }
        logger.info("[시나리오 2/%s] 기간=%d, pred=%.2f%%, signal=%s, R²=%.3f",
                    model_name, len(sub), pred * 100, signal, res.rsquared)

    return results_by_model


# ── 시나리오 1: 종목 패널 Fama-MacBeth ──────────────────────────────────

STOCK_FACTOR_SPECS = [
    # (table, column, label, 방향)
    ("factor_valuation_per_pbr_month",  "valuation_score",         "밸류에이션",    "높을수록 저평가"),
    ("factor_stock_price_momentum_month","momentum_score",          "가격 모멘텀",   "높을수록 모멘텀 강"),
    ("factor_size_month",               "size_percentile_cross",   "시가총액",      "높을수록 대형주"),
    ("factor_liquidity_turnover_month", "liquidity_score",         "유동성",        "높을수록 거래 활발"),
    ("factor_roe_trend_month",          "roe_sector_pct_ts",       "ROE 추세",      "높을수록 ROE 우수"),
    ("factor_investor_flow_momentum_month","flow_score",            "외인/기관 수급","높을수록 순매수"),
]


def _load_stock_panel(conn) -> pd.DataFrame:
    """종목 팩터 월간 시계열 + 1개월 후 수익률 결합."""
    ret_df = pd.read_sql(
        'SELECT ticker, period, ret_1m FROM factor_stock_price_momentum_month', conn
    )
    ret_df["period"] = ret_df["period"].astype(str)

    frames = []
    for table, col, label, _ in STOCK_FACTOR_SPECS:
        try:
            df = pd.read_sql(f'SELECT ticker, period, "{col}" FROM "{table}"', conn)
            df["period"] = df["period"].astype(str)
            frames.append(df.rename(columns={col: col}))
        except Exception as e:
            logger.warning("종목 팩터 로드 실패 %s.%s: %s", table, col, e)

    # 병합
    panel = ret_df.copy()
    for df in frames:
        panel = panel.merge(df, on=["ticker", "period"], how="left")

    panel = panel.sort_values(["ticker", "period"]).reset_index(drop=True)

    # Y = 다음 달 수익률 (ticker 그룹별 shift)
    panel["ret_fwd_1m"] = panel.groupby("ticker")["ret_1m"].shift(-1)

    return panel


def _build_fama_macbeth(conn) -> dict:
    """시나리오 1: Fama-MacBeth 횡단면 회귀."""
    logger.info("[시나리오 1] Fama-MacBeth 패널 회귀 시작")

    panel = _load_stock_panel(conn)
    factor_cols = [s[1] for s in STOCK_FACTOR_SPECS]

    periods = sorted(panel["period"].unique())
    # 마지막 period는 Y가 없으므로 제외
    periods = periods[:-1]

    monthly_betas = {c: [] for c in factor_cols}
    monthly_ic = {c: [] for c in factor_cols}

    for p in periods:
        sub = panel[panel["period"] == p].copy()
        sub = sub.dropna(subset=factor_cols + ["ret_fwd_1m"])
        if len(sub) < 30:
            continue

        sub_z = _zscore_cross(sub, factor_cols)

        # OLS 횡단면
        from statsmodels.api import OLS, add_constant
        X = add_constant(sub_z[factor_cols].values)
        y = sub_z["ret_fwd_1m"].values
        try:
            res = OLS(y, X).fit()
            for i, col in enumerate(factor_cols):
                monthly_betas[col].append(res.params[i + 1])
        except Exception:
            pass

        # IC (Spearman)
        for col in factor_cols:
            if sub_z[col].notna().sum() > 5:
                ic, _ = stats.spearmanr(sub_z[col], sub_z["ret_fwd_1m"])
                if not np.isnan(ic):
                    monthly_ic[col].append(ic)

    factor_results = []
    for col in factor_cols:
        spec = next(s for s in STOCK_FACTOR_SPECS if s[1] == col)
        betas = pd.Series(monthly_betas[col])
        ics = pd.Series(monthly_ic[col])
        t_beta = _newey_west_t(betas) if len(betas) >= 4 else float("nan")
        t_ic = _newey_west_t(ics) if len(ics) >= 4 else float("nan")
        factor_results.append({
            "key":          col,
            "label":        spec[2],
            "direction":    spec[3],
            "n_periods":    int(len(betas)),
            "beta_mean":    round(float(betas.mean()), 5) if len(betas) else None,
            "beta_t":       round(float(t_beta), 3) if not np.isnan(t_beta) else None,
            "ic_mean":      round(float(ics.mean()), 4) if len(ics) else None,
            "ic_t":         round(float(t_ic), 3) if not np.isnan(t_ic) else None,
            "ic_ir":        round(float(ics.mean() / ics.std()), 3) if len(ics) > 1 and ics.std() > 0 else None,
            "significant":  bool(abs(t_ic) > 1.65) if not np.isnan(t_ic) else False,
        })
        logger.info("[FM] %s: IC=%.4f t=%.2f n=%d", col,
                    float(ics.mean()) if len(ics) else 0, float(t_ic) if not np.isnan(t_ic) else 0, len(ics))

    return {
        "periods":       len(periods),
        "stock_count":   int(panel["ticker"].nunique()),
        "start_period":  str(periods[0]) if periods else "",
        "end_period":    str(periods[-1]) if periods else "",
        "factors":       factor_results,
    }


# ── 시나리오 3: 레짐 인터랙션 ────────────────────────────────────────────

def _build_regime_interaction(conn, panel: pd.DataFrame) -> dict:
    """시나리오 3: 레짐 더미 × 팩터 인터랙션 회귀."""
    logger.info("[시나리오 3] 레짐 인터랙션 분석 시작")

    regime_df = pd.read_sql(
        'SELECT period, market_regime, risk_on_flag, risk_off_flag FROM factor_market_macro_regime_month',
        conn
    )
    regime_df["period"] = regime_df["period"].astype(str)

    panel_r = panel.merge(regime_df, on="period", how="left")

    factor_cols = [s[1] for s in STOCK_FACTOR_SPECS]
    regimes = ["risk_on", "risk_off", "other"]

    results = {r: {} for r in regimes}

    for regime in regimes:
        if regime == "risk_on":
            sub = panel_r[panel_r["risk_on_flag"] == 1].copy()
        elif regime == "risk_off":
            sub = panel_r[panel_r["risk_off_flag"] == 1].copy()
        else:
            sub = panel_r[(panel_r["risk_on_flag"] != 1) & (panel_r["risk_off_flag"] != 1)].copy()

        sub = sub.dropna(subset=factor_cols + ["ret_fwd_1m"])
        if len(sub) < 20:
            results[regime] = {"n": 0, "factors": []}
            continue

        monthly_ic = {c: [] for c in factor_cols}
        for p in sorted(sub["period"].unique()):
            period_sub = sub[sub["period"] == p].dropna(subset=factor_cols + ["ret_fwd_1m"])
            if len(period_sub) < 10:
                continue
            for col in factor_cols:
                ic, _ = stats.spearmanr(period_sub[col], period_sub["ret_fwd_1m"])
                if not np.isnan(ic):
                    monthly_ic[col].append(ic)

        regime_factors = []
        for col in factor_cols:
            spec = next(s for s in STOCK_FACTOR_SPECS if s[1] == col)
            ics = pd.Series(monthly_ic[col])
            t_ic = _newey_west_t(ics) if len(ics) >= 4 else float("nan")
            regime_factors.append({
                "key":    col,
                "label":  spec[2],
                "ic":     round(float(ics.mean()), 4) if len(ics) else None,
                "t_stat": round(float(t_ic), 3) if not np.isnan(t_ic) else None,
                "sig":    bool(abs(t_ic) > 1.65) if not np.isnan(t_ic) else False,
                "n_months": int(len(ics)),
            })
        results[regime] = {
            "n": int(len(sub["period"].unique())),
            "factors": regime_factors,
        }
        logger.info("[레짐 %s] 기간수=%d", regime, int(len(sub["period"].unique())))

    # 현재 레짐 판별
    latest = regime_df.sort_values("period").iloc[-1]
    cur_regime = str(latest.get("market_regime", "unknown"))
    if latest.get("risk_on_flag") == 1:
        cur_bucket = "risk_on"
    elif latest.get("risk_off_flag") == 1:
        cur_bucket = "risk_off"
    else:
        cur_bucket = "other"

    return {
        "current_regime":   cur_regime,
        "current_bucket":   cur_bucket,
        "current_period":   str(latest["period"]),
        "regimes":          results,
    }


# ── 종목별 레짐 조정 점수 계산 ────────────────────────────────────────────

def _compute_regime_adj_stock_scores(panel: pd.DataFrame, fmb_result: dict, regime_result: dict) -> pd.DataFrame:
    """현재 레짐에서 유효한 팩터를 강조한 종목별 점수."""
    cur_bucket = regime_result.get("current_bucket", "other")
    regime_factors = regime_result.get("regimes", {}).get(cur_bucket, {}).get("factors", [])

    # 팩터별 가중치: significant → IC 절대값, else → 0.2 (기본)
    weights = {}
    for f in regime_factors:
        key = f.get("key")
        ic = f.get("ic") or 0
        sig = f.get("sig", False)
        weights[key] = abs(ic) if sig else 0.1

    total_w = sum(weights.values()) or 1.0
    norm_w = {k: v / total_w for k, v in weights.items()}

    factor_cols = [s[1] for s in STOCK_FACTOR_SPECS]

    # 최신 period 종목 팩터
    latest_period = panel["period"].max()
    latest = panel[panel["period"] == latest_period].copy()
    latest_z = _zscore_cross(latest, factor_cols)

    # 0~1 변환 (rank percentile per factor)
    for col in factor_cols:
        if col in latest_z.columns:
            latest_z[f"{col}_pct"] = latest_z[col].rank(pct=True)

    def _regime_score(row):
        score = 0.0
        for col, w in norm_w.items():
            pct_col = f"{col}_pct"
            val = row.get(pct_col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                score += float(val) * w
        return round(score, 4)

    latest_z["regime_adj_score"] = latest_z.apply(_regime_score, axis=1)
    return latest_z[["ticker", "regime_adj_score"]].dropna()


# ── DB 저장 ────────────────────────────────────────────────────────────────

def _save_to_db(conn, market_timing: dict, fmb: dict, regime: dict, regime_scores: pd.DataFrame):
    cur = conn.cursor()

    # 1. regression_market_timing
    cur.execute("DROP TABLE IF EXISTS regression_market_timing")
    rows = []
    for model_name, res in market_timing.items():
        for f in res.get("factors", []):
            rows.append({
                "model":        model_name,
                "key":          f["key"],
                "label":        f["label"],
                "coef_ols":     f["coef_ols"],
                "t_stat":       f["t_stat"],
                "p_value":      f["p_value"],
                "significant":  int(f["significant"]),
                "coef_ridge":   f["coef_ridge"],
                "current_val":  f["current_val"],
                "signal":       res["signal"],
                "pred_pct":     res["pred_pct"],
                "r2":           res["r2"],
                "periods":      res["periods"],
                "pred_period":  res["pred_period"],
            })
    if rows:
        pd.DataFrame(rows).to_sql("regression_market_timing", conn, if_exists="replace", index=False)

    # 2. regression_factor_ic (Fama-MacBeth)
    cur.execute("DROP TABLE IF EXISTS regression_factor_ic")
    if fmb.get("factors"):
        pd.DataFrame(fmb["factors"]).to_sql("regression_factor_ic", conn, if_exists="replace", index=False)

    # 3. regression_regime_ic
    cur.execute("DROP TABLE IF EXISTS regression_regime_ic")
    rows = []
    for regime_name, r in regime.get("regimes", {}).items():
        for f in r.get("factors", []):
            rows.append({"regime": regime_name, **f})
    if rows:
        pd.DataFrame(rows).to_sql("regression_regime_ic", conn, if_exists="replace", index=False)

    # 4. regression_regime_adj_scores (종목별)
    cur.execute("DROP TABLE IF EXISTS regression_regime_adj_scores")
    if not regime_scores.empty:
        regime_scores.to_sql("regression_regime_adj_scores", conn, if_exists="replace", index=False)

    # 5. 메타 테이블
    cur.execute("DROP TABLE IF EXISTS regression_meta")
    cur.execute("""
        CREATE TABLE regression_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    import json
    meta = {
        "as_of":            market_timing.get("base", {}).get("pred_period", ""),
        "market_signal":    market_timing.get("base", {}).get("signal", ""),
        "market_pred_pct":  str(market_timing.get("base", {}).get("pred_pct", "")),
        "current_regime":   regime.get("current_regime", ""),
        "current_bucket":   regime.get("current_bucket", ""),
        "fm_periods":       str(fmb.get("periods", "")),
        "fm_stock_count":   str(fmb.get("stock_count", "")),
        "full_market_timing": json.dumps(market_timing, ensure_ascii=False),
        "full_fmb":           json.dumps(fmb, ensure_ascii=False),
        "full_regime":        json.dumps(regime, ensure_ascii=False),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO regression_meta (key, value) VALUES (?,?)", (k, str(v)))

    conn.commit()
    logger.info("DB 저장 완료: regression_market_timing / regression_factor_ic / regression_regime_ic / regression_regime_adj_scores / regression_meta")


# ── 진입점 ─────────────────────────────────────────────────────────────────

def main():
    if not DB_PATH.exists():
        logger.error("DB 없음: %s", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # 시나리오 2
        market_timing = _build_market_timing(conn)

        # 시나리오 1
        panel = _load_stock_panel(conn)
        fmb = _build_fama_macbeth(conn)

        # 시나리오 3
        regime = _build_regime_interaction(conn, panel)

        # 종목별 레짐 조정 점수
        regime_scores = _compute_regime_adj_stock_scores(panel, fmb, regime)

        # 저장
        _save_to_db(conn, market_timing, fmb, regime, regime_scores)

        logger.info("=== 전체 완료 ===")
        logger.info("시장 타이밍 signal (base): %s / pred=%.2f%%",
                    market_timing.get("base", {}).get("signal", "-"),
                    market_timing.get("base", {}).get("pred_pct", 0))
        logger.info("현재 레짐: %s (%s)", regime.get("current_regime"), regime.get("current_bucket"))
        logger.info("종목 레짐 조정 점수: %d종목", len(regime_scores))

    finally:
        conn.close()


if __name__ == "__main__":
    main()

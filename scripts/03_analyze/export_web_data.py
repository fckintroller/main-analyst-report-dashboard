import glob
import json
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _records_from_csv(file_path, **read_csv_kwargs):
    df = pd.read_csv(file_path, **read_csv_kwargs)
    df.fillna("", inplace=True)
    return df.to_dict(orient="records")


def _load_krx_names():
    try:
        import FinanceDataReader as fdr

        krx = fdr.StockListing("KRX")[["Code", "Name"]].set_index("Code")
        return krx["Name"].to_dict()
    except Exception as e:
        logger.warning("KRX 종목명 로드 실패, ticker만 사용: %s", e)
        return {}



def _safe_number(value):
    try:
        if value is None or value == "":
            return None
        num = float(str(value).replace(",", ""))
        if pd.isna(num):
            return None
        return num
    except Exception:
        return None


def _latest_table_rows(conn, table_name, ticker_col="ticker", date_col="period"):
    """테이블별 최신 행을 ticker 기준 1건으로 축약."""
    try:
        df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
    except Exception:
        return pd.DataFrame()
    if df.empty or ticker_col not in df.columns:
        return pd.DataFrame()
    if date_col in df.columns:
        df = df.sort_values([ticker_col, date_col])
    return df.groupby(ticker_col, as_index=False).tail(1)


def _parse_earnings_consensus_record(item):
    """네이버 컨센서스 raw JSON에서 최근/올해/내년 영업이익과 가치지표 추출."""
    try:
        raw = json.loads(item.get("consensus_raw") or "{}")
        cols = list(raw.keys())
        label_col = next((c for c in cols if "주요재무정보" in c), None)
        if not label_col:
            return {}

        def find_row(names):
            return next(
                (k for k in raw[label_col].keys()
                 if any(name in str(raw[label_col][k]) for name in names)),
                None,
            )

        op_row = find_row(["영업이익"])
        eps_row = find_row(["EPS"])
        per_row = find_row(["PER"])
        bps_row = find_row(["BPS"])
        pbr_row = find_row(["PBR"])
        if op_row is None:
            return {}

        year_cols = sorted([c for c in cols if "연간" in c])
        if len(year_cols) < 3:
            return {}
        last_year_col, this_year_col, next_year_col = year_cols[-3:]

        last_op = _safe_number(raw[last_year_col].get(op_row))
        this_op = _safe_number(raw[this_year_col].get(op_row))
        next_op = _safe_number(raw[next_year_col].get(op_row))

        def pct(curr, prev):
            if curr is None or prev in (None, 0):
                return None
            return round((curr - prev) / abs(prev) * 100, 2)

        return {
            "recent_op_profit": last_op,
            "this_year_op_profit_est": this_op,
            "next_year_op_profit_est": next_op,
            "this_year_op_growth_pct": pct(this_op, last_op),
            "next_year_op_growth_pct": pct(next_op, this_op),
            "consensus_last_year_col": last_year_col,
            "consensus_this_year_col": this_year_col,
            "consensus_next_year_col": next_year_col,
            "consensus_per": _safe_number(raw[last_year_col].get(per_row)) if per_row else None,
            "consensus_pbr": _safe_number(raw[last_year_col].get(pbr_row)) if pbr_row else None,
            "consensus_eps": _safe_number(raw[last_year_col].get(eps_row)) if eps_row else None,
            "consensus_bps": _safe_number(raw[last_year_col].get(bps_row)) if bps_row else None,
        }
    except Exception:
        return {}


def _build_stock_attractiveness(raw_data_dir, krx_dict):
    """웹 검색/필터용 종목 시장 매력도 payload 생성.

    CSV 산출물이 아니라 GitHub Pages에서 즉시 검색 가능한 축약 JSON을 만든다.
    최신 KRX 스냅샷 + 컨센서스 + 주요 팩터 최신값을 ticker 단위로 결합한다.
    """
    raw_data_dir = Path(raw_data_dir)
    snap_dir = raw_data_dir / "stock_market_snapshot"
    if not snap_dir.exists():
        return {"as_of": "", "rows": []}

    import re
    dates = []
    for f in snap_dir.glob("*_market_cap_by_ticker_*.csv"):
        m = re.search(r"_(\d{8})\.csv$", f.name)
        if m:
            dates.append(m.group(1))
    if not dates:
        return {"as_of": "", "rows": []}
    latest_date = max(dates)
    as_of = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]}"

    names = {}
    names_path = snap_dir / f"ticker_names_{latest_date}.csv"
    if names_path.exists():
        try:
            names_df = pd.read_csv(names_path, dtype={"ticker": str})
            names = dict(zip(names_df["ticker"].str.zfill(6), names_df["name"]))
        except Exception:
            names = {}
    if krx_dict:
        names.update({str(k).zfill(6): v for k, v in krx_dict.items()})

    frames = []
    for market in ["kospi", "kosdaq"]:
        cap_path = snap_dir / f"{market}_market_cap_by_ticker_{latest_date}.csv"
        fund_path = snap_dir / f"{market}_fundamental_by_ticker_{latest_date}.csv"
        if not cap_path.exists():
            continue
        cap = pd.read_csv(cap_path, dtype={"티커": str})
        cap["ticker"] = cap["티커"].astype(str).str.zfill(6)
        cap["market"] = market.upper()
        for col in ["종가", "시가총액", "거래량", "거래대금", "상장주식수"]:
            if col in cap.columns:
                cap[col] = pd.to_numeric(cap[col], errors="coerce")
        if fund_path.exists():
            fund = pd.read_csv(fund_path, dtype={"티커": str})
            fund["ticker"] = fund["티커"].astype(str).str.zfill(6)
            for col in ["BPS", "PER", "PBR", "EPS", "DIV", "DPS"]:
                if col in fund.columns:
                    fund[col] = pd.to_numeric(fund[col], errors="coerce")
            cap = cap.merge(fund.drop(columns=["티커"], errors="ignore"), on="ticker", how="left")
        frames.append(cap)
    if not frames:
        return {"as_of": as_of, "rows": []}

    base = pd.concat(frames, ignore_index=True)
    base["name"] = base["ticker"].map(names).fillna(base["ticker"])
    base = base.sort_values("시가총액", ascending=False)
    base["market_cap_rank_all"] = range(1, len(base) + 1)
    base["market_cap_rank_market"] = base.groupby("market")["시가총액"].rank(method="first", ascending=False)
    base["kospi200_proxy"] = (base["market"].eq("KOSPI") & (base["market_cap_rank_market"] <= 200)).astype(int)

    def size_bucket(row):
        cap = row.get("시가총액")
        rank = row.get("market_cap_rank_market")
        if pd.isna(cap) or pd.isna(rank):
            return "unknown"
        if cap >= 10_000_000_000_000 or rank <= 100:
            return "large"
        if cap >= 1_000_000_000_000 or rank <= 300:
            return "mid"
        return "small"
    base["size_bucket"] = base.apply(size_bucket, axis=1)

    consensus_path = raw_data_dir / "valuation" / "earnings_consensus.csv"
    consensus_map = {}
    if consensus_path.exists():
        try:
            cdf = pd.read_csv(consensus_path, dtype={"ticker": str})
            for rec in cdf.fillna("").to_dict(orient="records"):
                t = str(rec.get("ticker", "")).zfill(6)
                consensus_map[t] = _parse_earnings_consensus_record(rec)
        except Exception as e:
            logger.warning("stock_attractiveness 컨센서스 파싱 실패: %s", e)

    db_path = raw_data_dir.parent / "database" / "quant_data.sqlite"
    factor_frames = []
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            table_specs = [
                ("factor_valuation_per_pbr_month", "period", ["sector", "valuation_score", "per_percentile_sector", "pbr_percentile_sector", "pbr_zscore_own_24m"]),
                ("factor_sector_relative_value_month", "period", [
                    "sector_relative_per", "sector_relative_pbr", "pbr_roe_adjusted_score", "value_quality_score",
                    "sector_value_zscore", "debt_ratio", "debt_to_assets", "fcf", "fcf_to_assets",
                    "debt_to_equity", "net_debt_to_ebitda", "interest_coverage", "current_ratio", "equity_impairment_flag",
                    "operating_cashflow_positive", "fcf_margin", "fcf_yield", "accrual_ratio", "cash_conversion",
                    "revenue_yoy_stability", "op_margin_volatility", "net_loss_count", "roe_volatility",
                    "debt_ratio_score", "fcf_to_assets_score", "financial_quality_score",
                    "balance_sheet_quality_score", "cashflow_quality_score", "earnings_stability_score", "quality_source",
                ]),
                ("factor_stock_price_momentum_month", "period", ["close", "ret_1m", "ret_3m", "ret_6m", "momentum_score", "turnover_spike_flag"]),
                ("factor_size_month", "period", ["market_cap", "size_percentile_cross", "small_cap_score"]),
                ("factor_liquidity_turnover_month", "period", ["turnover_value_avg", "turnover_ratio", "liquidity_score"]),
                ("factor_roe_trend_month", "period", ["roe", "roe_sector_pct_ts"]),
                ("factor_investor_flow_momentum_month", "period", ["flow_score", "foreign_net_ratio", "inst_net_ratio", "foreign_net_ratio_change", "inst_net_ratio_change"]),
                ("factor_shorting_month", "period", ["shorting_pressure_score", "short_squeeze_flag", "balance_ratio", "balance_ratio_1m_chg"]),
                ("factor_technical_meanrev_snapshot", "snapshot_date", ["meanrev_score", "rsi_14", "bb_percent_b", "disparity_20"]),
                ("factor_value_composite_snapshot", "snapshot_date", ["value_composite_score", "forward_valuation_score", "peg_composite_score", "forward_per", "peg_ratio"]),
                ("factor_forward_per_snapshot", "snapshot_date", ["eps_growth_expected"]),
                ("factor_earnings_momentum_snapshot", "snapshot_date", ["earnings_momentum_score", "op_profit_yoy", "latest_quarter"]),
                ("factor_piotroski_snapshot", "bsns_year", ["f_score", "f_score_norm"]),
            ]
            for table, date_col, cols in table_specs:
                df = _latest_table_rows(conn, table, date_col=date_col)
                if df.empty:
                    continue
                keep = ["ticker"] + [c for c in cols if c in df.columns]
                renamed = df[keep].copy()
                prefix = table.replace("factor_", "").replace("_month", "").replace("_snapshot", "")
                for c in keep:
                    if c != "ticker":
                        renamed.rename(columns={c: f"{prefix}__{c}"}, inplace=True)
                factor_frames.append(renamed)
            conn.close()
        except Exception as e:
            logger.warning("stock_attractiveness factor load 실패: %s", e)

    out = base.copy()
    for ff in factor_frames:
        out = out.merge(ff, on="ticker", how="left")

    score_cols = {
        "score_base_5factor": ["valuation_per_pbr__valuation_score", "stock_price_momentum__momentum_score", "size__size_percentile_cross", "liquidity_turnover__liquidity_score", "roe_trend__roe_sector_pct_ts"],
        "score_value_quality": ["valuation_per_pbr__valuation_score", "roe_trend__roe_sector_pct_ts", "value_composite__value_composite_score", "piotroski__f_score_norm", "earnings_momentum__earnings_momentum_score"],
        "score_momentum_flow": ["stock_price_momentum__momentum_score", "investor_flow_momentum__flow_score", "liquidity_turnover__liquidity_score"],
        "score_reversal_value_flow": ["valuation_per_pbr__valuation_score", "technical_meanrev__meanrev_score", "investor_flow_momentum__flow_score"],
        "score_short_squeeze_addon": ["stock_price_momentum__momentum_score", "investor_flow_momentum__flow_score", "shorting__shorting_pressure_score"],
    }

    def weighted_score(parts):
        vals = []
        weights = []
        for value, weight in parts:
            v = _safe_number(value)
            if v is None:
                continue
            vals.append(v * weight)
            weights.append(weight)
        return round(sum(vals) / sum(weights), 4) if weights else None

    def compact_factor_profile(rec):
        def pct_score(v):
            n = _safe_number(v)
            return round(n * 100, 1) if n is not None else None

        profile = [
            {"key": "valuation", "label": "밸류", "score": pct_score(rec.get("valuation_score")), "raw": rec.get("per"), "raw_label": "PER"},
            {"key": "sector_value", "label": "섹터상대 가치", "score": pct_score(rec.get("sector_value_score")), "raw": rec.get("sector_value_zscore"), "raw_label": "섹터 value z"},
            {"key": "roe", "label": "ROE", "score": pct_score(rec.get("roe_score")), "raw": rec.get("roe"), "raw_label": "ROE"},
            {"key": "momentum", "label": "가격 모멘텀", "score": pct_score(rec.get("momentum_score")), "raw": rec.get("ret_3m"), "raw_label": "3M 수익률"},
            {"key": "flow", "label": "수급", "score": pct_score(rec.get("flow_score")), "raw": rec.get("foreign_net_ratio_change"), "raw_label": "외국인 변화"},
            {"key": "liquidity", "label": "유동성", "score": pct_score(rec.get("liquidity_score")), "raw": rec.get("turnover_value_avg"), "raw_label": "평균 거래대금"},
            {"key": "bs_quality", "label": "재무건전성", "score": pct_score(rec.get("balance_sheet_quality_score")), "raw": rec.get("debt_ratio"), "raw_label": "부채비율"},
            {"key": "cf_quality", "label": "현금흐름", "score": pct_score(rec.get("cashflow_quality_score")), "raw": rec.get("fcf_to_assets"), "raw_label": "FCF/자산"},
            {"key": "earnings", "label": "실적", "score": pct_score(rec.get("earnings_momentum_score")), "raw": rec.get("this_year_op_growth_pct"), "raw_label": "올해 영익 성장"},
            {"key": "reversal", "label": "반등 셋업", "score": pct_score(rec.get("meanrev_score")), "raw": rec.get("rsi_14"), "raw_label": "RSI"},
        ]
        return [p for p in profile if p.get("score") is not None or p.get("raw") is not None]

    def build_risk_flags(rec):
        flags = []
        if _safe_number(rec.get("debt_ratio")) is not None and rec["debt_ratio"] > 2.0:
            flags.append("부채비율 200% 초과")
        if _safe_number(rec.get("fcf_to_assets")) is not None and rec["fcf_to_assets"] < 0:
            flags.append("FCF/자산 음수")
        if _safe_number(rec.get("ret_3m")) is not None and abs(rec["ret_3m"]) >= 0.25:
            flags.append("최근 3개월 가격 변동성 큼")
        if _safe_number(rec.get("turnover_value_avg")) is not None and rec["turnover_value_avg"] < 1_000_000_000:
            flags.append("평균 거래대금 10억원 미만")
        if rec.get("equity_impairment_flag"):
            flags.append("자본잠식 플래그")
        if _safe_number(rec.get("net_loss_count")) is not None and rec["net_loss_count"] >= 2:
            flags.append("최근 적자 빈도 높음")
        if _safe_number(rec.get("sector_value_zscore")) is not None and rec["sector_value_zscore"] < -1:
            flags.append("섹터 자체가 과거 대비 저평가 구간")
        if rec.get("short_squeeze_flag"):
            flags.append("공매도/숏커버 이벤트성 변동 가능")
        return flags[:5]

    rows = []
    for _, r in out.iterrows():
        t = str(r.get("ticker", "")).zfill(6)
        rec = {
            "ticker": t,
            "name": r.get("name") or t,
            "market": r.get("market"),
            "sector": r.get("valuation_per_pbr__sector") or "",
            "price": _safe_number(r.get("종가")),
            "market_cap": _safe_number(r.get("시가총액")),
            "trading_value": _safe_number(r.get("거래대금")),
            "market_cap_rank": int(r.get("market_cap_rank_market")) if not pd.isna(r.get("market_cap_rank_market")) else None,
            "market_cap_rank_all": int(r.get("market_cap_rank_all")) if not pd.isna(r.get("market_cap_rank_all")) else None,
            "size_bucket": r.get("size_bucket"),
            "kospi200_proxy": int(r.get("kospi200_proxy") or 0),
            "per": _safe_number(r.get("PER")),
            "pbr": _safe_number(r.get("PBR")),
            "eps": _safe_number(r.get("EPS")),
            "bps": _safe_number(r.get("BPS")),
            "div_yield": _safe_number(r.get("DIV")),
            "valuation_score": _safe_number(r.get("valuation_per_pbr__valuation_score")),
            "sector_relative_per": _safe_number(r.get("sector_relative_value__sector_relative_per")),
            "sector_relative_pbr": _safe_number(r.get("sector_relative_value__sector_relative_pbr")),
            "sector_value_score": _safe_number(r.get("sector_relative_value__value_quality_score")),
            "sector_pbr_roe_score": _safe_number(r.get("sector_relative_value__pbr_roe_adjusted_score")),
            "sector_value_zscore": _safe_number(r.get("sector_relative_value__sector_value_zscore")),
            "debt_ratio": _safe_number(r.get("sector_relative_value__debt_ratio")),
            "debt_to_assets": _safe_number(r.get("sector_relative_value__debt_to_assets")),
            "fcf": _safe_number(r.get("sector_relative_value__fcf")),
            "fcf_to_assets": _safe_number(r.get("sector_relative_value__fcf_to_assets")),
            "debt_ratio_score": _safe_number(r.get("sector_relative_value__debt_ratio_score")),
            "fcf_to_assets_score": _safe_number(r.get("sector_relative_value__fcf_to_assets_score")),
            "financial_quality_score": _safe_number(r.get("sector_relative_value__financial_quality_score")),
            "debt_to_equity": _safe_number(r.get("sector_relative_value__debt_to_equity")),
            "net_debt_to_ebitda": _safe_number(r.get("sector_relative_value__net_debt_to_ebitda")),
            "interest_coverage": _safe_number(r.get("sector_relative_value__interest_coverage")),
            "current_ratio": _safe_number(r.get("sector_relative_value__current_ratio")),
            "equity_impairment_flag": int(_safe_number(r.get("sector_relative_value__equity_impairment_flag")) or 0),
            "operating_cashflow_positive": _safe_number(r.get("sector_relative_value__operating_cashflow_positive")),
            "fcf_margin": _safe_number(r.get("sector_relative_value__fcf_margin")),
            "fcf_yield": _safe_number(r.get("sector_relative_value__fcf_yield")),
            "accrual_ratio": _safe_number(r.get("sector_relative_value__accrual_ratio")),
            "cash_conversion": _safe_number(r.get("sector_relative_value__cash_conversion")),
            "revenue_yoy_stability": _safe_number(r.get("sector_relative_value__revenue_yoy_stability")),
            "op_margin_volatility": _safe_number(r.get("sector_relative_value__op_margin_volatility")),
            "net_loss_count": _safe_number(r.get("sector_relative_value__net_loss_count")),
            "roe_volatility": _safe_number(r.get("sector_relative_value__roe_volatility")),
            "balance_sheet_quality_score": _safe_number(r.get("sector_relative_value__balance_sheet_quality_score")),
            "cashflow_quality_score": _safe_number(r.get("sector_relative_value__cashflow_quality_score")),
            "earnings_stability_score": _safe_number(r.get("sector_relative_value__earnings_stability_score")),
            "quality_source": r.get("sector_relative_value__quality_source"),
            "momentum_score": _safe_number(r.get("stock_price_momentum__momentum_score")),
            "ret_1m": _safe_number(r.get("stock_price_momentum__ret_1m")),
            "ret_3m": _safe_number(r.get("stock_price_momentum__ret_3m")),
            "ret_6m": _safe_number(r.get("stock_price_momentum__ret_6m")),
            "turnover_spike_flag": int(_safe_number(r.get("stock_price_momentum__turnover_spike_flag")) or 0),
            "liquidity_score": _safe_number(r.get("liquidity_turnover__liquidity_score")),
            "turnover_value_avg": _safe_number(r.get("liquidity_turnover__turnover_value_avg")),
            "turnover_ratio": _safe_number(r.get("liquidity_turnover__turnover_ratio")),
            "roe": _safe_number(r.get("roe_trend__roe")),
            "roe_score": _safe_number(r.get("roe_trend__roe_sector_pct_ts")),
            "flow_score": _safe_number(r.get("investor_flow_momentum__flow_score")),
            "foreign_net_ratio": _safe_number(r.get("investor_flow_momentum__foreign_net_ratio")),
            "inst_net_ratio": _safe_number(r.get("investor_flow_momentum__inst_net_ratio")),
            "foreign_net_ratio_change": _safe_number(r.get("investor_flow_momentum__foreign_net_ratio_change")),
            "inst_net_ratio_change": _safe_number(r.get("investor_flow_momentum__inst_net_ratio_change")),
            "meanrev_score": _safe_number(r.get("technical_meanrev__meanrev_score")),
            "rsi_14": _safe_number(r.get("technical_meanrev__rsi_14")),
            "bb_percent_b": _safe_number(r.get("technical_meanrev__bb_percent_b")),
            "disparity_20": _safe_number(r.get("technical_meanrev__disparity_20")),
            "shorting_pressure_score": _safe_number(r.get("shorting__shorting_pressure_score")),
            "balance_ratio": _safe_number(r.get("shorting__balance_ratio")),
            "balance_ratio_1m_chg": _safe_number(r.get("shorting__balance_ratio_1m_chg")),
            "short_squeeze_flag": int(_safe_number(r.get("shorting__short_squeeze_flag")) or 0),
            "value_composite_score": _safe_number(r.get("value_composite__value_composite_score")),
            "forward_valuation_score": _safe_number(r.get("value_composite__forward_valuation_score")),
            "forward_per": _safe_number(r.get("value_composite__forward_per")),
            "eps_growth_expected": _safe_number(r.get("forward_per__eps_growth_expected")),
            "earnings_momentum_score": _safe_number(r.get("earnings_momentum__earnings_momentum_score")),
            "op_profit_yoy": _safe_number(r.get("earnings_momentum__op_profit_yoy")),
            "f_score_norm": _safe_number(r.get("piotroski__f_score_norm")),
        }
        rec.update(consensus_map.get(t, {}))
        for score_name, cols in score_cols.items():
            vals = [_safe_number(r.get(c)) for c in cols]
            vals = [v for v in vals if v is not None]
            rec[score_name] = round(sum(vals) / len(vals), 4) if vals else None
        rec["scenario_a_momentum"] = weighted_score([
            (rec.get("momentum_score"), 0.35),
            (rec.get("flow_score"), 0.30),
            (rec.get("liquidity_score"), 0.20),
            (rec.get("earnings_momentum_score"), 0.15),
        ])
        rec["scenario_b_value_quality"] = weighted_score([
            (rec.get("valuation_score"), 0.16),
            (rec.get("sector_value_score"), 0.22),
            (rec.get("roe_score"), 0.14),
            (rec.get("f_score_norm"), 0.10),
            (rec.get("balance_sheet_quality_score"), 0.12),
            (rec.get("cashflow_quality_score"), 0.12),
            (rec.get("earnings_stability_score"), 0.08),
            (rec.get("earnings_momentum_score"), 0.10),
            (rec.get("forward_valuation_score"), 0.06),
        ])
        rec["scenario_c_reversal"] = weighted_score([
            (rec.get("meanrev_score"), 0.30),
            (rec.get("valuation_score"), 0.20),
            (rec.get("sector_value_score"), 0.20),
            (rec.get("flow_score"), 0.20),
            (rec.get("shorting_pressure_score"), 0.10),
        ])
        rec["scenario_d_large_stable"] = weighted_score([
            (_safe_number(r.get("size__size_percentile_cross")), 0.25),
            (rec.get("liquidity_score"), 0.20),
            (rec.get("roe_score"), 0.20),
            (rec.get("valuation_score"), 0.15),
            (rec.get("flow_score"), 0.10),
            (rec.get("f_score_norm"), 0.10),
        ])
        score_vals = [rec.get(k) for k in score_cols if rec.get(k) is not None]
        rec["market_attractiveness_score"] = round(sum(score_vals) / len(score_vals), 4) if score_vals else None
        rec["factor_profile"] = compact_factor_profile(rec)
        rec["risk_flags"] = build_risk_flags(rec)
        rows.append(rec)

    rows.sort(key=lambda x: (x.get("market_attractiveness_score") is None, -(x.get("market_attractiveness_score") or 0)))
    return {
        "as_of": as_of,
        "method": "latest KRX snapshot + earnings consensus + latest factor tables; KOSPI200 is approximated by KOSPI market-cap top 200 when official constituent file is unavailable",
        "rows": rows,
    }


def _compute_derived_macro(quant_data, raw_data_dir, include_stock_detail=False):
    """수집된 CSV에서 파생 거시지표를 계산해 quant_data['macro']에 추가."""
    indices_dir = Path(raw_data_dir) / "macro" / "macro_indices"
    commod_dir  = Path(raw_data_dir) / "macro" / "commodities"

    def _load(path):
        """CSV → {YYYY-MM-DD: float}. Close → Adj Close → 첫 번째 숫자 열 순으로 시도."""
        if not path.exists():
            return {}
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
            for col in ["Close", "close", "Adj Close"]:
                if col in df.columns:
                    s = df[col].dropna()
                    return {d.strftime("%Y-%m-%d"): float(v) for d, v in s.items()}
            num = df.select_dtypes(include="number")
            if not num.empty:
                s = num.iloc[:, 0].dropna()
                return {d.strftime("%Y-%m-%d"): float(v) for d, v in s.items()}
        except Exception:
            pass
        return {}

    def _to_monthly(daily):
        """일별·주별 → 월말 기준 월별 dict (키: YYYY-MM-01)."""
        buckets = {}
        for d, v in sorted(daily.items()):
            buckets[d[:7]] = v
        return {f"{ym}-01": v for ym, v in buckets.items()}

    def _records(d):
        return [{"date": k, "value": v} for k, v in sorted(d.items())]

    # ── 1. 실질 Fed 유동성 (billions USD) ────────────────────────────────
    # WALCL, WTREGEN: FRED 단위 millions → /1000 = billions
    # RRPONTSYD: FRED 단위 billions (그대로)
    walcl   = _to_monthly(_load(indices_dir / "WALCL.csv"))
    wtregen = _to_monthly(_load(indices_dir / "WTREGEN.csv"))
    rrpo    = _to_monthly(_load(indices_dir / "RRPONTSYD.csv"))
    if walcl and wtregen and rrpo:
        dates = sorted(set(walcl) & set(wtregen) & set(rrpo))
        res = {}
        for d in dates:
            try:
                res[d] = round((walcl[d] - wtregen[d]) / 1000 - rrpo[d], 1)
            except Exception:
                pass
        if res:
            quant_data["macro"]["real_fed_liquidity"] = _records(res)
            logger.info(" - 파생: 실질 Fed 유동성 (%d rows)", len(res))

    # ── 2. 미국 장단기 금리차 (10Y − 2Y) ────────────────────────────────
    dgs10 = _to_monthly(_load(indices_dir / "DGS10.csv"))
    dgs2  = _to_monthly(_load(indices_dir / "DGS2.csv"))
    if dgs10 and dgs2:
        dates = sorted(set(dgs10) & set(dgs2))
        res = {d: round(dgs10[d] - dgs2[d], 3) for d in dates}
        quant_data["macro"]["us_yield_spread"] = _records(res)
        logger.info(" - 파생: 미국 장단기 금리차 (%d rows)", len(res))

    # ── 3. 구리/금 비율 (경기 낙관 방향성) ──────────────────────────────
    copper = _to_monthly(_load(commod_dir / "Copper.csv"))
    gold   = _to_monthly(_load(commod_dir / "Gold.csv"))
    if copper and gold:
        dates = sorted(set(copper) & set(gold))
        res = {d: round(copper[d] / gold[d], 6)
               for d in dates if gold.get(d) and gold[d] > 0}
        if res:
            quant_data["macro"]["copper_gold_ratio"] = _records(res)
            logger.info(" - 파생: 구리/금 비율 (%d rows)", len(res))

    # ── 4. WTI/금 비율 (경기 vs 안전자산) ───────────────────────────────
    wti = _to_monthly(_load(commod_dir / "WTI.csv"))
    if wti and gold:
        dates = sorted(set(wti) & set(gold))
        res = {d: round(wti[d] / gold[d], 5)
               for d in dates if gold.get(d) and gold[d] > 0}
        if res:
            quant_data["macro"]["wti_gold_ratio"] = _records(res)
            logger.info(" - 파생: WTI/금 비율 (%d rows)", len(res))

    # ── 5. AAII Bull−Bear Spread (투자심리) ─────────────────────────────
    bull = _load(indices_dir / "AAIIBULL.csv")
    bear = _load(indices_dir / "AAIIBEAR.csv")
    if bull and bear:
        dates = sorted(set(bull) & set(bear))
        res = {d: round(bull[d] - bear[d], 1) for d in dates}
        quant_data["macro"]["aaii_bull_bear"] = _records(res)
        logger.info(" - 파생: AAII Bull-Bear Spread (%d rows)", len(res))

    # ── 6. EEM/SOXX 상대강도 (신흥국 대비 반도체) ────────────────────────
    eem  = _to_monthly(_load(indices_dir / "EEM.csv"))
    soxx = _to_monthly(_load(indices_dir / "SOXX.csv"))
    if eem and soxx:
        dates = sorted(set(eem) & set(soxx))
        res = {d: round(soxx[d] / eem[d], 4)
               for d in dates if eem.get(d) and eem[d] > 0}
        if res:
            quant_data["macro"]["soxx_eem_ratio"] = _records(res)
            logger.info(" - 파생: SOXX/EEM 상대강도 (%d rows)", len(res))

    # ── 7. US Credit Impulse (신용 충격 지수) ────────────────────────────
    # = Δ(월간 대출증감/GDP) — 경기 9~12개월 선행
    # TOTLL: 주간→월말 resample / GDP: 분기→월 ffill
    totll = _to_monthly(_load(indices_dir / "US_TOTLL.csv"))
    gdp   = _to_monthly(_load(indices_dir / "US_GDP.csv"))
    if totll and gdp:
        try:
            t_ser = pd.Series(totll).sort_index()
            g_ser = pd.Series(gdp).sort_index()
            # GDP 분기 → 월별 ffill 보간
            all_m = pd.date_range(g_ser.index[0], t_ser.index[-1], freq="MS")
            g_ser = g_ser.reindex(all_m.strftime("%Y-%m-%d")).ffill()
            common = sorted(set(t_ser.index) & set(g_ser.index))
            if len(common) > 24:
                t_c = t_ser.loc[common]
                g_c = g_ser.loc[common]
                flow    = t_c.diff(1)               # 월간 신규 대출
                ci_raw  = flow / g_c * 100           # % of GDP
                ci_imp  = ci_raw.diff(12).dropna()   # YoY 변화 = 신용충격
                res = {d: round(float(v), 3) for d, v in ci_imp.items()
                       if not pd.isna(v)}
                if res:
                    quant_data["macro"]["us_credit_impulse"] = _records(res)
                    logger.info(" - 파생: US Credit Impulse (%d rows)", len(res))
        except Exception as e:
            logger.warning(" - Credit Impulse 계산 실패: %s", e)

    # ── 8. 한국 회사채 스프레드 (ECOS 수집 시 자동 계산) ─────────────────
    gov3y    = _to_monthly(_load(indices_dir / "KOR_GOV3Y.csv"))
    corp_aa  = _to_monthly(_load(indices_dir / "KOR_CORP_AA.csv"))
    if gov3y and corp_aa:
        dates = sorted(set(gov3y) & set(corp_aa))
        res = {d: round(corp_aa[d] - gov3y[d], 3) for d in dates}
        quant_data["macro"]["kor_corp_spread"] = _records(res)
        logger.info(" - 파생: 한국 회사채 스프레드 (%d rows)", len(res))

    # ── 9. 한국 BBB- 신용스프레드 (ECOS)
    corp_bbb = _to_monthly(_load(indices_dir / "KOR_CORP_BBB.csv"))
    if gov3y and corp_bbb:
        dates = sorted(set(gov3y) & set(corp_bbb))
        res = {d: round(corp_bbb[d] - gov3y[d], 3) for d in dates}
        if res:
            quant_data["macro"]["kor_corp_spread_bbb"] = _records(res)
            logger.info(" - 파생: 한국 BBB- 신용스프레드 (%d rows)", len(res))

    # ── 10. 한국 장단기 금리차 (10Y − 3Y)
    gov10y = _to_monthly(_load(indices_dir / "KOR_GOV10Y.csv"))
    if gov10y and gov3y:
        dates = sorted(set(gov10y) & set(gov3y))
        res = {d: round(gov10y[d] - gov3y[d], 3) for d in dates}
        if res:
            quant_data["macro"]["kor_yield_spread"] = _records(res)
            logger.info(" - 파생: 한국 장단기 금리차 10Y-3Y (%d rows)", len(res))

    # ── 11. WTI/Brent 스프레드 ─────────────────────────────────────────────
    wti_d   = _to_monthly(_load(commod_dir / "WTI.csv"))
    brent_d = _to_monthly(_load(commod_dir / "Brent.csv"))
    if wti_d and brent_d:
        dates = sorted(set(wti_d) & set(brent_d))
        res = {d: round(wti_d[d] - brent_d[d], 3) for d in dates}
        quant_data["macro"]["wti_brent_spread"] = _records(res)
        logger.info(" - 파생: WTI/Brent 스프레드 (%d rows)", len(res))

    # ── 10. 미국 산업생산 YoY (실물경기 확인 지표) ───────────────────────
    indpro = _to_monthly(_load(indices_dir / "US_INDPRO.csv"))
    if indpro:
        dates = sorted(indpro.keys())
        res = {}
        for d in dates:
            try:
                dt   = pd.Timestamp(d)
                prev = (dt - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
                if prev in indpro and indpro[prev] > 0:
                    res[d] = round((indpro[d] - indpro[prev]) / indpro[prev] * 100, 2)
            except Exception:
                pass
        if res:
            quant_data["macro"]["us_indpro_yoy"] = _records(res)
            logger.info(" - 파생: 미국 산업생산 YoY (%d rows)", len(res))

    # ── 11. KOSPI 시총가중 PBR (개별 종목 fundamental에서 계산)
    # pykrx KRX 인증 없이 사용 가능한 폴백: stock_detail 수집 데이터 활용
    # 기본 웹 export는 stock_detail 대용량 로드를 피하고 raw 파일 부작용도 만들지 않는다.
    if include_stock_detail:
        _compute_kospi_pbr_from_stocks(quant_data, raw_data_dir)


def _compute_kospi_pbr_from_stocks(quant_data, raw_data_dir):
    """stock_detail 수집 데이터(fundamental + market_cap)에서 시총가중 KOSPI PBR 계산."""
    stock_dir = Path(raw_data_dir) / "stock_detail"
    if not stock_dir.exists():
        return

    try:
        pbr_frames, cap_frames = [], []

        for ticker_dir in stock_dir.iterdir():
            if not ticker_dir.is_dir():
                continue
            fund_path = ticker_dir / "fundamental.csv"
            cap_path  = ticker_dir / "market_cap.csv"
            if not fund_path.exists() or not cap_path.exists():
                continue
            try:
                fund = pd.read_csv(fund_path, index_col=0, parse_dates=True)
                cap  = pd.read_csv(cap_path,  index_col=0, parse_dates=True)

                pbr_col = next((c for c in fund.columns if "PBR" in c.upper()), None)
                cap_col = next((c for c in cap.columns
                                if "시가총액" in c or "MarCap" in c.lower() or "marcap" in c.lower()), None)
                if pbr_col is None or cap_col is None:
                    continue

                pbr_s = fund[pbr_col].replace(0, float("nan")).dropna()
                cap_s = cap[cap_col].replace(0, float("nan")).dropna()
                common = pbr_s.index.intersection(cap_s.index)
                if len(common) < 10:
                    continue

                pbr_frames.append(pbr_s.loc[common].rename(ticker_dir.name))
                cap_frames.append(cap_s.loc[common].rename(ticker_dir.name))
            except Exception:
                continue

        if not pbr_frames:
            return

        pbr_df = pd.concat(pbr_frames, axis=1)
        cap_df = pd.concat(cap_frames, axis=1).reindex(columns=pbr_df.columns)

        # 시총가중 PBR: Σ(PBR_i × MarCap_i) / Σ(MarCap_i)
        weighted = (pbr_df * cap_df).sum(axis=1, min_count=1)
        total    = cap_df.sum(axis=1, min_count=1)
        kospi_pbr = (weighted / total).dropna()

        if kospi_pbr.empty:
            return

        # 분위수 계산
        current    = float(kospi_pbr.iloc[-1])
        pct_rank   = round(float((kospi_pbr < current).mean() * 100), 1)

        valuation_dir = Path(raw_data_dir) / "valuation"
        valuation_dir.mkdir(parents=True, exist_ok=True)

        # 이력 저장
        out = kospi_pbr.reset_index()
        out.columns = ["date", "kospi_pbr"]
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out.to_csv(valuation_dir / "kospi_fundamental_history.csv", index=False)

        # 분위수 스냅샷 저장
        pd.DataFrame([{
            "date":        str(kospi_pbr.index[-1])[:10],
            "current_pbr": round(current, 3),
            "percentile":  pct_rank,
            "min_10y":     round(float(kospi_pbr.min()), 3),
            "max_10y":     round(float(kospi_pbr.max()), 3),
            "median_10y":  round(float(kospi_pbr.median()), 3),
            "mean_10y":    round(float(kospi_pbr.mean()), 3),
        }]).to_csv(valuation_dir / "kospi_pbr_percentile.csv", index=False)

        logger.info(
            " - 파생: KOSPI 시총가중 PBR %.2f배 (%.1f%%ile, %d 종목 기준)",
            current, pct_rank, pbr_df.shape[1]
        )
    except Exception as e:
        logger.warning(" - KOSPI PBR 계산 실패 (건너뜀): %s", e)


def _build_factor_validation(raw_data_dir: Path) -> dict:
    """팩터 심사표 CSV 산출물을 웹용 payload로 축약."""
    try:
        project_dir = Path(__file__).resolve().parents[2]
        workspace_dir = project_dir.parents[1]
        outputs_root = workspace_dir / "02_outputs"
        candidates = sorted(outputs_root.glob("*_factor_validation_dashboard"))
        if not candidates:
            return {"as_of": "", "summary": [], "current_top": [], "correlation": {}, "coverage": [], "source_dir": ""}
        source_dir = candidates[-1]

        def load_csv(name):
            path = source_dir / name
            if not path.exists():
                logger.warning("factor_validation CSV 없음: %s", path)
                return pd.DataFrame()
            df = pd.read_csv(path)
            return df.where(pd.notnull(df), None)

        summary = load_csv("factor_validation_summary.csv")
        current = load_csv("current_top30_by_factor.csv")
        corr_df = load_csv("factor_correlation_matrix.csv")
        coverage = load_csv("factor_coverage_by_period.csv")

        correlation = {}
        if not corr_df.empty:
            first_col = corr_df.columns[0]
            for _, row in corr_df.iterrows():
                key = row.get(first_col)
                if key is None:
                    continue
                correlation[str(key)] = {
                    str(col): _safe_number(row.get(col))
                    for col in corr_df.columns
                    if col != first_col
                }

        as_of = ""
        if not current.empty and "period" in current.columns:
            vals = [str(v) for v in current["period"].dropna().tolist()]
            as_of = max(vals) if vals else ""
        if not as_of and not coverage.empty and "period" in coverage.columns:
            vals = [str(v) for v in coverage["period"].dropna().tolist()]
            as_of = max(vals) if vals else ""

        payload = {
            "as_of": as_of,
            "source_dir": str(source_dir),
            "method": "factor_validation_summary/current_top30/correlation/coverage CSV export; TopN 수익률은 거래비용 미반영, look-ahead caveat 유지",
            "summary": summary.to_dict(orient="records") if not summary.empty else [],
            "current_top": current.to_dict(orient="records") if not current.empty else [],
            "correlation": correlation,
            "coverage": coverage.to_dict(orient="records") if not coverage.empty else [],
        }
        return payload
    except Exception as e:
        logger.warning("factor_validation payload 로드 실패: %s", e)
        return {"as_of": "", "summary": [], "current_top": [], "correlation": {}, "coverage": [], "source_dir": ""}


def _build_factor_topn_quintile_backtest(raw_data_dir: Path) -> dict:
    """TopN/분위수 백테스트 CSV 산출물을 웹용 payload로 축약."""
    try:
        project_dir = Path(__file__).resolve().parents[2]
        workspace_dir = project_dir.parents[1]
        outputs_root = workspace_dir / "02_outputs"
        candidates = sorted(outputs_root.glob("*_factor_topn_quintile_backtest"))
        if not candidates:
            return {
                "as_of": "",
                "source_dir": "",
                "method": "",
                "topn_summary": [],
                "quintile_summary": [],
                "quintile_spread": [],
                "current_top": [],
                "coverage": [],
            }
        source_dir = candidates[-1]

        def load_csv(name):
            path = source_dir / name
            if not path.exists():
                logger.warning("factor_topn_quintile CSV 없음: %s", path)
                return pd.DataFrame()
            df = pd.read_csv(path)
            return df.where(pd.notnull(df), None)

        topn = load_csv("summary_topn_by_score.csv")
        quintile = load_csv("summary_quintile_by_score.csv")
        spread = load_csv("quintile_spread_summary.csv")
        current = load_csv("current_top30_by_score.csv")
        coverage = load_csv("coverage_by_period.csv")

        as_of = ""
        if not current.empty and "period" in current.columns:
            vals = [str(v) for v in current["period"].dropna().tolist()]
            as_of = max(vals) if vals else ""
        if not as_of and not coverage.empty and "period" in coverage.columns:
            vals = [str(v) for v in coverage["period"].dropna().tolist()]
            as_of = max(vals) if vals else ""

        return {
            "as_of": as_of,
            "source_dir": str(source_dir),
            "method": "월별 시가총액 상위 200개 KOSPI200 프록시 기준 TopN/5분위 검증; 거래비용·세금·슬리피지 미반영; 3M/6M forward return은 중첩 표본",
            "topn_summary": topn.to_dict(orient="records") if not topn.empty else [],
            "quintile_summary": quintile.to_dict(orient="records") if not quintile.empty else [],
            "quintile_spread": spread.to_dict(orient="records") if not spread.empty else [],
            "current_top": current.to_dict(orient="records") if not current.empty else [],
            "coverage": coverage.to_dict(orient="records") if not coverage.empty else [],
        }
    except Exception as e:
        logger.warning("factor_topn_quintile payload 로드 실패: %s", e)
        return {
            "as_of": "",
            "source_dir": "",
            "method": "",
            "topn_summary": [],
            "quintile_summary": [],
            "quintile_spread": [],
            "current_top": [],
            "coverage": [],
        }



def _build_regression_summary(raw_data_dir: Path) -> dict:
    """regression_* 테이블을 읽어 웹용 요약 딕셔너리 반환."""
    db_path = Path(raw_data_dir).parent / "database" / "quant_data.sqlite"
    if not db_path.exists():
        return {}
    try:
        import sqlite3, json as _json
        conn = sqlite3.connect(db_path)

        # 메타 (JSON 직렬화된 전체 결과 포함)
        meta_df = pd.read_sql("SELECT key, value FROM regression_meta", conn)
        meta = dict(zip(meta_df["key"], meta_df["value"]))

        market_timing_full = _json.loads(meta.get("full_market_timing", "{}"))
        fmb_full          = _json.loads(meta.get("full_fmb", "{}"))
        regime_full       = _json.loads(meta.get("full_regime", "{}"))

        # 시장 타이밍 요약 (base 모델 기준)
        base_mt = market_timing_full.get("base", {})
        timing_summary = {
            "signal":       base_mt.get("signal", "neutral"),
            "pred_pct":     base_mt.get("pred_pct", 0),
            "r2":           base_mt.get("r2", 0),
            "adj_r2":       base_mt.get("adj_r2", 0),
            "periods":      base_mt.get("periods", 0),
            "pred_period":  base_mt.get("pred_period", ""),
            "factors":      base_mt.get("factors", []),
            "full":         market_timing_full,  # full model 포함
        }

        # 팩터 IC 요약
        ic_summary = {
            "periods":      fmb_full.get("periods", 0),
            "stock_count":  fmb_full.get("stock_count", 0),
            "factors":      fmb_full.get("factors", []),
        }

        # 레짐 인터랙션 요약
        regime_summary = {
            "current_regime":  regime_full.get("current_regime", ""),
            "current_bucket":  regime_full.get("current_bucket", ""),
            "current_period":  regime_full.get("current_period", ""),
            "regimes":         regime_full.get("regimes", {}),
        }

        conn.close()
        return {
            "as_of":        meta.get("as_of", ""),
            "market_timing": timing_summary,
            "factor_ic":    ic_summary,
            "regime":       regime_summary,
        }
    except Exception as e:
        logger.warning("회귀 분석 요약 로드 실패: %s", e)
        return {}


def _inject_regime_scores(quant_data: dict):
    """regression_regime_adj_scores → stock_attractiveness rows에 regime_adj_score 주입."""
    db_path = Path(__file__).parents[2] / "data" / "database" / "quant_data.sqlite"
    if not db_path.exists():
        return
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        scores_df = pd.read_sql("SELECT ticker, regime_adj_score FROM regression_regime_adj_scores", conn)
        conn.close()
        score_map = dict(zip(scores_df["ticker"].astype(str).str.zfill(6),
                             scores_df["regime_adj_score"]))
        rows = quant_data.get("stock_attractiveness", {}).get("rows", [])
        for row in rows:
            t = str(row.get("ticker", "")).zfill(6)
            row["regime_adj_score"] = _safe_number(score_map.get(t))
    except Exception as e:
        logger.warning("regime_adj_score 주입 실패: %s", e)


def collect_quant_data(raw_data_dir, krx_dict=None, include_stock_detail=False):
    raw_data_dir = Path(raw_data_dir)
    krx_dict = krx_dict if krx_dict is not None else _load_krx_names()

    quant_data = {
        "macro": {},
        "money_flow": {},
        "sentiment": {},
        "valuation": {},
        "stock_attractiveness": {},
    }

    if include_stock_detail:
        quant_data["stock_detail"] = {"tickers": {}, "snapshots": {}}

    # 1. Macro Data 추출
    # 같은 stem이 여러 하위 폴더에 있으면 대시보드 지표용 원시 시계열(macro_indices)을
    # canonical source로 유지한다. 예: CPIAUCSL/UNRATE는 release_history에도 같은 파일명이
    # 있지만, 스코어카드는 장기 원시 시계열을 사용해야 YoY/최신값 계산이 정상 동작한다.
    macro_files = sorted(
        (raw_data_dir / "macro").glob("**/*.csv"),
        key=lambda p: (0 if p.parent.name == "macro_indices" else 1, str(p)),
    )
    macro_allowlist = {
        # UI에서 직접 사용하는 매크로/금리/원자재/스코어카드 키
        "BAMLC0A0CM", "BAMLH0A0HYM2", "BRA_CLI", "CHN_CLI", "CPIAUCSL",
        "DEU_CLI", "DGS10", "DGS2", "DXY", "FRA_CLI", "GBR_CLI", "Gold",
        "IND_CLI", "JPN_CLI", "KOR_BASE_RATE", "KOR_CALL_RATE", "KOR_CD91",
        "KOR_CLI", "KOR_CORP_AA", "KOR_EXPORTS", "KOR_GOV10Y", "KOR_GOV3Y",
        "KOR_GOV5Y", "M2SL", "NFCI", "STLFSI4", "TNX", "UMCSENT",
        "UNRATE", "USA_CLI", "USD_KRW", "VIX", "WALCL", "WTI",
        # 파생지표 계산용 소스
        "Copper", "WTREGEN", "RRPONTSYD", "AAIIBULL", "AAIIBEAR", "EEM", "SOXX",
        "US_TOTLL", "US_GDP", "KOR_CORP_BBB", "Brent", "US_INDPRO",
    }
    for file in macro_files:
        name = Path(file).stem
        if name not in macro_allowlist:
            continue
        try:
            if name in quant_data["macro"]:
                logger.warning(
                    "Duplicate macro key %s skipped: keeping existing source, ignored %s",
                    name,
                    file,
                )
                continue
            quant_data["macro"][name] = _records_from_csv(file)
        except Exception as e:
            logger.warning("Error reading %s: %s", file, e)

    # 2. Money Flow Data 추출
    for file in glob.glob(str(raw_data_dir / "money_flow" / "*.csv")):
        name = Path(file).stem
        try:
            quant_data["money_flow"][name] = _records_from_csv(file)
        except Exception as e:
            logger.warning("Error reading %s: %s", file, e)

    # 3. Sentiment JSON/CSV 추출
    sentiment_json = raw_data_dir / "sentiment" / "fear_greed.json"
    if sentiment_json.exists():
        try:
            with open(sentiment_json, "r", encoding="utf-8") as f:
                quant_data["sentiment"]["fear_greed"] = json.load(f)
        except Exception as e:
            logger.warning("Error reading %s: %s", sentiment_json, e)

    breadth_files = {
        "trin": raw_data_dir / "sentiment" / "trin.csv",
        "us_adl": raw_data_dir / "sentiment" / "us_adl.csv",
        "kr_trin": raw_data_dir / "sentiment" / "kr_trin.csv",
        "kr_adl": raw_data_dir / "sentiment" / "kr_adl.csv",
    }
    for key, filepath in breadth_files.items():
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                df.fillna("", inplace=True)
                for col in df.columns:
                    if col.lower() in ("date", "unnamed: 0"):
                        df.rename(columns={col: "date"}, inplace=True)
                        break
                quant_data["sentiment"][key] = df.to_dict(orient="records")
                logger.info(" - sentiment/%s: %d rows loaded", key, len(df))
            except Exception as e:
                logger.warning("Error reading %s: %s", filepath, e)

    # pytrends 키워드 트렌드 (월별/일별)
    for f in sorted((raw_data_dir / "sentiment").glob("pytrends_*.csv")):
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            df.index.name = "date"
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df.fillna("", inplace=True)
            quant_data["sentiment"][f.stem] = df.to_dict(orient="records")
            logger.info(" - sentiment/%s: %d rows", f.stem, len(df))
        except Exception as e:
            logger.warning("Error reading %s: %s", f, e)

    # NAVER DataLab 섹터 관심도
    naver_dir = raw_data_dir / "sentiment" / "naver_datalab"
    if naver_dir.exists():
        for f in sorted(naver_dir.glob("*.csv")):
            try:
                df = pd.read_csv(f)
                df.fillna("", inplace=True)
                quant_data["sentiment"][f"naver_{f.stem}"] = df.to_dict(orient="records")
                logger.info(" - sentiment/naver_datalab/%s: %d rows", f.stem, len(df))
            except Exception as e:
                logger.warning("Error reading %s: %s", f, e)

    # 퀀트 팩터 (data/raw/factors/) — 웹 대시보드가 직접 참조하는 관심도/레짐 파일만 선별 로드
    factors_dir = raw_data_dir / "factors"
    if factors_dir.exists():
        quant_data["sentiment"]["factors"] = {}
        factor_allowlist = {
            "market_macro_regime_month.csv",
            "regime_adjusted_sector_interest_month.csv",
            "regime_adjusted_factor_catalog.csv",
        }
        for f in sorted(p for p in factors_dir.glob("*.csv") if p.name in factor_allowlist):
            try:
                df = pd.read_csv(f)
                df.fillna("", inplace=True)
                quant_data["sentiment"]["factors"][f.stem] = df.to_dict(orient="records")
                logger.info(" - factors/%s: %d rows", f.stem, len(df))
            except Exception as e:
                logger.warning("Error reading %s: %s", f, e)

    # KRX 전종목 스냅샷 (stock_market_snapshot/) — 최신 날짜 파일만 로드
    if include_stock_detail:
        snap_dir = raw_data_dir / "stock_market_snapshot"
        if snap_dir.exists():
            snap_files = sorted(snap_dir.glob("*.csv"))
            # 날짜별로 그룹화해서 최신 날짜만 사용
            from collections import defaultdict
            date_groups: dict = defaultdict(list)
            import re as _re
            for f in snap_files:
                m = _re.search(r"(\d{8})\.csv$", f.name)
                if m:
                    date_groups[m.group(1)].append(f)
            if date_groups:
                latest_date = max(date_groups)
                for f in date_groups[latest_date]:
                    key = _re.sub(r"_\d{8}$", "", f.stem)  # 날짜 제거
                    try:
                        df = pd.read_csv(f, dtype=str)
                        df.fillna("", inplace=True)
                        quant_data["stock_detail"]["snapshots"][key] = df.to_dict(orient="records")
                        logger.info(" - stock_market_snapshot/%s: %d rows", key, len(df))
                    except Exception as e:
                        logger.warning("Error reading %s: %s", f, e)

    # 4. Valuation Data 추출
    for file in glob.glob(str(raw_data_dir / "valuation" / "*.csv")):
        name = Path(file).stem
        try:
            records = _records_from_csv(file, dtype={"ticker": str, "Code": str})
            if name == "earnings_consensus":
                for r in records:
                    t = str(r.get("ticker", "")).zfill(6)
                    r["ticker"] = t
                    r["corp_name"] = krx_dict.get(t, t)
            quant_data["valuation"][name] = records
        except Exception as e:
            logger.warning("Error reading %s: %s", file, e)

    # 5. Stock Detail Data 추출
    if include_stock_detail:
        stock_detail_dir = raw_data_dir / "stock_detail"
        if stock_detail_dir.exists():
            for file in sorted(stock_detail_dir.glob("*.csv")):
                key = file.stem
                try:
                    quant_data["stock_detail"]["snapshots"][key] = _records_from_csv(file, dtype={"ticker": str, "Code": str})
                except Exception as e:
                    logger.warning("Error reading %s: %s", file, e)

            for ticker_dir in sorted(p for p in stock_detail_dir.iterdir() if p.is_dir()):
                ticker = ticker_dir.name
                ticker_payload = {"name": krx_dict.get(ticker, ticker)}
                for file in sorted(ticker_dir.glob("*.csv")):
                    key = file.stem
                    try:
                        ticker_payload[key] = _records_from_csv(file)
                    except Exception as e:
                        logger.warning("Error reading %s: %s", file, e)
                if len(ticker_payload) > 1:
                    quant_data["stock_detail"]["tickers"][ticker] = ticker_payload

    # 6. 웹 검색/필터용 종목 시장 매력도 payload
    quant_data["stock_attractiveness"] = _build_stock_attractiveness(raw_data_dir, krx_dict)
    logger.info(
        " - stock_attractiveness: %d rows loaded",
        len(quant_data["stock_attractiveness"].get("rows", [])),
    )

    # 6-1. 회귀 분석 결과 (regression_* 테이블 → regression 키)
    quant_data["regression"] = _build_regression_summary(raw_data_dir)
    _inject_regime_scores(quant_data)
    logger.info(" - regression: signal=%s / regime=%s",
                quant_data["regression"].get("market_timing", {}).get("signal", "-"),
                quant_data["regression"].get("regime", {}).get("current_regime", "-"))
    # 6-2. 팩터 심사표 결과 (독립 검증 CSV → factor_validation 키)
    quant_data["factor_validation"] = _build_factor_validation(raw_data_dir)
    quant_data["factor_validation"]["topn_quintile"] = _build_factor_topn_quintile_backtest(raw_data_dir)
    logger.info(
        " - factor_validation: summary=%d / current_top=%d / topn_quintile=%d,%d",
        len(quant_data["factor_validation"].get("summary", [])),
        len(quant_data["factor_validation"].get("current_top", [])),
        len(quant_data["factor_validation"].get("topn_quintile", {}).get("topn_summary", [])),
        len(quant_data["factor_validation"].get("topn_quintile", {}).get("quintile_spread", [])),
    )

    # 7. 파생 거시지표 계산 (원본 CSV에서 직접 계산)
    _compute_derived_macro(quant_data, raw_data_dir, include_stock_detail=include_stock_detail)

    return quant_data


def export_to_web(raw_data_dir=None, web_dir=None, krx_dict=None, include_stock_detail=False):
    logger.info("=== 웹 대시보드 연동 JSON/JS 파일 생성 시작 ===")

    base_dir = Path(__file__).resolve().parent
    raw_data_dir = Path(raw_data_dir) if raw_data_dir is not None else (base_dir / ".." / ".." / "data" / "raw").resolve()
    web_dir = Path(web_dir) if web_dir is not None else (base_dir / ".." / ".." / "web").resolve()
    web_dir.mkdir(parents=True, exist_ok=True)

    quant_data = collect_quant_data(raw_data_dir, krx_dict=krx_dict, include_stock_detail=include_stock_detail)
    js_content = "window.QUANT_DATA = " + json.dumps(quant_data, ensure_ascii=False) + ";"

    output_path = web_dir / "quant_data.js"
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(js_content)

    logger.info(" - JS 파일 내보내기 완료: %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    export_to_web()

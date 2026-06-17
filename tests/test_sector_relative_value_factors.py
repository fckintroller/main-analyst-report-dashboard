import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "03_analyze" / "build_sector_relative_value_factors.py"
    spec = importlib.util.spec_from_file_location("sector_relative_value", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_panel(months=14):
    rows = []
    for mi in range(months):
        period = pd.Timestamp("2025-01-01") + pd.DateOffset(months=mi)
        for si, sector in enumerate(["A", "B"]):
            for i in range(6):
                ticker = f"{sector}{i}"
                per = 5 + i + si * 10 + mi * 0.1
                pbr = 0.5 + i * 0.2 + si * 1.0 + mi * 0.01
                roe = 0.05 + i * 0.02
                rows.append({
                    "ticker": ticker,
                    "period": period.strftime("%Y-%m-01"),
                    "sector": sector,
                    "PER": per,
                    "PBR": pbr,
                    "EPS": roe * 1000,
                    "BPS": 1000,
                    "roe": roe,
                    "roe_sector_pct_ts": (i + 1) / 6,
                    "per_percentile_sector": (i + 1) / 6,
                    "pbr_percentile_sector": (i + 1) / 6,
                    "valuation_score": 1 - (i + 1) / 6,
                    "valuation_bucket": "neutral",
                })
    return pd.DataFrame(rows)


def test_sector_relative_per_pbr_use_sector_median_not_market_median():
    mod = load_module()
    df = sample_panel(months=1)
    out = mod.add_sector_relative_multiples(df)
    a0 = out[out["ticker"] == "A0"].iloc[0]
    b0 = out[out["ticker"] == "B0"].iloc[0]
    assert a0["sector_median_per"] != b0["sector_median_per"]
    assert np.isclose(a0["sector_relative_per"], a0["PER"] / out[out["sector"] == "A"]["PER"].median())
    assert np.isclose(b0["sector_relative_pbr"], b0["PBR"] / out[out["sector"] == "B"]["PBR"].median())


def test_small_sector_is_nan_for_relative_metrics():
    mod = load_module()
    df = sample_panel(months=1).query("sector == 'A' and ticker in ['A0','A1','A2']").copy()
    out = mod.add_sector_relative_multiples(df)
    assert out["sector_relative_per"].isna().all()
    assert out["sector_relative_pbr"].isna().all()


def test_pbr_roe_adjusted_score_prefers_low_pbr_for_same_roe():
    mod = load_module()
    df = pd.DataFrame({
        "ticker": [f"T{i}" for i in range(6)],
        "period": ["2026-01-01"] * 6,
        "sector": ["A"] * 6,
        "PBR": [0.5, 0.8, 1.0, 1.5, 2.0, 3.0],
        "roe": [0.10] * 6,
    })
    out = mod.add_pbr_roe_adjusted(df)
    low = out[out["ticker"] == "T0"].iloc[0]
    high = out[out["ticker"] == "T5"].iloc[0]
    assert low["pbr_to_roe"] < high["pbr_to_roe"]
    assert low["pbr_roe_adjusted_score"] > high["pbr_roe_adjusted_score"]


def test_sector_value_zscore_available_after_min_history():
    mod = load_module()
    df = sample_panel(months=14)
    out = mod.add_sector_value_zscores(df)
    latest = out[out["period"] == out["period"].max()]
    assert latest["sector_value_zscore"].notna().all()
    assert set(latest["sector_value_bucket"].unique()) <= {"historically_cheap", "cheap", "neutral", "rich", "historically_rich", "N/A"}


def test_value_quality_score_combines_cheapness_and_roe_quality():
    mod = load_module()
    df = sample_panel(months=1)
    df = mod.add_sector_relative_multiples(df)
    df = mod.add_pbr_roe_adjusted(df)
    out = mod.add_value_quality_score(df)
    assert out["value_quality_score"].between(0, 1).all()
    high = out.sort_values("value_quality_score", ascending=False).iloc[0]
    assert high["value_quality_bucket"] in {"deep_value_quality", "value_quality", "neutral"}


def test_financial_quality_snapshot_prefers_low_debt_and_positive_fcf():
    mod = load_module()
    raw = pd.DataFrame([
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "current_liabilities", "amount": 100},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "noncurrent_liabilities", "amount": 100},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "total_equity", "amount": 800},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "cfo", "amount": 120},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "capex", "amount": -30},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "current_liabilities", "amount": 500},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "noncurrent_liabilities", "amount": 200},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "total_equity", "amount": 300},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "cfo", "amount": 40},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "capex", "amount": 80},
    ])
    out = mod.build_dart_financial_quality_snapshot(raw, {"000001": "A", "000002": "A"})
    strong = out[out["ticker"] == "000001"].iloc[0]
    weak = out[out["ticker"] == "000002"].iloc[0]
    assert np.isclose(strong["debt_ratio"], 0.25)
    assert np.isclose(strong["fcf"], 90)
    assert np.isclose(weak["fcf"], -40)
    assert strong["debt_ratio_score"] > weak["debt_ratio_score"]
    assert strong["fcf_to_assets_score"] > weak["fcf_to_assets_score"]
    assert strong["financial_quality_score"] > weak["financial_quality_score"]


def test_balance_sheet_quality_outputs_user_requested_metrics():
    mod = load_module()
    raw = pd.DataFrame([
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "current_assets", "amount": 400},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "current_liabilities", "amount": 100},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "noncurrent_liabilities", "amount": 100},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "total_equity", "amount": 800},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "capital_stock", "amount": 500},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "cash", "amount": 120},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "operating_income", "amount": 100},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "interest_expense", "amount": 10},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "current_assets", "amount": 150},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "current_liabilities", "amount": 300},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "noncurrent_liabilities", "amount": 400},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "total_equity", "amount": 300},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "capital_stock", "amount": 500},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "cash", "amount": 50},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "operating_income", "amount": 20},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "interest_expense", "amount": 40},
    ])
    out = mod.build_dart_financial_quality_snapshot(raw, {"000001": "A", "000002": "A"})
    strong = out[out["ticker"] == "000001"].iloc[0]
    weak = out[out["ticker"] == "000002"].iloc[0]
    assert np.isclose(strong["debt_to_equity"], 0.25)
    assert np.isclose(strong["net_debt_to_ebitda"], 0.8)
    assert np.isclose(strong["interest_coverage"], 10.0)
    assert np.isclose(strong["current_ratio"], 4.0)
    assert strong["equity_impairment_flag"] == 0
    assert weak["equity_impairment_flag"] == 1
    assert strong["balance_sheet_quality_score"] > weak["balance_sheet_quality_score"]


def test_cashflow_quality_outputs_user_requested_metrics():
    mod = load_module()
    raw = pd.DataFrame([
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "revenue", "amount": 1000},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "net_income", "amount": 80},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "cfo", "amount": 120},
        {"ticker": "000001", "bsns_year": 2024, "period": "current", "account_id": "capex", "amount": -20},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "total_assets", "amount": 1000},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "revenue", "amount": 1000},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "net_income", "amount": 120},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "cfo", "amount": 30},
        {"ticker": "000002", "bsns_year": 2024, "period": "current", "account_id": "capex", "amount": 60},
    ])
    out = mod.build_dart_financial_quality_snapshot(raw, {"000001": "A", "000002": "A"}, market_cap_map={"000001": 2000, "000002": 2000})
    strong = out[out["ticker"] == "000001"].iloc[0]
    weak = out[out["ticker"] == "000002"].iloc[0]
    assert strong["operating_cashflow_positive"] == 1
    assert np.isclose(strong["fcf_margin"], 0.10)
    assert np.isclose(strong["fcf_yield"], 0.05)
    assert np.isclose(strong["accrual_ratio"], -0.04)
    assert np.isclose(strong["cash_conversion"], 1.5)
    assert weak["operating_cashflow_positive"] == 1
    assert weak["fcf_margin"] < 0
    assert strong["cashflow_quality_score"] > weak["cashflow_quality_score"]


def test_earnings_stability_prefers_stable_growth_and_profitability():
    mod = load_module()
    rows = []
    for ticker, revenue, op_income, net_income, equity in [
        ("000001", [1000, 950, 900], [100, 95, 90], [80, 76, 72], [800, 780, 760]),
        ("000002", [1000, 600, 1200], [120, -50, 200], [90, -40, 150], [500, 520, 480]),
    ]:
        for period, rev, op, ni, eq in zip(["current", "prior", "prior2"], revenue, op_income, net_income, equity):
            rows.extend([
                {"ticker": ticker, "bsns_year": 2024, "period": period, "account_id": "revenue", "amount": rev},
                {"ticker": ticker, "bsns_year": 2024, "period": period, "account_id": "operating_income", "amount": op},
                {"ticker": ticker, "bsns_year": 2024, "period": period, "account_id": "net_income", "amount": ni},
                {"ticker": ticker, "bsns_year": 2024, "period": period, "account_id": "total_equity", "amount": eq},
            ])
    out = mod.build_dart_financial_quality_snapshot(pd.DataFrame(rows), {"000001": "A", "000002": "A"})
    stable = out[out["ticker"] == "000001"].iloc[0]
    volatile = out[out["ticker"] == "000002"].iloc[0]
    assert stable["revenue_yoy_stability"] > volatile["revenue_yoy_stability"]
    assert stable["op_margin_volatility"] < volatile["op_margin_volatility"]
    assert stable["net_loss_count"] == 0
    assert volatile["net_loss_count"] == 1
    assert stable["roe_volatility"] < volatile["roe_volatility"]
    assert stable["earnings_stability_score"] > volatile["earnings_stability_score"]


def test_value_quality_score_includes_debt_and_fcf_when_available():
    mod = load_module()
    df = sample_panel(months=1)
    df = mod.add_sector_relative_multiples(df)
    df = mod.add_pbr_roe_adjusted(df)
    df["debt_ratio_score"] = 0.5
    df["fcf_to_assets_score"] = 0.5
    target = df.index[0]
    df.loc[target, ["debt_ratio_score", "fcf_to_assets_score"]] = [1.0, 1.0]
    base = mod.add_value_quality_score(df.drop(columns=["debt_ratio_score", "fcf_to_assets_score"]))
    enriched = mod.add_value_quality_score(df)
    assert enriched.loc[target, "quality_source"] == "valuation_roe_debt_fcf"
    assert enriched.loc[target, "value_quality_score"] > base.loc[target, "value_quality_score"]


def test_catalog_maps_requested_numbers():
    mod = load_module()
    cat = mod.build_catalog()
    assert {"1", "2", "3", "5", "6", "debt_fcf", "38", "39", "40"}.issubset(set(cat["requested_no"]))
    assert {
        "sector_relative_per", "sector_relative_pbr", "value_quality_score", "sector_value_zscore",
        "debt_ratio", "fcf_to_assets", "debt_to_equity", "net_debt_to_ebitda",
        "interest_coverage", "current_ratio", "equity_impairment_flag", "balance_sheet_quality_score",
        "operating_cashflow_positive", "fcf_margin", "fcf_yield", "accrual_ratio", "cash_conversion",
        "cashflow_quality_score", "revenue_yoy_stability", "op_margin_volatility", "net_loss_count",
        "roe_volatility", "earnings_stability_score",
    }.issubset(set(cat["factor_name"]))

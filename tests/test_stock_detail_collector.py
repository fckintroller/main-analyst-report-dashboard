import importlib.util
import sys
from pathlib import Path

import pandas as pd


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_build_universe_uses_financedatareader_listing_when_pykrx_is_unavailable(monkeypatch):
    project = Path(__file__).resolve().parents[1]
    mod = load_module(project / "scripts" / "01_collect" / "06_stock_detail.py", "stock_detail_test")

    def fail(*args, **kwargs):
        raise RuntimeError("pykrx unavailable")

    monkeypatch.setattr(mod.stock, "get_index_portfolio_deposit_file", fail)
    monkeypatch.setattr(mod.stock, "get_market_cap_by_ticker", fail)
    monkeypatch.setattr(mod.stock, "get_market_ticker_name", lambda ticker: ticker)

    def fake_listing(market):
        if market == "KOSPI":
            return pd.DataFrame([
                {"Code": "000001", "Name": "낮은시총", "Marcap": 1},
                {"Code": "005930", "Name": "삼성전자", "Marcap": 100},
            ])
        if market == "KOSDAQ":
            return pd.DataFrame([
                {"Code": "035720", "Name": "카카오", "Marcap": 50},
            ])
        raise AssertionError(market)

    monkeypatch.setattr(mod.fdr, "StockListing", fake_listing)

    universe = mod.build_universe("20260603")

    assert universe == {
        "005930": "삼성전자",
        "000001": "낮은시총",
        "035720": "카카오",
    }
    assert mod.PYKRX_DETAIL_AVAILABLE is False

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_export_to_web_includes_stock_detail_ticker_series_and_snapshots(tmp_path):
    project = Path(__file__).resolve().parents[1]
    export_web_data = load_module(project / "scripts" / "03_analyze" / "export_web_data.py", "export_web_data_test")

    raw = tmp_path / "raw"
    web = tmp_path / "web"
    ticker_dir = raw / "stock_detail" / "005930"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "ohlcv.csv").write_text("Date,Close,Volume\n2026-06-01,70000,1000\n", encoding="utf-8-sig")
    (ticker_dir / "fundamental.csv").write_text("Date,PER,PBR\n2026-06-01,12.3,1.1\n", encoding="utf-8-sig")
    (raw / "stock_detail" / "sector_map.csv").write_text("ticker,name,sector\n005930,삼성전자,반도체\n", encoding="utf-8-sig")

    output_path = export_web_data.export_to_web(raw_data_dir=raw, web_dir=web, krx_dict={"005930": "삼성전자"})

    payload = (Path(output_path).read_text(encoding="utf-8-sig")
        .removeprefix("window.QUANT_DATA = ")
        .removesuffix(";"))
    data = json.loads(payload)
    assert "stock_detail" in data
    assert data["stock_detail"]["tickers"]["005930"]["name"] == "삼성전자"
    assert data["stock_detail"]["tickers"]["005930"]["ohlcv"][0]["Close"] == 70000
    assert data["stock_detail"]["tickers"]["005930"]["fundamental"][0]["PER"] == 12.3
    assert data["stock_detail"]["snapshots"]["sector_map"][0]["sector"] == "반도체"


def test_load_to_db_loads_nested_stock_detail_tables_with_unique_names(tmp_path):
    project = Path(__file__).resolve().parents[1]
    load_to_db = load_module(project / "scripts" / "02_store" / "load_to_db.py", "load_to_db_test")

    raw = tmp_path / "raw"
    db_path = tmp_path / "quant_data.sqlite"
    ticker_dir = raw / "stock_detail" / "005930"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "ohlcv.csv").write_text("Date,Close\n2026-06-01,70000\n", encoding="utf-8-sig")
    (raw / "stock_detail" / "sector_map.csv").write_text("ticker,name,sector\n005930,삼성전자,반도체\n", encoding="utf-8-sig")

    loaded = load_to_db.load_csv_to_sqlite(raw_dir=raw, db_path=db_path)

    assert loaded == 2
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    assert "stock_detail_005930_ohlcv" in tables
    assert "stock_detail_sector_map" in tables
    assert conn.execute('select Close from stock_detail_005930_ohlcv').fetchone()[0] == 70000
    conn.close()

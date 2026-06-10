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


def _compute_derived_macro(quant_data, raw_data_dir):
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

    # ── 11. KOSPI 시총가중 PBR (개별 종목 fundamental에서 계산) ───────────
    # pykrx KRX 인증 없이 사용 가능한 폴백: stock_detail 수집 데이터 활용
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


def collect_quant_data(raw_data_dir, krx_dict=None):
    raw_data_dir = Path(raw_data_dir)
    krx_dict = krx_dict if krx_dict is not None else _load_krx_names()

    quant_data = {
        "macro": {},
        "money_flow": {},
        "sentiment": {},
        "valuation": {},
        "stock_detail": {"tickers": {}, "snapshots": {}},
    }

    # 1. Macro Data 추출
    for file in glob.glob(str(raw_data_dir / "macro" / "**" / "*.csv"), recursive=True):
        name = Path(file).stem
        try:
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

    # 퀀트 팩터 (data/raw/factors/) — regime, regime_adjusted 등
    factors_dir = raw_data_dir / "factors"
    if factors_dir.exists():
        quant_data["sentiment"]["factors"] = {}
        for f in sorted(factors_dir.glob("*.csv")):
            try:
                df = pd.read_csv(f)
                df.fillna("", inplace=True)
                quant_data["sentiment"]["factors"][f.stem] = df.to_dict(orient="records")
                logger.info(" - factors/%s: %d rows", f.stem, len(df))
            except Exception as e:
                logger.warning("Error reading %s: %s", f, e)

    # KRX 전종목 스냅샷 (stock_market_snapshot/) — 최신 날짜 파일만 로드
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

    # 6. 파생 거시지표 계산 (원본 CSV에서 직접 계산)
    _compute_derived_macro(quant_data, raw_data_dir)

    return quant_data


def export_to_web(raw_data_dir=None, web_dir=None, krx_dict=None):
    logger.info("=== 웹 대시보드 연동 JSON/JS 파일 생성 시작 ===")

    base_dir = Path(__file__).resolve().parent
    raw_data_dir = Path(raw_data_dir) if raw_data_dir is not None else (base_dir / ".." / ".." / "data" / "raw").resolve()
    web_dir = Path(web_dir) if web_dir is not None else (base_dir / ".." / ".." / "web").resolve()
    web_dir.mkdir(parents=True, exist_ok=True)

    quant_data = collect_quant_data(raw_data_dir, krx_dict=krx_dict)
    js_content = "window.QUANT_DATA = " + json.dumps(quant_data, ensure_ascii=False) + ";"

    output_path = web_dir / "quant_data.js"
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(js_content)

    logger.info(" - JS 파일 내보내기 완료: %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    export_to_web()

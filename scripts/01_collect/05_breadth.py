"""
05_breadth.py — 미국/한국 TRIN & ADL 수집

[미국]
  - TRIN : Stooq trin.us (NYSE Arms Index)
  - ADL  : Stooq ^nyad  (NYSE Cumulative Advance-Decline Line)

[한국]
  - ADL + TRIN : pykrx get_market_ohlcv_by_ticker로 단일 패스 산출 (KRX API 정상 시)
                 KRX API 야간 점검 중이면 FinanceDataReader(Naver Finance) 폴백
    TRIN = (Adv종목수 / Dec종목수) / (Adv거래량 / Dec거래량)
"""

import datetime
import io
import logging
import os
import time

import FinanceDataReader as fdr
import pandas as pd
import requests
from pykrx import stock

logger = logging.getLogger(__name__)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "sentiment")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


# ─────────────────────────────────────────────
# 미국 TRIN  (Stooq — trin.us)
# ─────────────────────────────────────────────
def fetch_us_trin(years=10):
    logger.info("[US TRIN] downloading trin.us (stooq, %dy) ...", years)
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=years * 365)
        url = (
            f"https://stooq.com/q/d/l/?s=trin.us"
            f"&d1={start.strftime('%Y%m%d')}&d2={end.strftime('%Y%m%d')}&i=d"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        header_idx = next((i for i, l in enumerate(lines) if l.startswith("Date")), None)
        if header_idx is None:
            logger.warning(" - trin.us: no CSV header found (stooq)")
            return
        df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
        if df.empty or "Close" not in df.columns:
            logger.warning(" - trin.us returned empty (stooq)")
            return
        df = df[["Date", "Close"]].rename(columns={"Date": "date", "Close": "trin"})
        df = df.dropna().sort_values("date")
        out = os.path.join(BASE_DIR, "trin.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        logger.info(" - US TRIN saved: %s rows → %s", len(df), out)
    except Exception as e:
        logger.error(" - US TRIN FAILED: %s", e)


# ─────────────────────────────────────────────
# 미국 ADL  (Stooq — ^nyad)
# ─────────────────────────────────────────────
def fetch_us_adl(years=10):
    logger.info("[US ADL] downloading ^nyad (stooq, %dy) ...", years)
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=years * 365)
        url = (
            f"https://stooq.com/q/d/l/?s=%5Enyad"
            f"&d1={start.strftime('%Y%m%d')}&d2={end.strftime('%Y%m%d')}&i=d"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        header_idx = next((i for i, l in enumerate(lines) if l.startswith("Date")), None)
        if header_idx is None:
            logger.warning(" - ^nyad: no CSV header found (stooq)")
            return
        df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
        if df.empty or "Close" not in df.columns:
            logger.warning(" - ^nyad returned empty (stooq)")
            return
        df = df[["Date", "Close"]].rename(columns={"Date": "date"})
        df = df.dropna().sort_values("date")
        out = os.path.join(BASE_DIR, "us_adl.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        logger.info(" - US ADL saved: %s rows → %s", len(df), out)
    except Exception as e:
        logger.error(" - US ADL FAILED: %s", e)


# ─────────────────────────────────────────────
# 한국 ADL + TRIN  — FinanceDataReader 폴백
# KRX API 야간 점검 시 Naver Finance 백엔드로 수집
# ─────────────────────────────────────────────
def _fetch_kr_breadth_fdr(lookback_days=730):
    logger.info("[KR-FDR] fetching KOSPI breadth via FinanceDataReader (%dd) ...", lookback_days)
    try:
        today      = datetime.date.today()
        start_str  = (today - datetime.timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end_str    = today.strftime("%Y-%m-%d")

        listing = fdr.StockListing("KOSPI")
        tickers = listing["Code"].dropna().tolist()
        logger.info(" - KOSPI tickers: %d", len(tickers))

        # date → {adv, dec, unch, adv_vol, dec_vol}
        day_map: dict = {}

        for i, ticker in enumerate(tickers):
            try:
                df = fdr.DataReader(ticker, start_str, end_str)
                if df.empty or "Change" not in df.columns:
                    continue
                vol_col = "Volume" if "Volume" in df.columns else None
                for dt, row in df.iterrows():
                    d = dt.strftime("%Y-%m-%d")
                    if d not in day_map:
                        day_map[d] = {"adv": 0, "dec": 0, "unch": 0, "adv_vol": 0, "dec_vol": 0}
                    chg = float(row["Change"]) if pd.notna(row["Change"]) else 0.0
                    vol = int(row[vol_col]) if (vol_col and pd.notna(row[vol_col])) else 0
                    if chg > 0:
                        day_map[d]["adv"]     += 1
                        day_map[d]["adv_vol"] += vol
                    elif chg < 0:
                        day_map[d]["dec"]     += 1
                        day_map[d]["dec_vol"] += vol
                    else:
                        day_map[d]["unch"] += 1
            except Exception:
                pass

            if (i + 1) % 50 == 0:
                logger.info(" - processed %d / %d tickers", i + 1, len(tickers))

        if not day_map:
            logger.warning(" - KR-FDR: no data collected")
            return

        adl_rows  = []
        trin_rows = []
        adl_cum   = 0

        for date_str in sorted(day_map):
            d = day_map[date_str]
            adv, dec, unch = d["adv"], d["dec"], d["unch"]
            adv_vol, dec_vol = d["adv_vol"], d["dec_vol"]
            adl_cum += adv - dec

            adl_rows.append({
                "date": date_str, "advancing": adv,
                "declining": dec, "unchanged": unch,
                "adl_cumulative": adl_cum,
            })

            trin = None
            if dec > 0 and dec_vol > 0:
                trin = round((adv / dec) / (adv_vol / dec_vol), 4)

            trin_rows.append({
                "date":       date_str,
                "advancing":  adv,
                "declining":  dec,
                "adv_volume": adv_vol,
                "dec_volume": dec_vol,
                "trin":       trin,
                "signal":     ("Bullish" if trin and trin < 0.85
                               else "Bearish" if trin and trin > 1.25
                               else "Neutral"),
            })

        pd.DataFrame(adl_rows).to_csv(
            os.path.join(BASE_DIR, "kr_adl.csv"), index=False, encoding="utf-8-sig")
        logger.info(" - KR ADL saved: %d rows", len(adl_rows))

        pd.DataFrame(trin_rows).to_csv(
            os.path.join(BASE_DIR, "kr_trin.csv"), index=False, encoding="utf-8-sig")
        logger.info(" - KR TRIN saved: %d rows", len(trin_rows))

    except Exception as e:
        logger.error(" - KR-FDR FAILED: %s", e)


# ─────────────────────────────────────────────
# 한국 ADL + TRIN  (pykrx 단일 패스, FDR 폴백)
# ─────────────────────────────────────────────
def fetch_kr_breadth(lookback_days=730):
    """
    KRX API 정상 시: pykrx get_market_ohlcv_by_ticker로 단일 패스 산출.
    KRX API 야간 점검 시: FinanceDataReader(Naver Finance) 폴백.
    """
    logger.info("[KR] fetching KOSPI breadth (ADL+TRIN, past %dd) ...", lookback_days)
    logging.getLogger("pykrx").setLevel(logging.CRITICAL)
    try:
        today      = datetime.date.today()
        start_date = today - datetime.timedelta(days=lookback_days)
        end_date   = today
        start = start_date.strftime("%Y%m%d")
        end   = end_date.strftime("%Y%m%d")

        # KRX API 가용성 사전 체크
        probe_date = (today - datetime.timedelta(days=7)).strftime("%Y%m%d")
        krx_ok = False
        try:
            probe = stock.get_market_ohlcv_by_ticker(probe_date, market="KOSPI")
            krx_ok = not probe.empty
        except Exception:
            pass

        if not krx_ok:
            logger.warning("[KR] KRX API offline — using FinanceDataReader fallback")
            _fetch_kr_breadth_fdr(lookback_days)
            return

        # 실제 KRX 영업일 목록
        try:
            kospi_idx    = stock.get_index_ohlcv_by_date(start, end, "1001")
            trading_days = list(kospi_idx.index)
            logger.info(" - trading days from KRX index: %d", len(trading_days))
        except Exception as idx_err:
            logger.warning(" - get_index_ohlcv_by_date failed (%s), using bdate_range", idx_err)
            trading_days = list(pd.bdate_range(str(start_date), str(end_date)))

        trin_rows = []
        adl_rows  = []
        adl_cum   = 0

        for bd in trading_days:
            ds = bd.strftime("%Y%m%d")
            try:
                df = stock.get_market_ohlcv_by_ticker(ds, market="KOSPI")
                if df.empty:
                    continue

                change_col = next((c for c in df.columns if "등락" in c), None)
                vol_col    = next((c for c in df.columns if "거래량" in c), None)
                if not change_col or not vol_col:
                    continue

                adv_n   = int((df[change_col] > 0).sum())
                dec_n   = int((df[change_col] < 0).sum())
                unch_n  = int((df[change_col] == 0).sum())
                adv_vol = int(df.loc[df[change_col] > 0, vol_col].sum())
                dec_vol = int(df.loc[df[change_col] < 0, vol_col].sum())
                adl_cum += adv_n - dec_n

                date_str = bd.strftime("%Y-%m-%d")
                adl_rows.append({
                    "date": date_str, "advancing": adv_n,
                    "declining": dec_n, "unchanged": unch_n,
                    "adl_cumulative": adl_cum,
                })

                trin = None
                if dec_n > 0 and dec_vol > 0:
                    trin = round((adv_n / dec_n) / (adv_vol / dec_vol), 4)

                trin_rows.append({
                    "date":       date_str,
                    "advancing":  adv_n,
                    "declining":  dec_n,
                    "adv_volume": adv_vol,
                    "dec_volume": dec_vol,
                    "trin":       trin,
                    "signal":     ("Bullish" if trin and trin < 0.85
                                   else "Bearish" if trin and trin > 1.25
                                   else "Neutral"),
                })
            except Exception:
                pass
            time.sleep(0.5)

        if adl_rows:
            out = os.path.join(BASE_DIR, "kr_adl.csv")
            pd.DataFrame(adl_rows).to_csv(out, index=False, encoding="utf-8-sig")
            logger.info(" - KR ADL saved: %d rows → %s", len(adl_rows), out)
        else:
            logger.warning(" - KR ADL: no data collected")

        if trin_rows:
            out = os.path.join(BASE_DIR, "kr_trin.csv")
            pd.DataFrame(trin_rows).to_csv(out, index=False, encoding="utf-8-sig")
            logger.info(" - KR TRIN saved: %d rows → %s", len(trin_rows), out)
        else:
            logger.warning(" - KR TRIN: no data collected")

    except Exception as e:
        logger.error(" - KR breadth FAILED: %s", e)


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────
def run():
    logger.info("=== 05. Breadth Indicators (TRIN/ADL) collection started ===")
    ensure_dir(BASE_DIR)
    fetch_us_trin()
    fetch_us_adl()
    fetch_kr_breadth()
    logger.info("=== 05. Breadth Indicators collection finished ===")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run()

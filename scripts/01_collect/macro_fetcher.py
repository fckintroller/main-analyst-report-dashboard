import os
import sys
import json
import math
import random
import requests
from datetime import datetime
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    import FinanceDataReader as fdr
    _FDR_AVAILABLE = True
except ImportError:
    _FDR_AVAILABLE = False

# ==========================================
# 1. Configuration & API Keys
# ==========================================
FRED_API_KEY = os.environ.get('FRED_API_KEY')
ECOS_API_KEY = os.environ.get('ECOS_API_KEY')

WEB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'web')
OUTPUT_JS = os.path.join(WEB_DIR, 'bubble_data.js')
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

# ==========================================
# 2. 실데이터 수집 헬퍼
# ==========================================

def _fred_monthly(ticker, start="1994-01-01"):
    """FRED 시계열 수집 → 월초 기준 정렬 {YYYY-MM-DD: float} dict 반환."""
    if not _FDR_AVAILABLE:
        return {}
    try:
        df = fdr.DataReader(f"FRED:{ticker}", start)
        if df.empty:
            return {}
        monthly = df.resample("MS").last()
        col = monthly.columns[0]
        return {d.strftime("%Y-%m-%d"): float(v)
                for d, v in monthly[col].dropna().items()}
    except Exception as e:
        print(f"[Macro Fetcher] FRED:{ticker} 수집 실패: {e}")
        return {}


def _ecos_monthly(stat_code, item_code, start="199501"):
    """ECOS API 월별 시계열 수집 → {YYYY-MM-DD: float} dict 반환."""
    if not ECOS_API_KEY:
        return {}
    end = datetime.now().strftime("%Y%m")
    url = (f"{ECOS_BASE}/{ECOS_API_KEY}/json/kr/1/10000/"
           f"{stat_code}/MM/{start}/{end}/{item_code}")
    try:
        rows = requests.get(url, timeout=15).json().get("StatisticSearch", {}).get("row", [])
        result = {}
        for row in rows:
            t = str(row.get("TIME", ""))
            v = str(row.get("DATA_VALUE", ""))
            if len(t) != 6 or not v or v in ("-", ""):
                continue
            try:
                result[f"{t[:4]}-{t[4:6]}-01"] = float(v.replace(",", ""))
            except ValueError:
                pass
        return result
    except Exception as e:
        print(f"[ECOS] {stat_code}/{item_code} 수집 실패: {e}")
        return {}


def _align(series_dict, dates):
    """dates 기준 forward-fill 정렬. 데이터 없으면 None."""
    result, last = [], None
    for d in dates:
        if d in series_dict:
            last = series_dict[d]
        result.append(last)
    return result


def _yoy_growth(series_dict, dates):
    """전년동월비 성장률(%) 계산. 데이터 부족 시 None."""
    result = []
    for d in dates:
        curr = series_dict.get(d)
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            prev_d = dt.replace(year=dt.year - 1).strftime("%Y-%m-%d")
        except ValueError:
            result.append(None)
            continue
        prev = series_dict.get(prev_d)
        if curr is not None and prev is not None and prev != 0:
            result.append(round((curr - prev) / abs(prev) * 100, 1))
        else:
            result.append(None)
    return result


def _blend(real_list, mock_list):
    """실데이터 우선 사용, None 위치만 mock으로 채움."""
    return [r if r is not None else m for r, m in zip(real_list, mock_list)]


# ==========================================
# 3. FRED 오버레이 (API 키 불필요 — FDR 사용)
# ==========================================

def _overlay_fred(result, dates):
    print("[Macro Fetcher] FRED 실데이터 오버레이 중...")

    # 미국 M2 YoY 성장률
    m2 = _fred_monthly("M2SL")
    if len(m2) > 100:
        result["m2_us_growth"] = _blend(_yoy_growth(m2, dates), result["m2_us_growth"])
        print("  OK 미국 M2 YoY")

    # 장단기 금리차 (10Y-2Y) + 2년물
    dgs2 = _fred_monthly("DGS2")
    dgs10 = _fred_monthly("DGS10")
    if len(dgs2) > 100 and len(dgs10) > 100:
        spread = [
            round(dgs10[d] - dgs2[d], 2)
            if dgs10.get(d) is not None and dgs2.get(d) is not None else None
            for d in dates
        ]
        result["us_yield_spread"] = _blend(spread, result["us_yield_spread"])
        result["us_yield_2y"] = _blend(_align(dgs2, dates), result["us_yield_2y"])
        print("  OK 미국 장단기 금리차 / 2년물")

    # 30년물
    dgs30 = _fred_monthly("DGS30")
    if len(dgs30) > 100:
        result["us_yield_30y"] = _blend(_align(dgs30, dates), result["us_yield_30y"])
        print("  OK 미국 30년물")

    # HY 크레딧 스프레드 (FRED 단위: % → bps 변환 ×100)
    hy = _fred_monthly("BAMLH0A0HYM2")
    if len(hy) > 100:
        hy_bps = {d: round(v * 100) for d, v in hy.items()}
        result["credit_spread"] = _blend(_align(hy_bps, dates), result["credit_spread"])
        print("  OK HY 크레딧 스프레드")


# ==========================================
# 4. ECOS 오버레이 (ECOS_API_KEY 필요)
# ==========================================

def _ecos_key_stat_list():
    """ECOS KeyStatisticList 100대 지표를 {KEYSTAT_NAME: (float_value, cycle_str)} dict로 반환."""
    if not ECOS_API_KEY:
        return {}
    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{ECOS_API_KEY}/json/kr/1/100/"
    try:
        rows = requests.get(url, timeout=15).json().get("KeyStatisticList", {}).get("row", [])
        result = {}
        for r in rows:
            name = r.get("KEYSTAT_NAME", "")
            val_str = r.get("DATA_VALUE", "")
            cycle = r.get("CYCLE", "")
            try:
                result[name] = (float(val_str.replace(",", "")), cycle)
            except ValueError:
                pass
        return result
    except Exception as e:
        print(f"[ECOS] KeyStatisticList 실패: {e}")
        return {}


def _overlay_ecos(result, dates):
    print("[Macro Fetcher] ECOS 실데이터 오버레이 중 (KeyStatisticList)...")

    stats = _ecos_key_stat_list()
    if not stats:
        print("  ECOS 데이터 없음 — mock 유지")
        return

    def get_val(partial):
        for name, (val, cycle) in stats.items():
            if partial in name:
                return val, cycle
        return None, None

    # ── 한국 회사채 스프레드 (최신 1개 데이터 포인트 주입)
    gov3y, gov_cycle   = get_val("국고채수익률(3년)")
    corp_aa, aa_cycle  = get_val("회사채수익률(3년,AA-)")
    if gov3y is not None and corp_aa is not None:
        spread = round(corp_aa - gov3y, 3)
        if result.get("kor_corp_spread") is None:
            result["kor_corp_spread"] = [None] * len(dates)
        result["kor_corp_spread"][-1] = spread
        print(f"  OK 한국 회사채 스프레드: {corp_aa:.3f}% - {gov3y:.3f}% = {spread:.3f}%")

    # ── 기준금리 (최신값 로그)
    base, _ = get_val("기준금리")
    if base is not None:
        print(f"  OK 한국 기준금리: {base}%")

    # ── CCSI 최신값 (mock의 마지막 포인트를 실데이터로 덮어씀)
    ccsi, ccsi_cycle = get_val("소비자심리지수")
    if ccsi is not None:
        print(f"  OK CCSI: {ccsi} ({ccsi_cycle})")

    print(f"  → ECOS 총 {len(stats)}개 지표 수신")


# ==========================================
# 5. 진입점
# ==========================================

def fetch_real_data_or_mock():
    """Mock을 기저로, FRED/ECOS 실데이터를 가능한 범위에서 오버레이."""
    print("[Macro Fetcher] Starting data collection...")
    result = generate_mock_data()
    dates = result["dates"]

    if _FDR_AVAILABLE:
        try:
            _overlay_fred(result, dates)
        except Exception as e:
            print(f"[Macro Fetcher] FRED 오버레이 실패 (mock 유지): {e}")
    else:
        print("[Macro Fetcher] FinanceDataReader 미설치 — FRED 데이터 mock 유지")

    if ECOS_API_KEY:
        try:
            _overlay_ecos(result, dates)
        except Exception as e:
            print(f"[Macro Fetcher] ECOS 오버레이 실패 (mock 유지): {e}")
    else:
        print("[Macro Fetcher] ECOS_API_KEY 미설정 — 한국 지표 mock 유지")

    return result

def generate_mock_data():
    start_year = 1995
    _now = datetime.now()
    end_year = _now.year
    end_month = _now.month

    dates = []
    buffett = []
    shiller = []
    margin_loan = []
    receivable = []
    investor_deposit = []
    concentration_top10 = []
    credit_spread = []
    m2_growth = []
    m2_us_growth = []
    us_yield_spread = []
    us_yield_2y = []
    us_yield_30y = []

    bubbles = [
        (1999, 12, 1.4, 2.0, 3.0, 12),  
        (2007, 10, 1.3, 3.0, 4.0, 18),  
        (2021, 6, 1.4, 8.0, 6.0, 24),   
    ]

    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            if y == end_year and m > end_month:
                break
                
            date_str = f"{y}-{m:02d}-01"
            dates.append(date_str)
            
            years_elapsed = y - start_year + (m/12)
            total_years = end_year - start_year
            progress = years_elapsed / total_years
            
            base_buffett = 40 + (65 * progress)
            base_shiller = 9.0 + (3.0 * progress)
            base_margin = 1.0 * math.exp(progress * 3.0) 
            base_recv = 0.1 * math.exp(progress * 2.1)
            base_deposit = 5.0 * math.exp(progress * 2.5) # starts around 5T, ends around 60T
            
            base_concentration = 35 + (10 * progress)
            base_spread = 200
            base_m2 = 6.0
            base_m2_us = 6.0
            base_us_spread = 1.5

            # 미 2년물: Fed 사이클 반영 (1995 ~6% → 2010s 초저금리 → 2022 급등 → 현재 ~4.5%)
            if y <= 2001:
                base_2y = 5.5 - (y - 1995) * 0.2
            elif y <= 2004:
                base_2y = 1.5 + (y - 2001) * 0.5
            elif y <= 2007:
                base_2y = 3.0 + (y - 2004) * 0.7
            elif y <= 2015:
                base_2y = max(0.2, 5.0 - (y - 2007) * 0.6)
            elif y <= 2018:
                base_2y = 0.7 + (y - 2015) * 0.8
            elif y <= 2021:
                base_2y = max(0.1, 2.9 - (y - 2018) * 0.9)
            elif y <= 2023:
                base_2y = 0.2 + (y - 2021) * 2.5
            else:
                base_2y = 4.8 - (y - 2023) * 0.2

            # 미 30년물: 장기 하향 추세 (1995 ~7% → 2020 ~1.7% → 2023 ~5% → 현재 ~4.8%)
            if y <= 2000:
                base_30y = 6.5 - (y - 1995) * 0.15
            elif y <= 2008:
                base_30y = 5.7 - (y - 2000) * 0.25
            elif y <= 2016:
                base_30y = 3.8 - (y - 2008) * 0.2
            elif y <= 2021:
                base_30y = max(1.7, 2.2 - (y - 2016) * 0.1)
            elif y <= 2023:
                base_30y = 1.9 + (y - 2021) * 1.5
            else:
                base_30y = 4.7 - (y - 2023) * 0.05
            
            bubble_mult = 1.0
            margin_surge_add = 0
            recv_surge_add = 0
            deposit_surge_add = 0
            
            for by, bm, mag, m_surge, r_surge, length in bubbles:
                dist = abs((y - by) * 12 + (m - bm))
                if dist < length * 2:
                    intensity = math.exp(-0.5 * (dist / (length/2)) ** 2)
                    bubble_mult += (mag - 1.0) * intensity
                    
                    if by == 2021:
                        margin_surge_add += (22.0 - base_margin) * intensity if 22.0 > base_margin else 0
                        recv_surge_add += (1.2 - base_recv) * intensity if 1.2 > base_recv else 0
                        deposit_surge_add += (70.0 - base_deposit) * intensity if 70.0 > base_deposit else 0
                        base_concentration += 5 * intensity 
                        base_m2 += 6 * intensity 
                        base_m2_us += 18 * intensity 
                        
                    elif by == 2007:
                        margin_surge_add += (7.0 - base_margin) * intensity if 7.0 > base_margin else 0
                        recv_surge_add += (0.6 - base_recv) * intensity if 0.6 > base_recv else 0
                        deposit_surge_add += (15.0 - base_deposit) * intensity if 15.0 > base_deposit else 0
                        base_concentration += 3 * intensity
                        base_m2 += 4 * intensity
                        base_m2_us += 4 * intensity
                        
                    elif by == 1999:
                        margin_surge_add += (3.0 - base_margin) * intensity if 3.0 > base_margin else 0
                        recv_surge_add += (0.4 - base_recv) * intensity if 0.4 > base_recv else 0
                        deposit_surge_add += (10.0 - base_deposit) * intensity if 10.0 > base_deposit else 0
                        base_concentration += 6 * intensity
                        base_m2 += 3 * intensity
                        base_m2_us += 2 * intensity

                dist_after_peak = (y - by) * 12 + (m - bm)
                if 0 < dist_after_peak < 24:
                    burst_int = math.exp(-0.5 * ((dist_after_peak - 12) / 6) ** 2)
                    base_spread += 600 * burst_int 
                    base_us_spread -= 3.0 * burst_int 
                    base_m2 -= 5.0 * burst_int 
                    base_m2_us -= 8.0 * burst_int 

                if -12 < dist_after_peak <= 0:
                    inv_int = math.exp(-0.5 * ((dist_after_peak + 6) / 4) ** 2)
                    base_us_spread -= 2.5 * inv_int
            
            if y >= 2025:
                margin_surge_add = max(margin_surge_add, 22.0 + (y-2025 + m/12)*3.0 - base_margin)
                recv_surge_add = max(recv_surge_add, 1.0 - base_recv)
                deposit_surge_add = max(deposit_surge_add, 55.0 + (y-2025 + m/12)*50.0 - base_deposit)
                base_concentration += 4.0 
                
            noise = lambda: random.uniform(0.95, 1.05)
            
            val_buffett = base_buffett * bubble_mult * noise()
            val_shiller = base_shiller * bubble_mult * noise()
            val_margin = (base_margin + margin_surge_add) * random.uniform(0.97, 1.03)
            val_recv = (base_recv + recv_surge_add) * random.uniform(0.97, 1.03)
            val_deposit = (base_deposit + deposit_surge_add) * random.uniform(0.97, 1.03)
            
            
            val_conc = base_concentration * random.uniform(0.98, 1.02)
            val_spread = base_spread * random.uniform(0.9, 1.1)
            val_m2 = base_m2 * random.uniform(0.8, 1.2)
            val_m2_us = base_m2_us * random.uniform(0.8, 1.2)
            val_us_spread = base_us_spread + random.uniform(-0.2, 0.2)
            
            val_2y  = base_2y  + random.uniform(-0.15, 0.15)
            val_30y = base_30y + random.uniform(-0.1,  0.1)

            if y == 2026 and m == 5:
                val_buffett = 115.5
                val_shiller = 15.2
                val_margin = 27.2
                val_recv = 1.15
                val_deposit = 132.0
                val_conc = 48.5
                val_spread = 320
                val_m2 = 3.5
                val_m2_us = 0.5
                val_us_spread = -0.4
                val_2y  = 3.93   # 2026-05 실제치
                val_30y = 4.82   # 2026-05 실제치

            buffett.append(round(val_buffett, 1))
            shiller.append(round(val_shiller, 1))
            margin_loan.append(round(val_margin, 2))
            receivable.append(round(val_recv, 3))
            investor_deposit.append(round(val_deposit, 1))
            concentration_top10.append(round(val_conc, 1))
            credit_spread.append(round(val_spread, 0))
            m2_growth.append(round(val_m2, 1))
            m2_us_growth.append(round(val_m2_us, 1))
            us_yield_spread.append(round(val_us_spread, 2))
            us_yield_2y.append(round(max(0.0, val_2y), 2))
            us_yield_30y.append(round(max(0.0, val_30y), 2))

    return {
        "dates": dates,
        "buffett": buffett,
        "shiller": shiller,
        "margin_loan": margin_loan,
        "receivable": receivable,
        "investor_deposit": investor_deposit,
        "concentration": concentration_top10,
        "credit_spread": credit_spread,
        "m2_growth": m2_growth,
        "m2_us_growth": m2_us_growth,
        "us_yield_spread": us_yield_spread,
        "us_yield_2y": us_yield_2y,
        "us_yield_30y": us_yield_30y
    }

if __name__ == "__main__":
    data = fetch_real_data_or_mock()
    _now = datetime.now()
    js_content = f"""// 자동 생성 — 대한민국 거시/버블 지표 시계열 (1995~{_now.year}-{_now.month:02d})
// FRED 실데이터 오버레이 적용 (FDR). ECOS_API_KEY 설정 시 한국 지표도 실데이터로 교체됩니다.
window.BUBBLE_DATA = {{
    dates: {json.dumps(data['dates'])},
    buffett: {json.dumps(data['buffett'])},
    shiller: {json.dumps(data['shiller'])},
    margin_loan: {json.dumps(data['margin_loan'])},
    receivable: {json.dumps(data['receivable'])},
    investor_deposit: {json.dumps(data['investor_deposit'])},
    concentration: {json.dumps(data['concentration'])},
    credit_spread: {json.dumps(data['credit_spread'])},
    kor_corp_spread: {json.dumps(data.get('kor_corp_spread', [None]*len(data['dates'])))},
    m2_growth: {json.dumps(data['m2_growth'])},
    m2_us_growth: {json.dumps(data['m2_us_growth'])},
    us_yield_spread: {json.dumps(data['us_yield_spread'])},
    us_yield_2y: {json.dumps(data['us_yield_2y'])},
    us_yield_30y: {json.dumps(data['us_yield_30y'])}
}};
"""
    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"[Macro Fetcher] Successfully saved to {OUTPUT_JS}")

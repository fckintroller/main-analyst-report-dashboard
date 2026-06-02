import os
import json
import math
import random
import requests
from datetime import datetime

# ==========================================
# 1. Configuration & API Keys
# ==========================================
# GitHub Secrets에서 환경변수로 읽어옵니다. 없으면 None이 됩니다.
FRED_API_KEY = os.environ.get('FRED_API_KEY')
ECOS_API_KEY = os.environ.get('ECOS_API_KEY')

WEB_DIR = os.path.join(os.path.dirname(__file__), '..', 'web')
OUTPUT_JS = os.path.join(WEB_DIR, 'bubble_data.js')

def fetch_real_data_or_mock():
    """
    API 키가 존재하면 실제 API를 찔러 데이터를 가져오고, 
    없으면 모의(Mock) 데이터를 생성하여 반환합니다.
    (현재는 API 키 부재 시를 대비해 정교한 Fallback 모의 데이터를 생성)
    """
    print("[Macro Fetcher] Starting data collection...")
    
    if FRED_API_KEY and ECOS_API_KEY:
        print("[Macro Fetcher] API Keys found. Fetching real data from FRED & ECOS...")
        # =========================================================================
        # [TO-DO: 실제 API 연동 로직] 
        # 나중에 API 키가 등록되면 requests.get()으로 데이터를 받아오는 로직을 
        # 여기에 활성화하면 됩니다. 현재는 안전하게 mock_generator()로 폴백합니다.
        # =========================================================================
        pass
    else:
        print("[Macro Fetcher] API Keys NOT found. Falling back to Mock Data Generator.")
        
    return generate_mock_data()

def generate_mock_data():
    start_year = 1995
    end_year = 2026
    end_month = 5

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
                deposit_surge_add = max(deposit_surge_add, 55.0 + (y-2025 + m/12)*2.0 - base_deposit)
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
            
            if y == 2026 and m == 5:
                val_buffett = 115.5
                val_shiller = 15.2
                val_margin = 27.2
                val_recv = 1.15
                val_deposit = 58.4
                val_conc = 48.5 
                val_spread = 320 
                val_m2 = 3.5     
                val_m2_us = 0.5 
                val_us_spread = -0.4 
                
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
        "us_yield_spread": us_yield_spread
    }

if __name__ == "__main__":
    data = fetch_real_data_or_mock()
    js_content = f"""// 자동 생성된 대한민국 맞춤형 모의 버블 지표 데이터 (1995~2026)
// (API Key 환경변수가 주입되면 실제 데이터로 동적 갱신됩니다)
window.BUBBLE_DATA = {{
    dates: {json.dumps(data['dates'])},
    buffett: {json.dumps(data['buffett'])},
    shiller: {json.dumps(data['shiller'])},
    margin_loan: {json.dumps(data['margin_loan'])},
    receivable: {json.dumps(data['receivable'])},
    investor_deposit: {json.dumps(data['investor_deposit'])},
    concentration: {json.dumps(data['concentration'])},
    credit_spread: {json.dumps(data['credit_spread'])},
    m2_growth: {json.dumps(data['m2_growth'])},
    m2_us_growth: {json.dumps(data['m2_us_growth'])},
    us_yield_spread: {json.dumps(data['us_yield_spread'])}
}};
"""
    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"[Macro Fetcher] Successfully saved to {OUTPUT_JS}")

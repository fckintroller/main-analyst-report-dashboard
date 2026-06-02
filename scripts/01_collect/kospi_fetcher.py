import os
import sys
from datetime import datetime

# 부모 디렉터리(scripts)를 경로에 추가하여 utils를 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import logger

try:
    import FinanceDataReader as fdr
    import pandas as pd
except ImportError:
    logger.error("[KOSPI Fetcher] FinanceDataReader 또는 pandas 패키지가 설치되지 않았습니다. 'pip install finance-datareader pandas'를 실행하세요.")
    sys.exit(1)

# 데이터 저장 경로 설정 (data/raw/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')
CSV_PATH = os.path.join(DATA_DIR, 'kospi_history.csv')

def fetch_kospi_data():
    logger.info("[KOSPI Fetcher] KOSPI 지수(KS11) 데이터 수집 시작...")
    
    # 디렉터리가 없으면 생성
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    start_date = "1990-01-01"
    
    try:
        # FinanceDataReader를 이용해 코스피 지수 데이터 가져오기 (단 1줄!)
        # 데이터프레임 형식으로 오픈부터 종가, 거래량까지 모두 수집
        df = fdr.DataReader('KS11', start_date)
        
        if df.empty:
            logger.warning("[KOSPI Fetcher] 가져온 KOSPI 데이터가 비어 있습니다.")
            return False
            
        # 인덱스(Date)를 컬럼으로 빼내고, 소수점 반올림 처리
        df.reset_index(inplace=True)
        # 날짜 포맷 변경 (YYYY-MM-DD)
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # 반올림 (Open, High, Low, Close는 소수점 2자리)
        cols_to_round = ['Open', 'High', 'Low', 'Close']
        df[cols_to_round] = df[cols_to_round].round(2)
        
        # CSV 파일로 저장 (매일 덮어쓰기 방식으로 전체 데이터 동기화)
        df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
        
        latest_date = df['Date'].iloc[-1]
        latest_close = df['Close'].iloc[-1]
        
        logger.info(f"[KOSPI Fetcher] 수집 완료! 총 {len(df)}일치 데이터 저장됨 (경로: {CSV_PATH})")
        logger.info(f"  -> 최근 데이터: {latest_date} / 종가: {latest_close}")
        return True
        
    except Exception as e:
        logger.error(f"[KOSPI Fetcher] KOSPI 데이터 수집 중 에러 발생: {e}")
        return False

if __name__ == "__main__":
    fetch_kospi_data()

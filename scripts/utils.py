import json
import os
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 공통 경로 정의 (scripts 폴더 내부 기준)
# BASE_DIR = .../scripts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# 데이터 경로
DATA_DIR = os.path.join(ROOT_DIR, "data")
CONFIG_DIR = os.path.join(DATA_DIR, "config")
DB_PATH = os.path.join(DATA_DIR, "analyst_database.json")
CALENDAR_PATH = os.path.join(DATA_DIR, "economic_calendar.json")
STOCKS_PATH = os.path.join(CONFIG_DIR, "stocks.json")
FIXED_EVENTS_PATH = os.path.join(CONFIG_DIR, "fixed_events.json")

# 웹 경로
WEB_DIR = os.path.join(ROOT_DIR, "web")
JS_PATH = os.path.join(WEB_DIR, "analyst_data.js")

# 리포트 경로
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")
MD_PATH = os.path.join(REPORTS_DIR, "analyst_awards_report.md")
CSV_PATH = os.path.join(REPORTS_DIR, "analyst_table_sheet.csv")

# 외부 백업 경로 (기존 유지)
OUTPUTS_DIR = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "02_outputs"))

def load_json(file_path, default=None):
    """JSON 파일을 로드합니다."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"JSON 로드 실패 ({file_path}): {e}")
    return default if default is not None else {}

def save_json(file_path, data):
    """JSON 데이터를 파일로 저장합니다."""
    try:
        # 상위 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"JSON 저장 실패 ({file_path}): {e}")
        return False

def load_db():
    """애널리스트 데이터베이스를 로드합니다."""
    return load_json(DB_PATH, {"analysts": [], "recommendations": [], "reports": []})

def save_db(data):
    """애널리스트 데이터베이스를 저장합니다."""
    return save_json(DB_PATH, data)

def load_stocks():
    """종목 마스터 데이터를 로드합니다."""
    return load_json(STOCKS_PATH, {})

def load_calendar():
    """경제 캘린더 데이터를 로드합니다."""
    return load_json(CALENDAR_PATH, [])

def save_calendar(data):
    """경제 캘린더 데이터를 저장합니다."""
    return save_json(CALENDAR_PATH, data)

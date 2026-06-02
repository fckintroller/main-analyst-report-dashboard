import os
import sys
import subprocess
from utils import logger

def run_script(script_path, description):
    logger.info(f"========== [파이프라인] {description} 시작 ==========")
    try:
        # Run the script using the same python executable
        result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True)
        # Log the stdout
        for line in result.stdout.splitlines():
            if line.strip():
                logger.info(f"  {line.strip()}")
        logger.info(f"========== [파이프라인] {description} 완료 ==========\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"========== [파이프라인] {description} 실패 ==========")
        logger.error(f"Error Code: {e.returncode}")
        for line in e.stdout.splitlines():
            if line.strip():
                logger.error(f"  {line.strip()}")
        for line in e.stderr.splitlines():
            if line.strip():
                logger.error(f"  {line.strip()}")
        return False

def main():
    logger.info("#######################################################")
    logger.info("         데이터 파이프라인 (ETL) 일일 배치 시작        ")
    logger.info("#######################################################")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 수집 (Collect)
    steps = [
        (os.path.join(base_dir, "01_collect", "report_crawler.py"), "1단계: 리포트 크롤링 (수집)"),
        (os.path.join(base_dir, "01_collect", "calendar_fetcher.py"), "1단계: 경제 캘린더 수집 (수집)"),
        (os.path.join(base_dir, "01_collect", "macro_fetcher.py"), "1단계: 매크로 지표 수집 (수집)"),
        # 2. 분석 (Analyze) - 추후 구현
        # 3. 정제 (Refine) - 추후 구현 (현재는 crawler에 내장됨)
        # 4. 도출 (Export)
        (os.path.join(base_dir, "04_export", "exporter.py"), "4단계: 자바스크립트/CSV 도출 (적재)")
    ]
    
    for script_path, desc in steps:
        if not os.path.exists(script_path):
            logger.error(f"[파이프라인 에러] 파일을 찾을 수 없습니다: {script_path}")
            continue
            
        success = run_script(script_path, desc)
        if not success:
            logger.error("[파이프라인 중단] 치명적 에러로 인해 파이프라인이 중단되었습니다.")
            sys.exit(1)

    logger.info("#######################################################")
    logger.info("         데이터 파이프라인 (ETL) 일일 배치 종료        ")
    logger.info("#######################################################")

if __name__ == "__main__":
    main()

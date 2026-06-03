import os
import sys
import subprocess
from utils import logger

def run_script(script_path, description):
    logger.info(f"========== [?뚯씠?꾨씪?? {description} ?쒖옉 ==========")
    try:
        # Run the script using the same python executable
        result = subprocess.run([sys.executable, script_path], check=True, capture_output=True, text=True)
        # Log the stdout
        for line in result.stdout.splitlines():
            if line.strip():
                logger.info(f"  {line.strip()}")
        logger.info(f"========== [?뚯씠?꾨씪?? {description} ?꾨즺 ==========\n")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"========== [?뚯씠?꾨씪?? {description} ?ㅽ뙣 ==========")
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
    logger.info("         ?곗씠???뚯씠?꾨씪??(ETL) ?쇱씪 諛곗튂 ?쒖옉        ")
    logger.info("#######################################################")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. ?섏쭛 (Collect)
    steps = [
        (os.path.join(base_dir, "01_collect", "report_crawler.py"), "1?④퀎: 由ы룷???щ·留?(?섏쭛)"),
        (os.path.join(base_dir, "01_collect", "01_macro.py"), "1?④퀎: 嫄곗떆寃쎌젣(Macro) ?곗씠???섏쭛"),
        (os.path.join(base_dir, "01_collect", "02_sentiment.py"), "1?④퀎: ?쒖옣 ?щ━(Sentiment) ?곗씠???섏쭛"),
        (os.path.join(base_dir, "01_collect", "03_money_flow.py"), "1?④퀎: ?섍툒/?좊룞??Money Flow) ?곗씠???섏쭛"),
        (os.path.join(base_dir, "01_collect", "04_valuation.py"), "1?④퀎: 媛移?媛쒕퀎湲곗뾽(Valuation) ?곗씠???섏쭛"),
        (os.path.join(base_dir, "01_collect", "calendar_fetcher.py"), "1?④퀎: 寃쎌젣 罹섎┛???섏쭛 (?섏쭛)"),
        (os.path.join(base_dir, "01_collect", "macro_fetcher.py"), "1?④퀎: ?띿뒪??留ㅽ겕濡??섏쭛 (?섏쭛)"),

        # 2. ?곸옱 (Store) - ?뺥빀??寃????SQLite DB ?듯빀
        (os.path.join(base_dir, "02_store", "sanitize.py"), "2?④퀎: ?곗씠???뺥빀??寃??(Sanitize)"),
        (os.path.join(base_dir, "02_store", "load_to_db.py"), "2?④퀎: SQLite DB 留덉씠洹몃젅?댁뀡 (?곸옱)"),

        # 3. 遺꾩꽍 (Analyze)
        (os.path.join(base_dir, "03_analyze", "export_web_data.py"), "3?④퀎: ????쒕낫???곕룞??JS ?뚯씪 ?앹꽦 (Analyze)"),

        # 4. ?꾩텧 (Export)
        (os.path.join(base_dir, "04_export", "exporter.py"), "4?④퀎: ?먮컮?ㅽ겕由쏀듃/CSV ?꾩텧 (?곸옱)")
    ]

    for script_path, desc in steps:
        if not os.path.exists(script_path):
            logger.error(f"[?뚯씠?꾨씪???먮윭] ?뚯씪??李얠쓣 ???놁뒿?덈떎: {script_path}")
            continue

        success = run_script(script_path, desc)
        if not success:
            logger.error("[?뚯씠?꾨씪??以묐떒] 移섎챸???먮윭濡??명빐 ?뚯씠?꾨씪?몄씠 以묐떒?섏뿀?듬땲??")
            sys.exit(1)

    logger.info("#######################################################")
    logger.info("         ?곗씠???뚯씠?꾨씪??(ETL) ?쇱씪 諛곗튂 醫낅즺        ")
    logger.info("#######################################################")

if __name__ == "__main__":
    main()

import json
import os
import datetime

# 파일 경로 정의
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "analyst_database.json")
JS_PATH = os.path.join(BASE_DIR, "analyst_data.js")
MD_PATH = os.path.join(BASE_DIR, "analyst_awards_report.md")
CSV_PATH = os.path.join(BASE_DIR, "analyst_table_sheet.csv")
OUTPUTS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "02_outputs"))

def load_database():
    """analyst_database.json 로드"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"데이터베이스 파일이 없습니다: {DB_PATH}")
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_csv(db_data):
    """구글 시트 연동용 CSV(쉼표 구분) 갱신"""
    lines = ["연도/시기,부문(섹터),애널리스트 이름,소속 증권사,평가 등급,핵심 투자 관점 및 시그니처 분석\n"]
    
    # 애널리스트 데이터 쓰기
    for a in db_data.get("analysts", []):
        evaluation_clean = a['evaluation'].replace(',', ' ').replace('\n', ' ').strip()
        line = f"2025 하반기,{a['merged_sector']},{a['name']},{a['firm']},{a['awards'].split(',')[0]},{evaluation_clean}\n"
        lines.append(line)
        
    with open(CSV_PATH, "w", encoding="utf-8-sig") as f: # utf-8-sig로 저장하여 엑셀/구글시트에서 한글 깨짐 방지
        f.writelines(lines)
    print(f"  [CSV 완료] {CSV_PATH}가 성공적으로 업데이트되었습니다.")

def compile_markdown(db_data):
    """마크다운 보고서 동적 작성"""
    analysts = db_data.get("analysts", [])
    # 투자의견 변동 내역 최신순(역순) 정렬
    recommendations = sorted(db_data.get("recommendations", []), key=lambda x: x["date"], reverse=True)
    
    # 1. 투자의견 변동 섹션 빌드
    alerts_content = ""
    for r in recommendations:
        badge = "🟢 상향 (Upgrade)" if r["change_type"] == "upgrade" else "🔴 하향 (Downgrade)"
        comment_clean = r["comment"].replace("\n", " ")
        alerts_content += f"""
### {badge} {r['stock_name']} ({r['stock_code']})
*   **담당 애널리스트**: {next((a['firm'] + " " + a['name'] + " " + a['position'] for a in analysts if a['id'] == r['analyst_id']), '외부 기고가')}
*   **변경 내역**: `{r['previous_rating']}` $\\rightarrow$ **`{r['current_rating']}`** (목표가: {r['target_price']})
*   **의견 조정일**: {r['date']}
*   **리서치 코멘트**: *"{comment_clean}"*
---
"""
    if not alerts_content:
        alerts_content = "\n*현재 감지된 신규 투자의견 변경 알림이 없습니다.*\n"

    # 2. 결합 섹터별 애널리스트 그룹화
    sectors_map = {}
    for a in analysts:
        sector = a["merged_sector"]
        if sector not in sectors_map:
            sectors_map[sector] = []
        sectors_map[sector].append(a)

    sectors_content = ""
    for sector_name, member_list in sectors_map.items():
        sectors_content += f"\n## 📂 {sector_name} 부문\n"
        for a in member_list:
            targets_str = ", ".join(a["targets"])
            sectors_content += f"""
### 👤 {a['firm']} {a['name']} {a['position']}
> **"{a['awards']}"**
*   **시그니처 평가**: {a['evaluation']}
*   **핵심 커버 종목**: `{targets_str}`
"""
        sectors_content += "---\n"

    # 3. 전체 요약 표 동적 빌드 (구글 시트 연동용)
    table_rows = ""
    for a in analysts:
        table_rows += f"| 2025 하반기 | {a['merged_sector']} | {a['name']} | {a['firm']} | {a['awards'].split(',')[0]} | {a['evaluation']} |\n"

    # 4. 전체 마크다운 파일 조립
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    markdown_template = f"""# [대한민국 최정상급 베스트 애널리스트 핵심 데이터베이스]

> **"주식 시장의 1등 펀드매니저들이 가장 신뢰하는 브레인들의 투자 전략 분석 데이터베이스"**
> **최종 업데이트 일시**: `{now_str}`

---

## 📢 [실시간 알림] 핵심 투자의견 변동 추적 (Upgrade/Downgrade)

> [!WARNING]
> 본 섹터는 애널리스트들이 직전 등급 대비 **'매수 $\\leftrightarrow$ 홀딩', '홀딩 $\\leftrightarrow$ 매도'** 등 투자의견을 긴급 조정한 종목들을 실시간으로 트래킹합니다. 스윙/단기 모멘텀 매매 시 최우선 순위 포트폴리오 조정 기준으로 활용하십시오.

{alerts_content}

---

## 📁 5대 핵심 시너지 섹터별 최우수 애널리스트 상세 프로필

본 섹션은 중복되거나 연동성이 높은 산업군을 유기적으로 결합하여 구성한 **확장형 섹터 맵**입니다. 

{sectors_content}

---

## 📊 구글 시트 연동 전체 마스터 테이블

> [!TIP]
> 아래의 테이블 전체를 복사하여 귀하의 [구글 시트](https://docs.google.com/spreadsheets/d/1Gn-K4XEXDbzraHjY6RbsPLgR5ub7dGrddyO3QNz4aBo/edit?usp=sharing)에 **[텍스트로 붙여넣기]** 하시면 깨짐 현상 없이 정렬되어 데이터 관리가 즉시 연동됩니다.

| 연도/시기 | 부문 (결합 섹터) | 애널리스트 이름 | 소속 증권사 | 대표 평가 등급 | 핵심 투자 관점 및 시그니처 분석 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{table_rows}
---
"""
    return markdown_template

def generate_market_data(db_data):
    """코스피 및 종목별 52주 시계열 주가 데이터 시뮬레이션 생성"""
    import random
    random.seed(42) # 동일 데이터 재현을 위해 시드 고정
    
    dates = []
    start_date = datetime.date(2025, 6, 2)
    for i in range(52):
        d = start_date + datetime.timedelta(weeks=i)
        dates.append(d.strftime("%Y-%m-%d"))
        
    # 종목별 시작가, 종료가 매핑
    price_ranges = {
        "KOSPI": (2650, 2750),
        "SK하이닉스": (900000, 1700000),
        "삼성전자": (160000, 250000),
        "삼양식품": (830000, 1850000),
        "알테오젠": (300000, 620000),
        "한화에어로스페이스": (400000, 2040000),
        "한국전력": (22000, 65000),
        "에코프로비엠": (200000, 257000),
        "스튜디오드래곤": (52000, 47000),
        "LG에너지솔루션": (470000, 430000),
        "NAVER": (200000, 230000),
        "LG화학": (480000, 420000),
        "리가켐바이오": (90000, 140000),
        "두산테스나": (43000, 55000),
        "농심": (410000, 510000),
        "CJ ENM": (85000, 115000),
        "카카오": (62000, 58000),
        "CJ제일제당": (370000, 340000),
        "현대로템": (38000, 70000),
        "한국항공우주": (51000, 70000),
        "삼성전기": (650000, 1600000),
        "하이브": (210000, 310000),
        "삼성중공업": (9500, 14500),
        "현대건설": (35000, 48000),
        "한미약품": (290000, 390000),
        "아모레퍼시픽": (130000, 220000),
        "한미반도체": (100000, 180000),
        "LG디스플레이": (13000, 16500),
        "이수페타시스": (41000, 62000)
    }
    
    unique_stocks = set()
    for a in db_data.get("analysts", []):
        unique_stocks.update(a.get("targets", []))
    for rep in db_data.get("reports", []):
        unique_stocks.add(rep["stock_name"])
        
    for stock in unique_stocks:
        if stock not in price_ranges:
            price_ranges[stock] = (50000, 75000)
            
    # 시계열 가격 생성
    series = {}
    for stock, (start, end) in price_ranges.items():
        prices = []
        current = start
        for i in range(52):
            progress = i / 51.0
            noise = random.uniform(-0.03, 0.03)
            trend = start + (end - start) * progress
            current = trend * (1.0 + noise)
            
            # 특수 흐름 제어
            if stock == "KOSPI" and 10 < i < 30:
                current -= 100
            elif stock == "에코프로비엠" and i < 25:
                current *= 0.8
            elif stock == "삼성전기" and i < 20:
                current *= 0.9
                
            if stock == "KOSPI":
                prices.append(round(current, 2))
            else:
                prices.append(int(round(current, -2)))
                
        series[stock] = prices
        
    return {
        "dates": dates,
        "series": series
    }

def main():
    print("[Updater] 데이터베이스 로드 및 갱신 프로세스 시작...")
    db_data = load_database()
    
    # 시장 데이터 시뮬레이션 생성
    market_data = generate_market_data(db_data)
    
    # 1. 자바스크립트 브릿지 파일 갱신
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"window.ANALYST_DATABASE = {json.dumps(db_data, ensure_ascii=False, indent=2)};\n")
        f.write(f"window.MARKET_DATA = {json.dumps(market_data, ensure_ascii=False, indent=2)};\n")
    print(f"  [자바스크립트 브릿지 완료] {JS_PATH}가 성공적으로 업데이트되었습니다.")
    
    # 2. CSV 테이블 갱신
    generate_csv(db_data)
    
    # 3. 마크다운 보고서 빌드 및 저장
    markdown_content = compile_markdown(db_data)
    
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"  [마크다운 완료] {MD_PATH}가 성공적으로 업데이트되었습니다.")
    
    # 4. 작업 규칙 2번에 따른 02_outputs 폴더 사본 생성
    if os.path.exists(OUTPUTS_DIR):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        timestamped_filename = f"{timestamp}_Anal_reports.md"
        backup_path = os.path.join(OUTPUTS_DIR, timestamped_filename)
        
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"  [작업 규칙 준수 완료] 02_outputs 내 사본 저장 완료: {backup_path}")
    else:
        print(f"  [경고] 02_outputs 디렉터리가 없어 사본을 백업하지 못했습니다: {OUTPUTS_DIR}")

    print("[Updater] 모든 파일 자동 업데이트 프로세스가 정상 완료되었습니다.")

if __name__ == "__main__":
    main()

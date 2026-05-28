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
    recommendations = db_data.get("recommendations", [])
    
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
> **최종 자동 업데이트 일시**: `{now_str}` (2주 주기 스케줄러 작동 중)

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

## 🛠️ 자동화 스케줄러 시스템 활용법
*   본 데이터베이스 및 보고서는 `updater.py` 스크립트에 의해 **2주마다 자동 실행**되어 최신 정보를 마크다운과 웹사이트로 반영합니다.
*   새로운 애널리스트를 추가하고 싶으신 경우, `analyst_database.json` 파일의 `analysts` 배열에 정보를 포맷대로 추가하고 스크립트를 재실행(혹은 배치 실행)하시면 웹과 보고서에 실시간 확장 반영됩니다.
"""
    return markdown_template

def main():
    print("[Updater] 데이터베이스 로드 및 갱신 프로세스 시작...")
    db_data = load_database()
    
    # 1. 자바스크립트 브릿지 파일 갱신
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"window.ANALYST_DATABASE = {json.dumps(db_data, ensure_ascii=False, indent=2)};")
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

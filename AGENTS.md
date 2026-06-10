# AGENTS.md — Anal_reports

이 파일은 `C:\claude cowork\01_projects\Anal_reports` 프로젝트에서 Claude, Hermes, Codex 등 AI agent가 작업할 때 반드시 따라야 하는 프로젝트 전용 지침입니다.

---

## 1. Required Context Load

작업 전 아래 파일을 먼저 읽습니다.

1. `C:\claude cowork\00_context\working rule.md`
2. `C:\claude cowork\00_context\about-me.md`
3. `C:\claude cowork\00_context\voice&style.md`
4. `C:\claude cowork\00_context\AGENTS.md`
5. `C:\claude cowork\00_context\index.md`
6. `C:\claude cowork\00_context\collaboration.md`
7. `C:\claude cowork\00_context\work_state.md`
8. `C:\claude cowork\01_projects\Anal_reports\data.md`
9. 보고서/애널리스트 DB 수정이면 `C:\claude cowork\00_context\report.md`

---

## 2. Collaboration / Lock Rules

- 수정 전 `C:\claude cowork\00_context\work_state.md`에서 active lock을 확인합니다.
- 다른 agent가 lock 중인 파일/폴더/DB는 수정하지 않습니다.
- 작업 시작 시 필요한 경우 `work_state.md`에 lock을 남깁니다.
- 작업 완료 후 lock을 해제하고 `CHANGELOG_AGENT.md`에 기록합니다.
- 새 파일/폴더 생성 또는 구조 변경 후 `C:\claude cowork\00_context\index.md`를 업데이트합니다.

---

## 3. Single Source of Truth

### API / Secrets

- API 키 정본은 오직 프로젝트 루트 `.env`입니다.
  - `C:\claude cowork\01_projects\Anal_reports\.env`
- `env.bat`은 legacy 배치 호환용입니다.
- 새 secret/config 파일 생성 금지:
  - `api_key.txt`, `secrets.json`, `config.local`, `dart_key.txt`, `ecos_key.txt` 등
- 키 값은 문서, 로그, index, changelog에 기록하지 않습니다.

### SQLite DB

- 정본 DB:
  - `C:\claude cowork\01_projects\Anal_reports\data\database\quant_data.sqlite`
- SQLite 쓰기 작업은 exclusive lock 필요.
- DB 변경 전 백업을 만들거나 기존 백업 상태를 확인합니다.
- DB 변경 후 row count, 날짜 범위, 테이블명을 검증합니다.

---

## 4. Project Overview

- 목적: 국내 애널리스트 리포트 + 퀀트/매크로 대시보드
- Backend/Data: Python, pandas, requests, yfinance, FinanceDataReader, pykrx, OpenDartReader
- Frontend: Vanilla HTML/CSS/JS, Chart.js
- 주요 흐름:
  1. `scripts/01_collect/`에서 raw 수집
  2. `data/raw/`에 원천 CSV/JSON 보존
  3. `scripts/02_store/load_to_db.py` 등으로 SQLite 적재
  4. `scripts/03_analyze/export_web_data.py`로 web JS 산출
  5. `web/`에서 대시보드 렌더링

---

## 5. Setup & Execution Commands

Bash/MSYS 기준:

```bash
cd "/c/claude cowork/01_projects/Anal_reports"
python --version
pip install -r requirements.txt
python scripts/pipeline.py
```

웹 확인:

```bash
cd "/c/claude cowork/01_projects/Anal_reports/web"
python -m http.server 8000
```

브라우저:

```text
http://localhost:8000/index.html
```

---

## 6. Code Style & Data Rules

- 한국어 답변, 두괄식 보고.
- Vanilla JS 유지. React/Vue/Tailwind/jQuery 신규 도입 금지 unless 사용자 승인.
- 결측 데이터 임의 생성/보간 금지.
- 원천 raw 파일 보존.
- 수집/적재 후 검증 필수:
  - raw 파일 존재
  - CSV row count
  - SQLite table row count
  - 날짜 범위 min/max
  - 실패 소스는 명확히 `failed` 또는 주석 기록
- `analyst_database.json` 수정 시 `analyst_id` 100% 매칭 검증 필수.

---

## 7. Known Caveats

- FRED graph CSV endpoint는 현재 네트워크에서 timeout/RemoteDisconnected 이력이 있음.
- `^VNINDEX.VN` 베트남 지수는 장기 이력이 부족할 수 있음.
- Barley/Sorghum World Bank 원자료는 2020-08 이후 정체 가능. 임의 보간 금지.
- 2026 KOSPI/KOSDAQ 레벨은 사용자 확인 기준 이 workspace의 정본으로 취급.
- `.env`, `env.bat` 값은 절대 노출하지 않음.

---

## 8. Change Logging

작업 완료 후 `C:\claude cowork\01_projects\Anal_reports\CHANGELOG_AGENT.md`에 아래 형식으로 기록합니다.

```md
## YYYY-MM-DD HH:MM - AgentName
- Task:
- Changed:
- Created:
- Verification:
- Caveats:
```

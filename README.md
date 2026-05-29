# 📈 KOREAN ANALYST REPORT

> **"주식 시장의 브레인들이 분석하는 투자 전략을 한눈에 확인하는 올인원 데이터베이스"**

이 프로젝트는 국내 주요 증권사의 최정상급 애널리스트들의 리포트, 투자의견 변동(Upgrade/Downgrade), 그리고 주요 경제 지표를 실시간으로 수집하고 시각화하여 투자 의사결정을 돕는 자동화 대시보드 시스템입니다.

---

## 🚀 주요 기능

### 1. 실시간 데이터 수집 (Crawling & Fetching)
- **네이버 금융 리서치 수집**: 최신 기업/산업 분석 리포트를 자동으로 크롤링하여 데이터베이스화합니다. (중복 방지 로직 포함)
- **글로벌 경제 캘린더**: ForexFactory 및 고정 일정을 통해 시장에 큰 영향을 미치는 'High Impact' 이벤트를 가져옵니다.
- **주가 데이터 연동**: 네이버 금융 API를 통해 KOSPI 및 주요 종목의 52주 주가 데이터를 실시간 패치합니다.

### 2. 스마트 분석 및 리포팅
- **투자의견 추적**: 애널리스트들의 의견 변동 및 목표주가 변화를 실시간으로 감지하여 정밀한 알림을 생성합니다.
- **보고서 자동 생성**: 수집된 데이터를 바탕으로 마크다운(MD) 및 구글 시트 연동용 CSV 리포트를 자동 작성합니다.

### 3. 인터랙티브 대시보드
- **디자인 시스템 적용**: 'Dark Pine Green' 테마와 고대비 시각화 원칙을 적용한 전문적인 UI/UX를 제공합니다.
- **차트 분석**: 코스피 지수와 개별 종목의 수익률 및 주가 추이를 이중 축(Dual-Axis)으로 비교 분석합니다.

---

## 📂 프로젝트 구조

```text
├── data/
│   ├── config/            # 정적 설정 (stocks.json, fixed_events.json)
│   ├── analyst_database.json
│   └── economic_calendar.json
├── docs/                  # 프로젝트 기술 명세서 및 디자인 가이드
│   └── DESIGN_SYSTEM_AND_SPECS.md
├── scripts/               # 수집 및 분석 실행 로직 (utils.py 기반 공통화)
│   ├── crawler.py
│   ├── calendar_fetcher.py
│   ├── updater.py
│   └── utils.py
├── web/                   # 프론트엔드 대시보드 (XSS 방어 및 모듈화 적용)
│   ├── index.html
│   ├── app.js
│   └── analyst_data.js
├── reports/               # 생성된 분석 결과물 (MD, CSV)
├── .gitignore             # 환경 정리 및 보안 가이드
└── README.md              # 프로젝트 메인 가이드
```

---

## 🏗️ 핵심 설계 및 보안 원칙

이 프로젝트는 장기적인 유지보수와 안정적인 운영을 위해 다음 원칙을 준수합니다. 상세 내용은 [기술 명세서](docs/DESIGN_SYSTEM_AND_SPECS.md)를 참고하십시오.

- **보안 중심 (XSS Defense)**: 모든 외부 데이터 렌더링 시 `escapeHTML` 필터를 거쳐 보안 위협을 원천 차단합니다.
- **단일 진실 공급원 (SSOT)**: 모든 파일 경로와 공통 로직은 `utils.py`에서 관리하여 데이터 정합성을 보장합니다.
- **온라인 표준 동기화**: 라이브 대시보드와 로컬 환경 간의 UI 및 비즈니스 로직을 1:1로 완벽히 동기화합니다.

---

## 🛠️ 설치 및 실행 방법

### 1. 환경 준비
Python 3.x 버전이 설치되어 있어야 합니다. 표준 라이브러리 위주로 설계되어 별도의 복잡한 설치 과정이 필요하지 않습니다.

### 2. 데이터 업데이트 실행
```bash
cd scripts
python crawler.py
python calendar_fetcher.py
python updater.py
```

### 3. 대시보드 확인
`web/index.html` 파일을 크롬 등 최신 브라우저로 실행하십시오. (수정 사항 반영을 위해 `Ctrl + F5` 권장)

---
**최종 업데이트**: 2026-05-30

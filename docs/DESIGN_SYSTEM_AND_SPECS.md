# 🎨 KOREAN ANALYST REPORT: Detailed Design System & Technical Specifications

본 문서는 대시보드 프로젝트의 유지보수 및 확장을 위한 **단일 진실 공급원(Single Source of Truth)**입니다. UI/UX 디자인 원칙부터 데이터 파이프라인 구조, 컴포넌트 인터랙션 명세까지 상세한 개발 규칙을 정의합니다.

---

## 1. Design System Tokens (디자인 시스템 토큰)

모든 스타일링은 CSS 변수(`:root`) 및 사전 정의된 토큰을 기반으로 구현되어야 합니다. 임의의 하드코딩된 색상 사용을 엄격히 금지합니다.

### 1.1. Core Palette (핵심 팔레트)
테마 테마: **Dark Pine Green (저조도 / 고대비 다크 모드)**

| Token Name | Hex Code | Usage |
| :--- | :--- | :--- |
| `--bg-color` | `#040608` | 최상위 Body 배경. 완벽한 블랙에 가까운 틴트. |
| `--card-bg` | `#080c12` | 탭 콘텐츠, 카드, 컨테이너 배경. |
| `--card-border` | `#101620` | 모든 컨테이너와 표의 기본 구분선. |
| `--text-main` | `#d1d5db` | 주요 본문 텍스트 (명도 대비 확보). |
| `--text-sub` | `#6b7280` | 날짜, 설명 등 부가 정보 (가독성 유지 한계선). |
| `--primary` | `#047857` | 브랜드 포인트, 활성 탭 아웃라인. |
| `--primary-glow` | `rgba(4, 120, 87, 0.1)` | 카드 호버 시 발생하는 네온 글로우. |

### 1.3. Layout & Animation (레이아웃 및 애니메이션)
*   **Max Width**: 전체 컨테이너는 최대 `1300px`로 제한하며 중앙 정렬함.
*   **Grid Gap**: 주요 그리드 레이아웃(`.analysts-grid`, `.reports-grid`, `.chart-tab-container`)은 일관되게 `25px`의 간격을 유지함.
*   **Transition**: 모든 인터랙티브 요소는 `all 0.25s cubic-bezier(0.4, 0, 0.2, 1)` 속성을 사용하여 부드러운 상태 변화를 제공함.
*   **Scrollbar**: 가독성을 위해 `8px` 너비의 슬림 스크롤바를 사용하며, 핸들 색상은 `#101620`, 반경은 `4px`로 설정함.

### 1.2. Semantic Semantic & Feedback Colors (의미론적 색상)

**투자의견 (Investment Ratings)**
*   **Buy (매수)**: `#10b981` (Emerald Green)
*   **Hold (중립)**: `#d97706` (Golden Yellow)
*   **Sell (매도)**: `#ef4444` (Rose Red)
*   *상향 배지*: Border `#059669`, BG `rgba(5, 150, 105, 0.05)`
*   *하향 배지*: Border `#b91c1c`, BG `rgba(185, 28, 28, 0.05)`

**국가별 매핑 (Country Indicators)**
*   미국: `#3b82f6` (Blue)
*   한국/중국: `#ef4444` (Red)
*   일본: `#f59e0b` (Orange)
*   유로존: `#8b5cf6` (Purple)
*   영국: `#ec4899` (Pink)
*   *배지 렌더링 룰*: `background: {COLOR}15`, `border: 1px solid {COLOR}40`, `color: {COLOR}`

---

## 2. Component Specifications (컴포넌트 명세)

### 2.1. Global Layout (공통 레이아웃)
*   **Container**: `max-width: 1300px`, `margin: 0 auto`, `padding: 40px 20px`.
*   **Border Radius**: 모든 카드 및 주요 컨테이너는 `8px`의 반경을 가짐.

### 2.2. Analyst Card (애널리스트 카드)
*   **구조**: `display: flex; flex-direction: column; justify-content: space-between;`
*   **패딩**: 내부 사방 `25px`.
*   **스타일**: 
    *   기본 테두리(`--card-border`), 좌측 4px 두께의 `--primary` accent line.
    *   **Hover State**: `transform: translateY(-3px)`, Box-shadow (기본 블랙 섀도우 + `--primary-glow`).
*   **제약사항**: `evaluation-text`는 CSS `-webkit-line-clamp: 3`을 적용하여 3줄 초과 시 생략 기호(`...`) 처리 필수.

### 2.3. Research Report Card (리서치 보고서 카드)
*   **패딩**: 내부 사방 `20px`.
*   **구조**: 제목 및 메타정보를 포함하는 `.report-card-header`와 하단 푸터 `.report-footer`로 구분됨.
*   **인터랙션**: Hover 시 테두리 색상 변화 및 `translateY(-2px)` 애니메이션 적용.

### 2.4. Interactive Event Timeline (이벤트 타임라인)
*   **구조**: `.external-event-item`
*   **패딩**: `12px 15px`.
*   **Default State**: 배경색 `var(--card-bg)`, 텍스트 `#ffffff`.
*   **Highlight State (`.highlighted-event`)**: 
    *   배경색 `#ffffff !important`, 좌측/하단 테두리 `#facc15` (Yellow).
    *   텍스트(날짜, 제목 등) `#ef4444 !important` (Red) 및 `font-weight: 700` 적용.
*   **High Impact (사전 강조)**: `impact === 'High'`인 경우, 렌더링 시점부터 배경색 3% 틴트(`rgba(250, 204, 21, 0.03)`) 및 좌측 3px 두꺼운 테두리(`border-left: 3px solid #facc15`) 강제 적용.

### 2.5. Alerts Table (투자의견 변동 테이블)
*   **구조**: `.alerts-table` (반응형 `.table-responsive` 래퍼 필수).
*   **셀 스타일**:
    *   **Header (th)**: 패딩 `10px 12px`, 폰트 `0.85rem`, 배경 `#101620`, 텍스트 `#10b981`.
    *   **Data (td)**: 패딩 `10px 12px`, 폰트 `0.82rem`, 기본 `white-space: nowrap` 적용.
*   **인터랙션**: 
    *   **Row Hover**: `background: #101620` 및 부드러운 전환 효과 적용.
*   **특수 셀 규격**:
    *   **기업명**: `.company-name` (Bold/White) + `.company-code` (Sub-text) 조합.
    *   **리서치 코멘트**: `.alert-comment` (Italic), 최대 너비 `260px` 제한 및 `white-space: normal`로 줄바꿈 허용.

---

## 3. Data Architecture & Schema (데이터 파이프라인 스키마)

모든 데이터는 `data/` 및 `data/config/` 폴더 내 JSON 형식으로 철저히 관리됩니다.

### 3.1. `analyst_database.json`
*   **`reports` 배열 객체 구조:**
    ```json
    {
      "analyst_id": "string (애널리스트 고유 ID 또는 'external_analyst')",
      "stock_name": "string",
      "stock_code": "string",
      "title": "string",
      "summary": "string",
      "date": "YYYY-MM-DD",
      "rating": "string (매수/홀딩/매도 등)",
      "target_price": "string (예: '100,000원')"
    }
    ```
*   **데이터 정합성 (Deduplication)**: `crawler.py`는 수집 시 `f"{date}_{stock_name}_{title}"` 복합 키를 기준으로 중복 여부를 판별합니다.

### 3.2. `economic_calendar.json`
*   **객체 구조:**
    ```json
    {
      "date": "YYYY-MM-DD",
      "title": "string",
      "country": "string (미국/한국/유로존 등)",
      "impact": "High | Medium | Low",
      "forecast": "string (예: '2.5%')",
      "previous": "string"
    }
    ```
*   **병합 규칙**: `calendar_fetcher.py`는 API 수집 데이터와 `data/config/fixed_events.json`을 병합하며, `f"{date}_{title}"`을 기준으로 고유성을 보장합니다.

---

## 4. Complex Interactions (고난이도 인터랙션 명세)

### 4.1. Chart.js 이중 축(Dual-Axis) 및 스케일링 규칙
*   **KOSPI 절대 보존의 법칙**: KOSPI는 비교 대상으로서 항상 원시 지수(PT) 값을 유지해야 함. 따라서 '수익률(pct)' 모드일지라도 KOSPI는 퍼센트로 변환되지 않음.
*   **Dual-Axis 트리거 조건**: KOSPI와 다른 개별 종목이 **동시에** 선택된 경우, 차트 모드(`price` 또는 `pct`)와 무관하게 이중 축을 활성화함.
*   **동작 방식**: 
    *   **KOSPI**: 항상 우측 축(`y2`)에 배치, 단위 표시 `pt`, 틱 색상 `#10b981`.
    *   **기타 종목**: 항상 좌측 축(`y`)에 배치, 모드에 따라 단위 표시(`원` 또는 `%`), 틱 색상 `#9ca3af`.
    *   만약 KOSPI 단독 선택이거나, 개별 종목들만 선택된 경우 우측 축(`y2`)은 DOM에서 완전히 삭제(`delete marketChart.options.scales.y2`)되어 차트 여백 낭비를 방지.

### 4.3. Stock Search & Checklist Logic (종목 검색 및 체크리스트)
*   **Persistent KOSPI**: 종목 검색 필터링 시에도 `'KOSPI'` 항목은 항상 가시성을 유지해야 함 (`name === 'kospi' || name.includes(query)`).
*   **Checklist Sorting**: 리스트 생성 시 `'KOSPI'`를 최상단에 고정하고, 나머지 종목은 한글 가나다순으로 정렬함.
*   **Visual Feedback**: 체크박스 선택 상태에 따라 부모 라벨의 테두리 색상(`rgba(4, 120, 87, 0.4)`)과 배경색(`rgba(4, 120, 87, 0.04)`)을 동적으로 변경함.

### 4.4. Sorting Algorithms (정렬 알고리즘)
*   **Temporal Recency**: `recommendations` 및 `reports` 데이터는 렌더링 직전 `[...data].sort((a, b) => new Date(b.date) - new Date(a.date))` 공식을 사용하여 최신 날짜가 상단에 오도록 보장함.

### 4.5. State Management & Tooltips (상태 관리 및 툴팁)
*   **Tab Switching Latency**: 차트 탭(`.tab-chart`) 선택 시 Canvas 렌더링 타이밍을 맞추기 위해 `50ms`의 `setTimeout` 지연 후 `initChart()`를 실행함.
*   **Chart Tooltips**: 
    *   배경색 `#080c12`, 테두리 `#101620`, 텍스트색 `#d1d5db`.
    *   제목(Title)은 `bold` 굵기에 `#10b981`(Emerald) 색상을 적용하여 데이터 그룹을 강조함.

---

## 5. Security & Performance (보안 및 성능 최적화)

### 5.1. XSS (Cross-Site Scripting) 방어 원칙
대시보드는 외부 크롤링 데이터를 기반으로 동작하므로, 렌더링 시 태그 인젝션을 원천 차단해야 합니다.
*   **필수 사용 함수**: `web/app.js` 최상단에 정의된 `escapeHTML(str)`
*   **적용 범위**: `innerHTML` 템플릿 리터럴 내부의 모든 변수 `${}`에 감싸서 적용. (예: `${escapeHTML(event.title)}`)
*   **예외**: `onclick` 인라인 바인딩을 금지하고, `createElement` 후 `addEventListener('click', ...)` 방식으로 이벤트를 연결하여 특수 문자열(`&` 등) 파싱 에러를 예방합니다.

### 5.2. 성능 병목 방지
*   **미래 날짜 패딩**: 차트 우측에 미래 이벤트를 표시하기 위해 무의미하게 데이터 배열 크기를 늘리는 대신, X축 라벨만 30일치 연장하고 실제 데이터셋에는 `null`을 삽입하여 렌더링 성능 하락을 방지합니다.
*   **이벤트 리스너 위임 지양**: 대량의 카드나 리스트 아이템이 동적 생성되지만, 상태 변화(필터링, 체크박스 등)가 복잡하지 않으므로 각 노드 생성 시 독립적인 리스너를 바인딩하여 Event Bubbling 오버헤드를 줄입니다.

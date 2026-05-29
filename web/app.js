// XSS 방지를 위한 HTML 이스케이프 함수
function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// 국가별 시그니처 색상 매핑 (온라인 버전 기준)
function getCountryColor(country) {
  const map = {
    '미국': '#3b82f6',    // 신뢰의 블루
    '유로존': '#8b5cf6',  // 로열 퍼플
    '영국': '#ec4899',    // 마젠타 핑크
    '일본': '#f59e0b',    // 선셋 오렌지
    '한국': '#ef4444',    // 다이나믹 레드
    '중국': '#ef4444',    // 레드
    '캐나다': '#14b8a6',  // 틸 그린
    '호주': '#10b981'     // 에메랄드
  };
  return map[country] || '#10b981';
}

// 등급별 눈이 편안한 시그니처 색상 매핑
function getRatingColor(rating) {
  if (!rating) return 'var(--text-main)';
  const r = rating.trim();
  if (r.includes('매수') || r.includes('Buy')) return '#10b981'; // 에메랄드 그린
  if (r.includes('홀딩') || r.includes('Hold') || r.includes('보유') || r.includes('중립')) return '#d97706'; // 황금색
  if (r.includes('매도') || r.includes('Sell') || r.includes('비중축소')) return '#ef4444'; // 로즈 레드
  return 'var(--text-main)';
}

// 탭 전환 핸들러 (clickedBtn 인자 추가하여 ID 기반 동작 지원)
function switchTab(tabId, clickedBtn) {
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
  });
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });

  const targetTab = document.getElementById(tabId);
  if (targetTab) {
    targetTab.classList.add('active');
  }
  
  if (clickedBtn) {
    clickedBtn.classList.add('active');
  } else {
    // fallback: ID로 버튼 찾기
    const btnId = `btn-${tabId}`;
    const btn = document.getElementById(btnId);
    if (btn) btn.classList.add('active');
  }

  // 차트 탭 초기화 지연 기동 (Canvas 렌더링 타이밍 보장 - 50ms)
  if (tabId === 'tab-chart' && !marketChart) {
    setTimeout(initChart, 50);
  }
}

// 전역 상태 변수
let currentDatabase = window.ANALYST_DATABASE || { analysts: [], recommendations: [] };
let marketChart = null;
let chartMode = 'pct'; // 'pct' 또는 'price'
let selectedStocks = ['KOSPI']; // 코스피 기본 선택

// 화면 로드 즉시 렌더링
window.addEventListener('DOMContentLoaded', () => {
  // 1. 이벤트 리스너 바인딩 (보안 및 아키텍처 규칙 준수)
  const tabMap = {
    'btn-tab-analysts': 'tab-analysts',
    'btn-tab-alerts': 'tab-alerts',
    'btn-tab-reports': 'tab-reports',
    'btn-tab-chart': 'tab-chart',
    'btn-tab-calendar': 'tab-calendar'
  };

  Object.entries(tabMap).forEach(([btnId, tabId]) => {
    const btn = document.getElementById(btnId);
    if (btn) btn.addEventListener('click', (e) => switchTab(tabId, e.currentTarget));
  });

  const btnPct = document.getElementById('btn-chart-mode-pct');
  const btnPrice = document.getElementById('btn-chart-mode-price');
  if (btnPct) btnPct.addEventListener('click', () => setChartMode('pct'));
  if (btnPrice) btnPrice.addEventListener('click', () => setChartMode('price'));

  const btnAll = document.getElementById('btn-toggle-all');
  const btnNone = document.getElementById('btn-toggle-none');
  if (btnAll) btnAll.addEventListener('click', () => toggleAllStocks(true));
  if (btnNone) btnNone.addEventListener('click', () => toggleAllStocks(false));

  renderDashboard();
});

function renderDashboard() {
  const analysts = currentDatabase.analysts || [];
  // 온라인 정렬 로직 반영 (최신순)
  const recs = [...(currentDatabase.recommendations || [])].sort((a, b) => new Date(b.date) - new Date(a.date));

  // 2. 동적 필터 버튼 바인딩
  const filterButtonsContainer = document.getElementById('filter-buttons');
  if (filterButtonsContainer) {
    filterButtonsContainer.innerHTML = '';
    
    const allBtn = document.createElement('button');
    allBtn.className = 'filter-btn active';
    allBtn.innerText = '전체보기';
    allBtn.addEventListener('click', () => filterSector('ALL'));
    filterButtonsContainer.appendChild(allBtn);

    const uniqueSectors = [...new Set(analysts.map(a => a.merged_sector))];
    uniqueSectors.forEach(sector => {
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.innerText = sector;
      btn.addEventListener('click', () => filterSector(sector));
      filterButtonsContainer.appendChild(btn);
    });
  }

  renderAnalysts(analysts);
  renderAlerts(recs, analysts);
  const reports = [...(currentDatabase.reports || [])].sort((a, b) => new Date(b.date) - new Date(a.date));
  renderReports(reports, analysts);
  renderStockChecklist();
  renderCalendar();
  renderExternalEvents();
}

function renderAnalysts(analystList) {
  const container = document.getElementById('analysts-container');
  if (!container) return;
  container.innerHTML = '';
  if (analystList.length === 0) {
    container.innerHTML = '<p style="color:var(--text-sub); text-align:center; grid-column:1/-1;">조건에 부합하는 애널리스트가 없습니다.</p>';
    return;
  }
  analystList.forEach(a => {
    const card = document.createElement('div');
    card.className = 'analyst-card';
    card.setAttribute('data-sector', a.merged_sector);
    const tagsHtml = (a.targets || []).map(t => `<span class="tag">${escapeHTML(t)}</span>`).join('');
    card.innerHTML = `
      <div>
        <div class="card-header">
          <div class="profile-info">
            <h3>${escapeHTML(a.name)}</h3>
            <span class="firm-tag">${escapeHTML(a.firm)}</span>
            <span class="position-tag">${escapeHTML(a.position)}</span>
          </div>
          <span class="sector-badge">${escapeHTML(a.merged_sector)}</span>
        </div>
        <div class="award-text">
          <i class="fa-solid fa-trophy"></i>
          <span>${escapeHTML(a.awards)}</span>
        </div>
        <p class="evaluation-text">${escapeHTML(a.evaluation)}</p>
      </div>
      <div>
        <div class="coverage-title">
          <i class="fa-solid fa-chart-line" style="color:var(--accent);"></i>
          <span>대표 커버 기업</span>
        </div>
        <div class="coverage-tags">${tagsHtml}</div>
      </div>
    `;
    container.appendChild(card);
  });
}

function filterSector(sectorName) {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    if (btn.innerText === sectorName || (sectorName === 'ALL' && btn.innerText === '전체보기')) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  document.querySelectorAll('.analyst-card').forEach(card => {
    const cardSector = card.getAttribute('data-sector');
    if (sectorName === 'ALL' || cardSector === sectorName) {
      card.style.display = 'flex';
      card.style.animation = 'fadeIn 0.2s ease';
    } else {
      card.style.display = 'none';
    }
  });
}

function renderAlerts(recs, analysts) {
  const tbody = document.getElementById('alerts-container-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (recs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-sub);">최근 의견 변동 감지 내역이 없습니다.</td></tr>';
    return;
  }
  recs.forEach(r => {
    const aObj = analysts.find(a => a.id === r.analyst_id) || { name: '외부', firm: '기고', position: '위원' };
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><div class="company-cell"><span class="company-name">${escapeHTML(r.stock_name)}</span><span class="company-code">(${escapeHTML(r.stock_code)})</span></div></td>
      <td><span style="font-weight:700;">${escapeHTML(aObj.firm)} ${escapeHTML(aObj.name)}</span><span style="color:var(--text-sub); font-size:0.85rem; margin-left:6px;">${escapeHTML(aObj.position)}</span></td>
      <td><span class="badge-alert ${r.change_type === 'upgrade' ? 'upgrade' : 'downgrade'}">${r.change_type === 'upgrade' ? '🟢 상향' : '🔴 하향'}</span></td>
      <td><div class="rating-flow"><span style="color:${getRatingColor(r.previous_rating)}; font-weight:700;">${escapeHTML(r.previous_rating)}</span><i class="fa-solid fa-circle-arrow-right rating-arrow"></i><span style="color:${getRatingColor(r.current_rating)}; font-weight:700;">${escapeHTML(r.current_rating)}</span></div></td>
      <td class="rating-target">${escapeHTML(r.target_price)}</td>
      <td class="comment-cell"><p class="alert-comment">"${escapeHTML(r.comment)}"</p></td>
      <td style="color:var(--text-sub);">${escapeHTML(r.date)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderReports(reportList, analysts) {
  const container = document.getElementById('reports-container-grid');
  if (!container) return;
  container.innerHTML = '';
  if (reportList.length === 0) {
    container.innerHTML = '<p style="color:var(--text-sub); text-align:center; grid-column:1/-1;">등록된 보고서가 없습니다.</p>';
    return;
  }
  reportList.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id) || { name: '외부', firm: '기고', position: '위원' };
    const card = document.createElement('div');
    card.className = 'report-card';
    card.innerHTML = `
      <div>
        <div class="report-card-header">
          <div><h3 class="report-title">${escapeHTML(rep.title)}</h3><div class="report-meta"><span class="report-author">${escapeHTML(aObj.firm)} ${escapeHTML(aObj.name)} ${escapeHTML(aObj.position)}</span><span style="margin: 0 4px; color: var(--text-sub);">•</span><span>${escapeHTML(rep.date)}</span></div></div>
        </div>
        <p class="report-summary">${escapeHTML(rep.summary)}</p>
      </div>
      <div class="report-footer">
        <div><span style="color:var(--text-sub);">종목: </span><span style="font-weight:700; color:#ffffff;">${escapeHTML(rep.stock_name)}</span></div>
        <div><span style="color:var(--text-sub);">의견: </span><span style="color:${getRatingColor(rep.rating)}; font-weight:700;">${escapeHTML(rep.rating)}</span></div>
        <div class="report-target-box"><span style="color:var(--text-sub); font-weight:normal; font-size:0.8rem;">목표가: </span><span>${escapeHTML(rep.target_price)}</span></div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderCalendar() {
  const container = document.getElementById('calendar-container-body');
  if (!container) return;
  container.innerHTML = '';
  const calendarData = window.CALENDAR_DATA || [];
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const getKorDateStr = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
  const todayStr = getKorDateStr(now);

  const tomorrow = new Date(now); tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = getKorDateStr(tomorrow);

  const dayOfWeek = now.getDay();
  const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const thisWeekStart = new Date(now); thisWeekStart.setDate(now.getDate() + diffToMonday);
  const thisWeekEnd = new Date(thisWeekStart); thisWeekEnd.setDate(thisWeekStart.getDate() + 6);
  const twStartStr = getKorDateStr(thisWeekStart);
  const twEndStr = getKorDateStr(thisWeekEnd);

  const lastWeekEnd = new Date(thisWeekStart); lastWeekEnd.setDate(lastWeekEnd.getDate() - 1);
  const lastWeekStart = new Date(lastWeekEnd); lastWeekStart.setDate(lastWeekStart.getDate() - 6);
  const lwStartStr = getKorDateStr(lastWeekStart);
  const lwEndStr = getKorDateStr(lastWeekEnd);

  const groups = [
    { id: '과거', title: '⏳ 과거 (지난주 이전)', isPast: true, events: [] },
    { id: '지난주', title: '⬅️ 지난주', isPast: true, events: [] },
    { id: '오늘', title: '📌 오늘', isPast: false, events: [] },
    { id: '내일', title: '🚀 내일', isPast: false, events: [] },
    { id: '이번주', title: '📅 이번 주', isPast: false, events: [] },
    { id: '다음주', title: '🗓️ 다음 주', isPast: false, events: [] },
    { id: '이번달', title: '📆 이번 달 (이후)', isPast: false, events: [] }
  ];

  calendarData.forEach(event => {
    const d = event.date;
    if (d < lwStartStr) groups[0].events.push(event);
    else if (d >= lwStartStr && d <= lwEndStr) groups[1].events.push(event);
    else if (d === todayStr) groups[2].events.push(event);
    else if (d === tomorrowStr) groups[3].events.push(event);
    else if (d >= twStartStr && d <= twEndStr) groups[4].events.push(event);
    else if (d > twEndStr && d <= getKorDateStr(new Date(thisWeekEnd.getTime() + 7 * 24 * 60 * 60 * 1000))) groups[5].events.push(event);
    else groups[6].events.push(event);
  });

  groups.forEach(group => {
    const groupDiv = document.createElement('div');
    groupDiv.style.marginBottom = '20px';
    let contentHtml = '';
    if (group.events.length === 0) {
      contentHtml = `<div style="color: var(--text-sub); font-size: 0.85rem; padding: 12px; background: rgba(31, 41, 55, 0.4); border-radius: 6px; text-align: center; border: 1px dashed #374151;">일정 없음</div>`;
    } else {
      contentHtml = group.events.map(e => {
        let resHtml = '';
        if (e.forecast || e.previous) {
          const isPast = e.date < todayStr;
          const joined = [e.forecast ? `예상: ${e.forecast}` : '', e.previous ? `이전: ${e.previous}` : ''].filter(x=>x).join(' | ');
          if (joined) resHtml = `<div class="event-result-text" style="font-size: 0.8rem; color: ${isPast ? '#facc15' : '#9ca3af'}; margin-top: 4px; font-weight: ${isPast ? '600' : '400'};">${isPast ? '✅ 결과치: ' : '📉 예측/이전: '}${joined}</div>`;
        }
        const cColor = getCountryColor(e.country);
        const isHigh = e.impact === 'High';
        const itemStyle = isHigh ? `background: rgba(250, 204, 21, 0.03); border-left: 3px solid #facc15;` : '';
        return `
          <div style="display: flex; align-items: center; gap: 15px; padding: 12px 15px; border-bottom: 1px solid #101620; ${itemStyle}">
            <div style="color: #e2e8f0; font-weight: 600; width: 100px;">${escapeHTML(e.date)}</div>
            <span style="background: ${cColor}15; color: ${cColor}; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; border: 1px solid ${cColor}40;">${escapeHTML(e.country)}</span>
            <div style="color: #ffffff; font-weight: 500; flex: 1;">${escapeHTML(e.title)}${resHtml}</div>
          </div>
        `;
      }).join('');
    }
    const headerColor = group.isPast ? '#9ca3af' : '#10b981';
    if (group.isPast) {
      groupDiv.innerHTML = `<details><summary style="font-size:1rem; font-weight:700; color:${headerColor}; cursor:pointer; padding-bottom:6px; border-bottom:1px solid #1f2937;">${group.title} (${group.events.length}건)</summary><div style="margin-top:12px;">${contentHtml}</div></details>`;
    } else {
      groupDiv.innerHTML = `<div style="font-size:1rem; font-weight:700; color:${headerColor}; margin-bottom:10px; border-bottom:1px solid #1f2937; padding-bottom:6px;">${group.title}</div><div>${contentHtml}</div>`;
    }
    container.appendChild(groupDiv);
  });
}

function renderExternalEvents() {
  const container = document.getElementById('external-events-list');
  if (!container) return;
  container.innerHTML = '';
  const calendarData = window.CALENDAR_DATA || [];
  const todayStr = new Date().toISOString().split('T')[0];
  if (calendarData.length === 0) {
    container.innerHTML = '<p style="color:var(--text-sub); text-align:center; padding: 20px;">예정된 경제 일정이 없습니다.</p>';
    return;
  }
  calendarData.forEach(e => {
    const item = document.createElement('div');
    item.className = 'external-event-item';
    item.setAttribute('data-date', e.date);
    let resHtml = '';
    if (e.forecast || e.previous) {
      const isPast = e.date < todayStr;
      const joined = [e.forecast ? `예상: ${e.forecast}` : '', e.previous ? `이전: ${e.previous}` : ''].filter(x=>x).join(' | ');
      if (joined) resHtml = `<div class="event-result-text" style="font-size: 0.8rem; color: ${isPast ? '#facc15' : '#9ca3af'}; margin-top: 4px;">${isPast ? '✅ 결과치: ' : '📉 예측/이전: '}${joined}</div>`;
    }
    const cColor = getCountryColor(e.country);
    const isHigh = e.impact === 'High';
    const itemStyle = isHigh ? `background: rgba(250, 204, 21, 0.03); border-left: 3px solid #facc15;` : '';
    item.style.cssText += itemStyle;
    item.innerHTML = `
      <div class="event-date" style="color: #e2e8f0; font-weight: 600; width: 90px;">${escapeHTML(e.date)}</div>
      <span style="background: ${cColor}15; color: ${cColor}; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; border: 1px solid ${cColor}40;">${escapeHTML(e.country)}</span>
      <div class="event-title" style="color: #ffffff; font-weight: 500; flex: 1;">${escapeHTML(e.title)}${resHtml}</div>
    `;
    container.appendChild(item);
  });
}

function initChart() {
  const canvas = document.getElementById('marketChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const marketData = window.MARKET_DATA || { dates: [], series: {} };
  const config = {
    type: 'line',
    data: { labels: marketData.dates, datasets: [] },
    options: {
      onHover: (e, activeElements, chart) => {
        if (!chart.scales.x) return;
        const xValue = chart.scales.x.getValueForPixel(e.x);
        document.querySelectorAll('.external-event-item').forEach(el => el.classList.remove('highlighted-event'));
        let needsUpdate = false;
        const annotations = chart.options.plugins.annotation?.annotations || {};
        if (xValue >= 0 && xValue < chart.data.labels.length) {
          const hoveredDate = chart.data.labels[xValue];
          let firstScrolled = false;
          for (const key in annotations) {
            const ann = annotations[key];
            if (!ann.original) ann.original = { borderColor: ann.borderColor, borderWidth: ann.borderWidth, labelDisplay: ann.label?.display };
            if (ann.xMin === hoveredDate) {
              if (ann.borderColor !== 'rgba(250, 204, 21, 1)') {
                ann.borderColor = 'rgba(250, 204, 21, 1)'; ann.borderWidth = 3; if (ann.label) ann.label.display = true; needsUpdate = true;
              }
              const targetEl = document.querySelector(`.external-event-item[data-date="${ann.originalDate || hoveredDate}"]`);
              if (targetEl) {
                targetEl.classList.add('highlighted-event');
                if (!firstScrolled) { targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); firstScrolled = true; }
              }
            } else {
              if (ann.borderColor === 'rgba(250, 204, 21, 1)') {
                ann.borderColor = ann.original.borderColor; ann.borderWidth = ann.original.borderWidth;
                if (ann.label) ann.label.display = ann.original.labelDisplay; needsUpdate = true;
              }
            }
          }
        }
        if (needsUpdate) chart.update('none');
      },
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: 80 } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, position: 'top', labels: { color: '#e2e8f0', font: { family: 'Inter', size: 11 } } },
        tooltip: {
          backgroundColor: '#080c12', titleColor: '#10b981', bodyColor: '#e2e8f0', borderColor: '#101620',
          borderWidth: 1, padding: 12, titleFont: { weight: 'bold' }
        }
      },
      scales: {
        x: { grid: { color: '#101620', borderColor: '#101620' }, ticks: { color: '#9ca3af', font: { size: 10 } } },
        y: { type: 'linear', display: true, position: 'left', grid: { color: '#101620', borderColor: '#101620' }, ticks: { color: '#9ca3af', font: { size: 10 } } }
      }
    }
  };
  marketChart = new Chart(ctx, config);
  updateChart();
}

function updateChart() {
  if (!marketChart) return;
  const marketData = window.MARKET_DATA || { dates: [], series: {} };
  const datasets = [];
  const colors = { 'KOSPI': '#10b981', 'SK하이닉스': '#06b6d4', '삼성전자': '#3b82f6', '삼양식품': '#f59e0b', '알테오젠': '#ec4899', '한화에어로스페이스': '#f97316', '한국전력': '#a855f7', '에코프로비엠': '#84cc16' };
  const defaultColors = ['#06b6d4', '#f59e0b', '#ec4899', '#f97316', '#a855f7', '#84cc16', '#3b82f6', '#14b8a6', '#6366f1'];
  let colorIndex = 0;

  const hasKospi = selectedStocks.includes('KOSPI');
  const hasOther = selectedStocks.some(s => s !== 'KOSPI');
  let yTitleText = chartMode === 'pct' ? '누적 수익률 (%)' : '주가 (KRW)';
  if (!hasOther && hasKospi) yTitleText = '코스피 지수 (PT)';

  const scales = {
    x: marketChart.options.scales.x,
    y: {
      type: 'linear', display: true, position: 'left', grid: { color: '#101620' },
      ticks: { color: '#9ca3af', callback: function(v) { if (!hasOther && hasKospi) return v.toLocaleString() + ' pt'; return chartMode === 'pct' ? v.toFixed(1) + '%' : v.toLocaleString(); } },
      title: { display: true, text: yTitleText, color: '#e2e8f0' }
    }
  };

  if (hasKospi && hasOther) {
    scales.y2 = { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#10b981', callback: function(v) { return v.toLocaleString() + ' pt'; } }, title: { display: true, text: '코스피 지수 (PT)', color: '#10b981' } };
  } else {
    delete marketChart.options.scales.y2;
  }

  // 미래 30일 패딩
  const today = new Date(); const todayStr = today.toISOString().split('T')[0];
  const paddedDates = [...marketData.dates];
  let lastDate = new Date(paddedDates[paddedDates.length - 1]);
  if (isNaN(lastDate)) lastDate = today;
  for (let i = 1; i <= 30; i++) { const n = new Date(lastDate); n.setDate(n.getDate() + i); paddedDates.push(n.toISOString().split('T')[0]); }
  marketChart.data.labels = paddedDates;

  selectedStocks.forEach(stock => {
    const series = marketData.series[stock];
    if (!series) return;
    let final = [];
    if (chartMode === 'pct' && stock !== 'KOSPI') { const base = series[0]; final = series.map(p => base === 0 ? 0 : ((p - base) / base) * 100); }
    else final = series;
    const paddedSeries = [...final]; for (let i = 0; i < 30; i++) paddedSeries.push(null);
    const color = colors[stock] || defaultColors[colorIndex++ % defaultColors.length];
    datasets.push({ label: stock, data: paddedSeries, borderColor: color, backgroundColor: color + '15', borderWidth: stock === 'KOSPI' ? 2.5 : 2, pointRadius: 1, pointHoverRadius: 4, tension: 0.15, yAxisID: (chartMode === 'price' && stock === 'KOSPI' && hasOther) ? 'y2' : 'y' });
  });

  // 어노테이션
  const annotations = {};
  const groupedEvents = {};
  (window.CALENDAR_DATA || []).forEach(ev => {
    let m = ev.date;
    if (!paddedDates.includes(m)) {
      const t = new Date(m).getTime(); let closest = paddedDates[0], min = Infinity;
      paddedDates.forEach(d => { const diff = Math.abs(new Date(d).getTime() - t); if (diff < min) { min = diff; closest = d; } });
      m = closest;
    }
    if (!groupedEvents[m]) groupedEvents[m] = [];
    groupedEvents[m].push({ ...ev, originalDate: ev.date });
  });

  let fIndex = 0;
  Object.keys(groupedEvents).forEach(m => {
    const evs = groupedEvents[m]; const isPast = evs[0].originalDate < todayStr;
    const contentArr = [];
    evs.forEach((ev, idx) => {
      contentArr.push(`[${ev.country}] ${ev.title}`);
      if (ev.forecast || ev.previous) contentArr.push(`  ${isPast ? '결과' : '예측'}: 예상 ${ev.forecast} | 이전 ${ev.previous}`);
      if (idx < evs.length - 1) contentArr.push('');
    });
    annotations[`event_${fIndex++}`] = {
      type: 'line', xMin: m, xMax: m, originalDate: evs[0].originalDate,
      borderColor: isPast ? 'rgba(156, 163, 175, 0.2)' : 'rgba(250, 204, 21, 0.2)', borderWidth: 1.5, borderDash: [3, 3],
      label: { display: false, content: contentArr, position: 'start', color: isPast ? '#ffffff' : '#000000', backgroundColor: isPast ? 'rgba(75, 85, 99, 0.95)' : 'rgba(250, 204, 21, 0.95)', borderRadius: 6, font: { size: 10, weight: 'bold' }, padding: 8, yAdjust: -30 }
    };
  });

  marketChart.options.plugins.annotation = { clip: false, annotations: annotations };
  marketChart.options.scales = scales;
  marketChart.data.datasets = datasets;
  marketChart.update();
}

function setChartMode(mode) {
  chartMode = mode;
  document.getElementById('btn-chart-mode-pct').classList.toggle('active', mode === 'pct');
  document.getElementById('btn-chart-mode-price').classList.toggle('active', mode === 'price');
  const desc = document.getElementById('chart-desc');
  if (mode === 'pct') desc.innerText = '* 2025년 6월 기점을 0%로 가정하고 코스피 대비 개별 종목들의 누적 수익률 추이를 비교 분석합니다.';
  else desc.innerText = '* 선택한 종목들의 원화(KRW) 실제 주가 추이를 코스피 지수(우측 축)와 연동하여 비교 분석합니다.';
  updateChart();
}

function renderStockChecklist() {
  const container = document.getElementById('stock-checklist');
  if (!container) return;
  container.innerHTML = '';
  const marketData = window.MARKET_DATA || { dates: [], series: {} };
  const sortedStocks = ['KOSPI', ...Object.keys(marketData.series).filter(s => s !== 'KOSPI').sort()];
  sortedStocks.forEach(stock => {
    const series = marketData.series[stock];
    const currentPrice = series[series.length - 1];
    const priceStr = stock === 'KOSPI' ? currentPrice.toLocaleString() + ' pt' : currentPrice.toLocaleString() + ' 원';
    const isChecked = selectedStocks.includes(stock);
    const item = document.createElement('label');
    item.className = 'stock-item-label';
    item.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border: 1px solid var(--card-border); border-radius: 6px; background: #080c12; cursor: pointer; transition: var(--transition); user-select: none;";
    item.setAttribute('data-stock-name', stock);
    item.innerHTML = `<div style="display: flex; align-items: center; gap: 10px;"><input type="checkbox" class="stock-chk" value="${escapeHTML(stock)}" ${isChecked ? 'checked' : ''} onchange="handleStockCheck(this)" style="accent-color: var(--primary); cursor: pointer;"><span style="font-size: 0.88rem; font-weight: ${stock === 'KOSPI' ? '700' : '500'}; color: ${stock === 'KOSPI' ? '#10b981' : '#ffffff'};">${escapeHTML(stock)}</span></div><span style="font-size: 0.8rem; color: var(--text-sub);">${priceStr}</span>`;
    if (isChecked) { item.style.borderColor = 'rgba(4, 120, 87, 0.4)'; item.style.background = 'rgba(4, 120, 87, 0.04)'; }
    container.appendChild(item);
  });
}

function handleStockCheck(chk) {
  const stock = chk.value;
  const label = chk.closest('.stock-item-label');
  if (chk.checked) { if (!selectedStocks.includes(stock)) selectedStocks.push(stock); label.style.borderColor = 'rgba(4, 120, 87, 0.4)'; label.style.background = 'rgba(4, 120, 87, 0.04)'; }
  else { selectedStocks = selectedStocks.filter(s => s !== stock); label.style.borderColor = 'var(--card-border)'; label.style.background = '#080c12'; }
  updateChart();
}

function filterStockChecklist() {
  const query = document.getElementById('stock-search').value.toLowerCase().trim();
  document.querySelectorAll('.stock-item-label').forEach(label => {
    const name = label.getAttribute('data-stock-name').toLowerCase();
    label.style.display = (name === 'kospi' || name.includes(query)) ? 'flex' : 'none';
  });
}

function toggleAllStocks(select) {
  const chks = document.querySelectorAll('.stock-chk');
  selectedStocks = ['KOSPI'];
  chks.forEach(chk => {
    const stock = chk.value; if (stock === 'KOSPI') return;
    chk.checked = select; const label = chk.closest('.stock-item-label');
    if (select) { selectedStocks.push(stock); label.style.borderColor = 'rgba(4, 120, 87, 0.4)'; label.style.background = 'rgba(4, 120, 87, 0.04)'; }
    else { label.style.borderColor = 'var(--card-border)'; label.style.background = '#080c12'; }
  });
  updateChart();
}

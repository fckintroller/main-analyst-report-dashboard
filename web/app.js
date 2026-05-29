// 등급별 눈이 편안한 시그니처 색상 매핑
function getRatingColor(rating) {
  if (!rating) return 'var(--text-main)';
  const r = rating.trim();
  if (r.includes('매수') || r.includes('Buy')) return '#10b981'; // 에메랄드 그린
  if (r.includes('홀딩') || r.includes('Hold') || r.includes('보유') || r.includes('중립')) return '#d97706'; // 황금색
  if (r.includes('매도') || r.includes('Sell') || r.includes('비중축소')) return '#ef4444'; // 로즈 레드
  return 'var(--text-main)';
}

// 탭 전환 핸들러
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
  });
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });

  document.getElementById(tabId).classList.add('active');
  event.currentTarget.classList.add('active');

  // 차트 탭 초기화 지연 기동
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
  renderDashboard();
});

function renderDashboard() {
  const analysts = currentDatabase.analysts;
  const recs = [...currentDatabase.recommendations].sort((a, b) => new Date(b.date) - new Date(a.date));

  // 2. 동적 필터 버튼 바인딩
  const filterButtonsContainer = document.getElementById('filter-buttons');
  if (filterButtonsContainer) {
    filterButtonsContainer.innerHTML = '<button class="filter-btn active" onclick="filterSector(\'ALL\')">전체보기</button>';
    const uniqueSectors = [...new Set(analysts.map(a => a.merged_sector))];
    uniqueSectors.forEach(sector => {
      const btn = document.createElement('button');
      btn.className = 'filter-btn';
      btn.innerText = sector;
      btn.setAttribute('onclick', `filterSector('${sector}')`);
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
    const tagsHtml = a.targets.map(t => `<span class="tag">${t}</span>`).join('');
    card.innerHTML = `
      <div>
        <div class="card-header">
          <div class="profile-info">
            <h3>${a.name}</h3>
            <span class="firm-tag">${a.firm}</span>
            <span class="position-tag">${a.position}</span>
          </div>
          <span class="sector-badge">${a.merged_sector}</span>
        </div>
        <div class="award-text">
          <i class="fa-solid fa-trophy"></i>
          <span>${a.awards}</span>
        </div>
        <p class="evaluation-text">${a.evaluation}</p>
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
      <td><div class="company-cell"><span class="company-name">${r.stock_name}</span><span class="company-code">(${r.stock_code})</span></div></td>
      <td><span style="font-weight:700;">${aObj.firm} ${aObj.name}</span><span style="color:var(--text-sub); font-size:0.85rem; margin-left:6px;">${aObj.position}</span></td>
      <td><span class="badge-alert ${r.change_type === 'upgrade' ? 'upgrade' : 'downgrade'}">${r.change_type === 'upgrade' ? '🟢 상향' : '🔴 하향'}</span></td>
      <td><div class="rating-flow"><span style="color:${getRatingColor(r.previous_rating)}; font-weight:700;">${r.previous_rating}</span><i class="fa-solid fa-circle-arrow-right rating-arrow"></i><span style="color:${getRatingColor(r.current_rating)}; font-weight:700;">${r.current_rating}</span></div></td>
      <td class="rating-target">${r.target_price}</td>
      <td class="comment-cell"><p class="alert-comment">"${r.comment}"</p></td>
      <td style="color:var(--text-sub);">${r.date}</td>
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
          <div><h3 class="report-title">${rep.title}</h3><div class="report-meta"><span class="report-author">${aObj.firm} ${aObj.name} ${aObj.position}</span><span style="margin: 0 4px; color: var(--text-sub);">•</span><span>${rep.date}</span></div></div>
        </div>
        <p class="report-summary">${rep.summary}</p>
      </div>
      <div class="report-footer">
        <div><span style="color:var(--text-sub);">종목: </span><span style="font-weight:700; color:#ffffff;">${rep.stock_name}</span></div>
        <div><span style="color:var(--text-sub);">의견: </span><span style="color:${getRatingColor(rep.rating)}; font-weight:700;">${rep.rating}</span></div>
        <div class="report-target-box"><span style="color:var(--text-sub); font-weight:normal; font-size:0.8rem;">목표가: </span><span>${rep.target_price}</span></div>
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

  // 간단한 그룹화 로직 (축약)
  const groups = [
    { id: '오늘', title: '📌 오늘', events: calendarData.filter(e => e.date === todayStr) },
    { id: '예정', title: '📅 예정된 일정', events: calendarData.filter(e => e.date > todayStr) },
    { id: '지난', title: '⏳ 지난 일정', events: calendarData.filter(e => e.date < todayStr), isPast: true }
  ];

  groups.forEach(group => {
    if (group.events.length === 0 && !group.isPast) return;
    const groupDiv = document.createElement('div');
    groupDiv.style.marginBottom = '20px';
    const content = group.events.map(e => `
      <div style="display: flex; align-items: center; gap: 15px; padding: 12px 15px; border-bottom: 1px solid #101620;">
        <div style="color: #e2e8f0; font-weight: 600; width: 100px;">${e.date}</div>
        <span style="background: rgba(4, 120, 87, 0.15); color: #10b981; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">${e.country}</span>
        <div style="color: #ffffff; font-weight: 500; flex: 1;">${e.title}</div>
      </div>
    `).join('');
    
    if (group.isPast) {
      groupDiv.innerHTML = `<details><summary style="cursor:pointer; color:#9ca3af; font-weight:700; margin-bottom:10px;">${group.title} (${group.events.length}건)</summary>${content}</details>`;
    } else {
      groupDiv.innerHTML = `<div style="font-size:1rem; font-weight:700; color:#10b981; margin-bottom:10px; border-bottom:1px solid #1f2937; padding-bottom:6px;">${group.title}</div>${content}`;
    }
    container.appendChild(groupDiv);
  });
}

function renderExternalEvents() {
  const container = document.getElementById('external-events-list');
  if (!container) return;
  container.innerHTML = (window.CALENDAR_DATA || []).map(e => `
    <div class="external-event-item" data-date="${e.date}">
      <div class="event-date" style="color: #e2e8f0; font-weight: 600; width: 90px;">${e.date}</div>
      <span style="background: rgba(4, 120, 87, 0.15); color: #10b981; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem;">${e.country}</span>
      <div class="event-title" style="color: #ffffff; font-weight: 500; flex: 1;">${e.title}</div>
    </div>
  `).join('');
}

function initChart() {
  const canvas = document.getElementById('marketChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const marketData = window.MARKET_DATA || { dates: [], series: {} };
  marketChart = new Chart(ctx, {
    type: 'line',
    data: { labels: marketData.dates, datasets: [] },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: true, position: 'top', labels: { color: '#e2e8f0' } } },
      scales: {
        x: { grid: { color: '#101620' }, ticks: { color: '#9ca3af' } },
        y: { grid: { color: '#101620' }, ticks: { color: '#9ca3af' } }
      }
    }
  });
  updateChart();
}

function updateChart() {
  if (!marketChart) return;
  const marketData = window.MARKET_DATA || { dates: [], series: {} };
  const datasets = [];
  const colors = { 'KOSPI': '#10b981' };
  const defaultColors = ['#06b6d4', '#f59e0b', '#ec4899', '#f97316', '#a855f7', '#84cc16', '#3b82f6'];
  let colorIdx = 0;

  selectedStocks.forEach(stock => {
    const series = marketData.series[stock];
    if (!series) return;
    let data = series;
    if (chartMode === 'pct' && stock !== 'KOSPI') {
      const base = series[0];
      data = series.map(p => base === 0 ? 0 : ((p - base) / base) * 100);
    }
    const color = colors[stock] || defaultColors[colorIdx++ % defaultColors.length];
    datasets.push({
      label: stock, data: data, borderColor: color, backgroundColor: color + '15',
      borderWidth: stock === 'KOSPI' ? 2.5 : 2, tension: 0.15,
      yAxisID: (stock === 'KOSPI' && selectedStocks.length > 1) ? 'y2' : 'y'
    });
  });

  const hasKospi = selectedStocks.includes('KOSPI');
  const hasOther = selectedStocks.length > (hasKospi ? 1 : 0);
  
  marketChart.options.scales.y.title = { display: true, text: chartMode === 'pct' ? '수익률 (%)' : '가격', color: '#e2e8f0' };
  if (hasKospi && hasOther) {
    marketChart.options.scales.y2 = { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#10b981' } };
  } else {
    delete marketChart.options.scales.y2;
  }

  marketChart.data.datasets = datasets;
  marketChart.update();
}

function setChartMode(mode) {
  chartMode = mode;
  document.getElementById('btn-chart-mode-pct').classList.toggle('active', mode === 'pct');
  document.getElementById('btn-chart-mode-price').classList.toggle('active', mode === 'price');
  updateChart();
}

function renderStockChecklist() {
  const container = document.getElementById('stock-checklist');
  if (!container) return;
  const marketData = window.MARKET_DATA || { series: {} };
  const stocks = ['KOSPI', ...Object.keys(marketData.series).filter(s => s !== 'KOSPI').sort()];
  container.innerHTML = stocks.map(stock => {
    const isChecked = selectedStocks.includes(stock);
    return `
      <label class="stock-item-label" style="display: flex; align-items: center; gap: 10px; padding: 8px 12px; border: 1px solid ${isChecked ? 'rgba(4,120,87,0.4)' : 'var(--card-border)'}; border-radius: 6px; background: ${isChecked ? 'rgba(4,120,87,0.04)' : '#080c12'}; cursor: pointer;">
        <input type="checkbox" value="${stock}" ${isChecked ? 'checked' : ''} onchange="handleStockCheck(this)">
        <span style="font-size: 0.88rem; color: ${stock === 'KOSPI' ? '#10b981' : '#ffffff'};">${stock}</span>
      </label>
    `;
  }).join('');
}

function handleStockCheck(chk) {
  const stock = chk.value;
  if (chk.checked) { if (!selectedStocks.includes(stock)) selectedStocks.push(stock); }
  else { selectedStocks = selectedStocks.filter(s => s !== stock); }
  renderStockChecklist();
  updateChart();
}

function filterStockChecklist() {
  const query = document.getElementById('stock-search').value.toLowerCase();
  document.querySelectorAll('.stock-item-label').forEach(label => {
    const name = label.innerText.toLowerCase();
    label.style.display = (name.includes(query) || name.includes('kospi')) ? 'flex' : 'none';
  });
}

function toggleAllStocks(select) {
  const marketData = window.MARKET_DATA || { series: {} };
  if (select) selectedStocks = Object.keys(marketData.series);
  else selectedStocks = ['KOSPI'];
  renderStockChecklist();
  updateChart();
}

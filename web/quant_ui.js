document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  setTimeout(() => {
    if (!window.QUANT_DATA) return;
    renderMacroChart();
    renderMoneyFlowChart();
    renderDartTable();
    renderEpsTable();
    renderSectorMap();
    renderScorecard();
  }, 200);
});

function html(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      document.querySelectorAll(".sidebar-sub-nav").forEach((n) => {
        n.style.display = "none";
      });

      this.classList.add("active");
      const targetId = this.id.replace("btn-", "");
      const target = document.getElementById(targetId);
      if (target) target.classList.add("active");

      const subNav = document.getElementById("nav-sub-" + targetId.replace("tab-", ""));
      if (subNav) {
        subNav.style.display = "flex";
        if (!subNav.querySelector(".sub-tab-btn.active")) {
          subNav.querySelector(".sub-tab-btn")?.click();
        }
      }

      if (targetId === "tab-macro") {
        renderMacroChart();
        renderMoneyFlowChart();
      }
    });
  });
}

function switchSubTab(targetId, btn) {
  const parentNav = btn.closest(".sidebar-sub-nav");
  if (!parentNav) return;

  parentNav.querySelectorAll(".sub-tab-btn").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");

  const mainTabId = "tab-" + parentNav.id.replace("nav-sub-", "");
  const parentContent = document.getElementById(mainTabId);
  if (!parentContent) return;

  parentContent.querySelectorAll(".sub-tab-content").forEach((c) => c.classList.remove("active"));
  document.getElementById("sub-" + targetId)?.classList.add("active");
}
window.switchSubTab = switchSubTab;

let chartInstances = [];

function createChartCanvas(containerId, title) {
  const container = document.getElementById(containerId);
  if (!container) return null;

  const wrapper = document.createElement("div");
  wrapper.style.background = "var(--card-bg)";
  wrapper.style.border = "1px solid var(--card-border)";
  wrapper.style.borderRadius = "8px";
  wrapper.style.padding = "15px";

  const h4 = document.createElement("h4");
  h4.style.fontSize = "0.95rem";
  h4.style.color = "var(--text-heading)";
  h4.style.marginBottom = "10px";
  h4.innerText = title;

  const canvasContainer = document.createElement("div");
  canvasContainer.style.position = "relative";
  canvasContainer.style.height = "250px";

  const canvas = document.createElement("canvas");
  canvasContainer.appendChild(canvas);
  wrapper.appendChild(h4);
  wrapper.appendChild(canvasContainer);
  container.appendChild(wrapper);

  return canvas.getContext("2d");
}

function latestValue(rows, candidates) {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const keys = Array.isArray(candidates) ? candidates : [candidates];
  for (let i = rows.length - 1; i >= 0; i--) {
    for (const key of keys) {
      const raw = rows[i]?.[key];
      const value = Number(String(raw ?? "").replace(/,/g, ""));
      if (!Number.isNaN(value)) return value;
    }
  }
  return null;
}

function numericValue(row, key) {
  return Number(String(row?.[key] ?? "").replace(/,/g, "")) || 0;
}

function renderMacroChart() {
  const macroData = window.QUANT_DATA?.macro;
  if (!macroData || !window.Chart) return;

  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];

  ["macro-rates-charts-dynamic", "macro-commodity-charts", "macro-global-charts", "macro-index-charts"].forEach((id) => {
    const container = document.getElementById(id);
    if (container) container.innerHTML = "";
  });

  const createLineChart = (containerId, title, dataArray, dateKey, valKey, color) => {
    if (!Array.isArray(dataArray) || dataArray.length === 0) return;
    const ctx = createChartCanvas(containerId, title);
    if (!ctx) return;
    const recent = dataArray.slice(-100);

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: recent.map((d) => String(d[dateKey] ?? "").substring(0, 10)),
        datasets: [{
          label: title,
          data: recent.map((d) => numericValue(d, valKey)),
          borderColor: color,
          backgroundColor: color + "20",
          borderWidth: 2,
          fill: true,
          tension: 0.1,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { maxTicksLimit: 5, color: "#6b7280" } },
          y: { ticks: { color: "#6b7280" } },
        },
      },
    });
    chartInstances.push(chart);
  };

  createLineChart("macro-rates-charts-dynamic", "미국 10년물 국채 금리", macroData.TNX, "Date", "Close", "#ef4444");
  createLineChart("macro-commodity-charts", "달러 인덱스", macroData.DXY, "Date", "Close", "#3b82f6");
  createLineChart("macro-commodity-charts", "WTI 원유", macroData.WTI, "Date", "Close", "#f59e0b");
  createLineChart("macro-commodity-charts", "금 가격", macroData.Gold, "Date", "Close", "#eab308");
  createLineChart("macro-global-charts", "미국 M2 통화량", macroData.M2SL, "DATE", "M2SL", "#10b981");
  createLineChart("macro-global-charts", "연준 총자산", macroData.WALCL, "DATE", "WALCL", "#8b5cf6");
}

function renderMoneyFlowChart() {
  const flowData = window.QUANT_DATA?.money_flow;
  if (!flowData || !window.Chart) return;

  const createBarChart = (containerId, title, dataArray, dateKey, series) => {
    if (!Array.isArray(dataArray) || dataArray.length === 0) return;
    const ctx = createChartCanvas(containerId, title);
    if (!ctx) return;
    const recent = dataArray.slice(-40);

    const chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: recent.map((d) => d[dateKey]),
        datasets: series.map((s) => ({
          label: s.label,
          data: recent.map((d) => numericValue(d, s.key)),
          backgroundColor: s.color,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: "#d1d5db" } } },
        scales: {
          x: { ticks: { maxTicksLimit: 10, color: "#6b7280" } },
          y: { ticks: { color: "#6b7280" } },
        },
      },
    });
    chartInstances.push(chart);
  };

  createBarChart("macro-index-charts", "KOSDAQ 순매수 추이", flowData.kosdaq_trend, "날짜", [
    { label: "외국인", key: "외국인", color: "#3b82f6" },
    { label: "개인", key: "개인", color: "#ef4444" },
    { label: "연기금등", key: "연기금등", color: "#10b981" },
  ]);
  createBarChart("macro-index-charts", "고객예탁금 및 신용잔고", flowData.market_funds_trend, "날짜_날짜", [
    { label: "고객예탁금", key: "고객예탁금_고객예탁금", color: "#f59e0b" },
    { label: "신용잔고", key: "신용잔고_신용잔고", color: "#ec4899" },
  ]);

  const programSeries = [
    { label: "차익", key: "차익거래_순매수", color: "#8b5cf6" },
    { label: "비차익", key: "비차익거래_순매수", color: "#06b6d4" },
  ];
  createBarChart("macro-index-charts", "KOSPI 프로그램 순매수", [...(flowData.program_kospi || [])].reverse(), "시간_시간", programSeries);
  createBarChart("macro-index-charts", "KOSDAQ 프로그램 순매수", [...(flowData.program_kosdaq || [])].reverse(), "시간_시간", programSeries);
}

function renderDartTable() {
  const dartData = window.QUANT_DATA?.valuation;
  const tbody = document.querySelector("#dart-table tbody");
  if (!dartData || !tbody) return;

  let allEvents = [];
  if (dartData.dart_buybacks) allEvents = allEvents.concat(dartData.dart_buybacks.map((d) => ({ ...d, type: "자사주" })));
  if (dartData.dart_dividends) allEvents = allEvents.concat(dartData.dart_dividends.map((d) => ({ ...d, type: "배당" })));
  if (dartData.dart_insiders) allEvents = allEvents.concat(dartData.dart_insiders.map((d) => ({ ...d, type: "지분변동" })));

  if (allEvents.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px; color:var(--text-sub);">금일 주요 DART 공시가 없습니다.</td></tr>';
    return;
  }

  allEvents.sort((a, b) => String(b.rcept_dt || "").localeCompare(String(a.rcept_dt || "")));
  tbody.innerHTML = allEvents.slice(0, 50).map((ev) => {
    const badgeColor = ev.type === "배당" ? "#8b5cf6" : ev.type === "지분변동" ? "#f59e0b" : "#10b981";
    const badge = `<span class="badge-alert" style="color:${badgeColor}; border-color:${badgeColor}; background:${badgeColor}1a;">${html(ev.type)}</span>`;
    return `
      <tr>
        <td>${html(ev.rcept_dt)}</td>
        <td><div class="company-cell"><span class="company-name">${html(ev.corp_name)}</span></div></td>
        <td>${badge} ${html(ev.report_nm)}</td>
        <td><a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${html(ev.rcept_no)}" target="_blank" style="color:#3b82f6; text-decoration:none;">${html(ev.rcept_no)}</a></td>
      </tr>
    `;
  }).join("");
}

function renderEpsTable() {
  const epsData = window.QUANT_DATA?.valuation?.earnings_consensus;
  const tbody = document.querySelector("#eps-table tbody");
  const thead = document.querySelector("#eps-table thead tr");
  if (!Array.isArray(epsData) || !tbody) return;

  if (thead) {
    thead.innerHTML = "<th>종목명 (코드)</th><th>최근 가치지표</th><th>최근 연도 영업이익</th><th>올해 예상</th><th>내년 예상</th>";
  }

  const formatNum = (value) => {
    const num = Number(String(value ?? "").replace(/,/g, ""));
    return Number.isFinite(num) ? num.toLocaleString("ko-KR") : "-";
  };

  const rows = [];
  epsData.forEach((item) => {
    try {
      const raw = JSON.parse(item.consensus_raw);
      const cols = Object.keys(raw);
      const labelCol = cols.find((c) => c.includes("주요재무정보"));
      if (!labelCol) return;

      const findRow = (names) => Object.keys(raw[labelCol]).find((k) => names.some((name) => String(raw[labelCol][k]).includes(name)));
      const opRow = findRow(["영업이익"]);
      const epsRow = findRow(["EPS"]);
      const perRow = findRow(["PER"]);
      const bpsRow = findRow(["BPS"]);
      const pbrRow = findRow(["PBR"]);
      if (opRow == null) return;

      const yearCols = cols.filter((c) => c.includes("연간")).sort();
      if (yearCols.length < 3) return;

      const [lastYearCol, thisYearCol, nextYearCol] = yearCols.slice(-3);
      const metrics = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.8rem; color:var(--text-sub);">
          <div>PER: <span style="font-weight:700; color:#3b82f6;">${html(raw[lastYearCol][perRow] || "-")}</span></div>
          <div>PBR: <span style="font-weight:700; color:#8b5cf6;">${html(raw[lastYearCol][pbrRow] || "-")}</span></div>
          <div>EPS: <span style="font-weight:600; color:var(--text-main);">${formatNum(raw[lastYearCol][epsRow])}</span></div>
          <div>BPS: <span style="font-weight:600; color:var(--text-main);">${formatNum(raw[lastYearCol][bpsRow])}</span></div>
        </div>
      `;

      rows.push(`
        <tr>
          <td>
            <div class="company-name" style="font-size:0.95rem; font-weight:700;">${html(item.corp_name || item.ticker)}</div>
            <div class="company-code" style="font-size:0.75rem; color:var(--text-sub);">${html(item.ticker)}</div>
          </td>
          <td>${metrics}</td>
          <td>${formatNum(raw[lastYearCol][opRow])}</td>
          <td style="font-weight:700; color:#10b981;">${formatNum(raw[thisYearCol][opRow])}</td>
          <td style="font-weight:700; color:#3b82f6;">${formatNum(raw[nextYearCol][opRow])}</td>
        </tr>
      `);
    } catch (_) {
      // Skip malformed source rows.
    }
  });

  tbody.innerHTML = rows.join("") || '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-sub);">실적 컨센서스 데이터가 없습니다.</td></tr>';
}

function renderSectorMap() {
  const sectorData = window.QUANT_DATA?.money_flow?.sector_returns;
  const container = document.getElementById("sector-map");
  if (!Array.isArray(sectorData) || !container) return;

  container.innerHTML = "";
  sectorData.forEach((sector) => {
    const name = sector["업종명"];
    const pct = sector["전일대비"];
    if (!name || !pct) return;

    const isUp = String(pct).includes("+") || Number.parseFloat(pct) > 0;
    const isDown = String(pct).includes("-");
    const box = document.createElement("div");
    box.className = `sector-box ${isUp ? "sector-up" : isDown ? "sector-down" : "sector-flat"}`;
    box.innerHTML = `<div style="font-size:0.9rem;">${html(name)}</div><div style="font-size:1.1rem; margin-top:5px;">${html(pct)}</div>`;
    container.appendChild(box);
  });
}

function renderScorecard() {
  const container = document.getElementById("scorecard-container");
  if (!container) return;

  const macro = window.QUANT_DATA?.macro || {};
  const fearVal = window.QUANT_DATA?.sentiment?.fear_greed?.value ?? null;
  const dxy = latestValue(macro.DXY, "Close");
  const tnx = latestValue(macro.TNX, "Close");
  const dgs10 = latestValue(macro.DGS10, "DGS10");
  const dgs2 = latestValue(macro.DGS2, "DGS2");
  const hy = latestValue(macro.BAMLH0A0HYM2, "BAMLH0A0HYM2");
  const unrate = latestValue(macro.UNRATE, "UNRATE");
  const m2Arr = macro.M2SL || [];

  let m2Yoy = null;
  if (m2Arr.length >= 13) {
    const latest = Number(m2Arr[m2Arr.length - 1].M2SL);
    const yearAgo = Number(m2Arr[m2Arr.length - 13].M2SL);
    if (Number.isFinite(latest) && Number.isFinite(yearAgo) && yearAgo !== 0) {
      m2Yoy = ((latest / yearAgo) - 1) * 100;
    }
  }

  const yieldSpread = dgs10 !== null && dgs2 !== null ? dgs10 - dgs2 : null;
  const signal = {
    dxy: dxy === null ? null : dxy < 100 ? 1 : dxy < 106 ? 0 : -1,
    tnx: tnx === null ? null : tnx < 4 ? 1 : tnx < 5 ? 0 : -1,
    spread: yieldSpread === null ? null : yieldSpread > 0.5 ? 1 : yieldSpread > 0 ? 0 : -1,
    hy: hy === null ? null : hy < 3.5 ? 1 : hy < 5 ? 0 : -1,
    fear: fearVal === null ? null : fearVal > 55 ? 1 : fearVal > 30 ? 0 : -1,
    unrate: unrate === null ? null : unrate < 4 ? 1 : unrate < 5.5 ? 0 : -1,
    m2: m2Yoy === null ? null : m2Yoy > 3 ? 1 : m2Yoy > 0 ? 0 : -1,
  };

  const indicators = [
    { name: "달러 인덱스", value: dxy, fmt: (v) => v.toFixed(2), sig: signal.dxy },
    { name: "미국 10년물 금리", value: tnx, fmt: (v) => `${v.toFixed(2)}%`, sig: signal.tnx },
    { name: "장단기 금리차", value: yieldSpread, fmt: (v) => `${v.toFixed(2)}%`, sig: signal.spread },
    { name: "하이일드 스프레드", value: hy, fmt: (v) => `${v.toFixed(2)}%`, sig: signal.hy },
    { name: "Fear & Greed", value: fearVal, fmt: (v) => v.toFixed(0), sig: signal.fear },
    { name: "미국 실업률", value: unrate, fmt: (v) => `${v.toFixed(1)}%`, sig: signal.unrate },
    { name: "M2 YoY", value: m2Yoy, fmt: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`, sig: signal.m2 },
  ];

  const valid = indicators.map((i) => i.sig).filter((s) => s !== null);
  const score = valid.reduce((sum, s) => sum + s, 0);
  const label = score >= 2 ? "RISK ON" : score <= -2 ? "RISK OFF" : "NEUTRAL";
  const color = score >= 2 ? "#10b981" : score <= -2 ? "#ef4444" : "#f59e0b";
  const sigLabel = (s) => s === 1 ? "Risk On" : s === -1 ? "Risk Off" : s === 0 ? "Neutral" : "No Data";

  const rows = indicators.map((ind) => `
    <tr>
      <td style="font-weight:600; color:var(--text-heading);">${html(ind.name)}</td>
      <td style="font-weight:700; color:#d1d5db; text-align:right;">${ind.value !== null ? html(ind.fmt(ind.value)) : "-"}</td>
      <td style="text-align:center; color:${ind.sig === 1 ? "#10b981" : ind.sig === -1 ? "#ef4444" : "#f59e0b"}; font-weight:700;">${sigLabel(ind.sig)}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <div style="background:${color}1f; border:1px solid ${color}66; border-radius:12px; padding:24px; text-align:center; margin-bottom:24px;">
      <div style="font-size:0.85rem; color:${color}; font-weight:700; letter-spacing:2px; margin-bottom:8px;">종합 매크로 신호</div>
      <div style="font-size:1.8rem; font-weight:800; color:${color};">${label}</div>
      <div style="font-size:0.88rem; color:var(--text-sub); margin-top:8px;">
        긍정 ${valid.filter((s) => s === 1).length}개 · 중립 ${valid.filter((s) => s === 0).length}개 · 부정 ${valid.filter((s) => s === -1).length}개
      </div>
    </div>
    <div class="table-responsive">
      <table class="alerts-table">
        <thead><tr><th style="width:220px;">지표</th><th style="text-align:right;">현재값</th><th style="text-align:center;">신호</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p style="color:var(--text-sub); font-size:0.8rem; margin-top:16px; text-align:right;">
      * 마지막 수집 데이터 기준 참고용 지표이며 투자 권유가 아닙니다.
    </p>
  `;
}
window.renderScorecard = renderScorecard;

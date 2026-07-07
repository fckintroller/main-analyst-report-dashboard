document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  setTimeout(() => {
    if (!window.QUANT_DATA) return;
    renderStatusBar();
    renderHomeDashboard();
    renderMacroChart();
    renderMoneyFlowChart();
    renderBreadthCharts();
    renderStockAttractiveness();
    renderStockActionCandidatesTab();
    renderSectorMap();
    renderRegimeCard();
    renderScorecard();
    renderRegressionPanel();
    renderFactorMaster();
    renderDataQualityDashboard();
    renderFactorValidation();
    renderPracticalBacktest();
    renderPositionSizing();
    renderPaperTrading();
    renderKiwoomDecisionPanel();
    renderTradeImportExportPanel();
    renderNewsSentiment();
    renderDecisionOSV2();
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
      window.scrollTo({ top: 0, behavior: "smooth" });
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
        renderBreadthCharts();
      }
      if (targetId === "tab-home") {
        renderHomeDashboard();
      }
      if (targetId === "tab-bubble") {
        setTimeout(() => {
          if (window.bubbleCharts?.length) {
            window.bubbleCharts.forEach((c) => { try { c.resize(); } catch (_) {} });
          } else if (typeof initBubbleCharts === "function") {
            initBubbleCharts();
          }
        }, 50);
      }
      setTimeout(renderDecisionOSV2, 60);
    });
  });
}

// 탭을 이름으로 전환하는 헬퍼 (홈 대시보드 버튼에서 사용)
function switchTab(name) {
  const btn = document.getElementById("btn-tab-" + name);
  if (btn) btn.click();
}
window.switchTab = switchTab;

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
  window.scrollTo({ top: 0, behavior: "smooth" });

  // 금리/채권 탭: hidden 상태로 그려진 차트들 크기 재계산
  if (targetId === "macro-leading") { setTimeout(renderLeadingIndicatorCharts, 50); }
  if (targetId === "macro-industry") { setTimeout(renderIndustryCharts, 50); }
  if (targetId === "macro-sector-momentum") { setTimeout(renderSectorMomentumCharts, 50); }
  if (targetId === "macro-scorecard") { setTimeout(() => { renderRegimeCard(); renderScorecard(); }, 50); }
  if (targetId === "macro-regression") { setTimeout(renderRegressionPanel, 50); }
  if (targetId === "macro-trade-import-export") { setTimeout(renderTradeImportExportPanel, 50); }
  if (targetId === "quant-factor-master") { setTimeout(renderFactorMaster, 50); }
  if (targetId === "quant-data-quality") { setTimeout(renderDataQualityDashboard, 50); }
  if (targetId === "quant-factor-validation") { setTimeout(renderFactorValidation, 50); }
  if (targetId === "quant-practical-backtest") { setTimeout(renderPracticalBacktest, 50); }
  if (targetId === "analysis-market-attractiveness") { setTimeout(renderStockAttractiveness, 50); }
  if (targetId === "analysis-action-candidates") { setTimeout(renderStockActionCandidatesTab, 50); }
  if (targetId === "analysis-position-sizing") { setTimeout(renderPositionSizing, 50); }
  if (targetId === "analysis-kiwoom-decision") { setTimeout(renderKiwoomDecisionPanel, 50); }
  if (targetId === "analysis-paper-trading") { setTimeout(renderPaperTrading, 50); }
  if (targetId === "news-sentiment") { setTimeout(renderNewsSentiment, 50); }
  if (targetId === "news-headlines") { setTimeout(renderNewsHeadlinesFeed, 50); }
  if (targetId === "macro-rates") {
    setTimeout(() => {
      if (window.bubbleCharts?.length) {
        window.bubbleCharts.forEach((c) => { try { c.resize(); } catch (_) {} });
      } else if (typeof initBubbleCharts === "function") {
        initBubbleCharts();
      }
    }, 50);
  }
}
window.switchSubTab = switchSubTab;

let chartInstances = [];
let tradeChartInstances = [];

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
  canvasContainer.style.height = "280px";

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
      if (raw === "" || raw === null || raw === undefined) continue;
      const value = Number(String(raw).replace(/,/g, ""));
      if (!Number.isNaN(value)) return value;
    }
  }
  return null;
}

function normalizeTimeSeries(arr, valCandidates, limit = 150) {
  if (!Array.isArray(arr) || arr.length === 0) return [];
  const dateKeys = ["date", "Date", "DATE"];
  const valKeys  = Array.isArray(valCandidates) ? valCandidates : [valCandidates];
  return arr.slice(-limit).map(row => {
    const date = dateKeys.reduce((v, k) => v || row[k], null);
    const val  = valKeys.reduce((v, k) => {
      if (v !== null && v !== undefined) return v;
      const n = Number(String(row[k] ?? "").replace(/,/g, ""));
      return isNaN(n) ? null : n;
    }, null);
    return { date: String(date || "").substring(0, 10), value: val };
  }).filter(r => r.date && r.value !== null && !isNaN(r.value));
}

function createNormalizedLineChart(containerId, title, arr, valKey, color, limit = 150) {
  const data = normalizeTimeSeries(arr, valKey, limit);
  if (data.length === 0) return;
  const ctx = createChartCanvas(containerId, title);
  if (!ctx) return;
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels:   data.map(r => r.date),
      datasets: [{ label: title, data: data.map(r => r.value),
                   borderColor: color, backgroundColor: color + "20",
                   borderWidth: 2, fill: true, tension: 0.1, pointRadius: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 5, color: "#6b7280" } },
        y: { ticks: { color: "#6b7280" } },
      },
    },
  });
  chartInstances.push(chart);
}

function numericValue(row, key) {
  return Number(String(row?.[key] ?? "").replace(/,/g, "")) || 0;
}

function moneyFlowValue(row, keys) {
  const candidates = Array.isArray(keys) ? keys : [keys];
  for (const key of candidates) {
    if (key in (row || {})) {
      const n = Number(String(row[key] ?? "").replace(/,/g, ""));
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}

function moneyFlowDate(row) {
  return row?.date || row?.date_raw || row?.["날짜_날짜"] || row?.["날짜"] || "";
}

function marketFundRows(limit = 120) {
  const rows = window.QUANT_DATA?.money_flow?.market_funds_trend;
  if (!Array.isArray(rows)) return [];
  return rows
    .map((r) => ({
      ...r,
      _date: moneyFlowDate(r),
      _customerDeposit: moneyFlowValue(r, ["customer_deposit", "고객예탁금_고객예탁금"]),
      _creditBalance: moneyFlowValue(r, ["credit_balance", "신용잔고_신용잔고"]),
    }))
    .filter((r) => r._date && (r._customerDeposit !== null || r._creditBalance !== null))
    .sort((a, b) => String(a._date).localeCompare(String(b._date)))
    .slice(-limit);
}

function renderMacroChart() {
  const macroData = window.QUANT_DATA?.macro;
  if (!macroData || !window.Chart) return;

  chartInstances.forEach((chart) => chart.destroy());
  chartInstances = [];

  ["macro-rates-charts-dynamic", "macro-commodity-charts", "macro-global-charts", "macro-index-charts",
   "macro-rates-kor-charts", "macro-index-futures-charts"].forEach((id) => {
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

  // ── 한국 금리 (ECOS)
  createLineChart("macro-rates-kor-charts", "한국 기준금리 (%)", macroData.KOR_BASE_RATE, "date", "value", "#10b981");
  createLineChart("macro-rates-kor-charts", "콜금리 1일 (%)", macroData.KOR_CALL_RATE, "date", "value", "#34d399");
  createLineChart("macro-rates-kor-charts", "CD금리 91일 (%)", macroData.KOR_CD91, "date", "value", "#6ee7b7");
  createLineChart("macro-rates-kor-charts", "국고채 3년 (%)", macroData.KOR_GOV3Y, "date", "value", "#f59e0b");
  createLineChart("macro-rates-kor-charts", "국고채 5년 (%)", macroData.KOR_GOV5Y, "date", "value", "#fbbf24");
  createLineChart("macro-rates-kor-charts", "국고채 10년 (%)", macroData.KOR_GOV10Y, "date", "value", "#fcd34d");
  createLineChart("macro-rates-kor-charts", "회사채 AA- (%)", macroData.KOR_CORP_AA, "date", "value", "#f97316");
  createLineChart("macro-rates-kor-charts", "회사채 BBB- 신용스프레드 (%p)", macroData.kor_corp_spread_bbb, "date", "value", "#ef4444");
  createLineChart("macro-rates-kor-charts", "한국 장단기 금리차 10Y-3Y (%p)", macroData.kor_yield_spread, "date", "value", "#8b5cf6");

  // ── 미국 금리
  createLineChart("macro-rates-charts-dynamic", "미국 10년물 국채 금리", macroData.DGS10 || macroData.TNX, macroData.DGS10 ? "DATE" : "Date", macroData.DGS10 ? "DGS10" : "Close", "#ef4444");
  createLineChart("macro-commodity-charts", "달러 인덱스", macroData.DXY, "Date", "Close", "#3b82f6");
  createLineChart("macro-commodity-charts", "WTI 원유", macroData.WTI, "Date", "Close", "#f59e0b");
  createLineChart("macro-commodity-charts", "금 가격", macroData.Gold, "Date", "Close", "#eab308");
  createLineChart("macro-global-charts", "미국 M2 통화량", macroData.M2SL, "DATE", "M2SL", "#10b981");
  createLineChart("macro-global-charts", "연준 총자산", macroData.WALCL, "DATE", "WALCL", "#8b5cf6");

  // ── 선물 매매동향 & 고객예탁금
  const flowData = window.QUANT_DATA?.money_flow || {};
  const futuresEl = document.getElementById("macro-index-futures-charts");
  if (futuresEl) {
    // 선물 매매동향 (외국인 + 기관 선물 순매수)
    const ft = flowData.futures_trend;
    if (Array.isArray(ft) && ft.length) {
      const ctx = createChartCanvas("macro-index-futures-charts", "선물 매매동향 (외국인/기관, 계약수)");
      if (ctx) {
        const dateKey = Object.keys(ft[0])[0];
        const keys = Object.keys(ft[0]);
        // 날짜 오름차순 정렬 후 최근 20일 (인코딩 무관하게 인덱스로 key 접근)
        const sorted = [...ft].sort((a, b) => String(a[dateKey] || "").localeCompare(String(b[dateKey] || "")));
        const recent = sorted.slice(-20);
        const chart = new Chart(ctx, {
          type: "bar",
          data: {
            labels: recent.map(r => {
              const raw = String(r[dateKey] || "");
              return raw.length >= 8 ? raw.slice(4,6) + "/" + raw.slice(6,8) : raw.slice(0, 8);
            }),
            datasets: [
              { label: "외국인", data: recent.map(r => parseFloat(r[keys[1]]) || 0), backgroundColor: "#3b82f688", borderColor: "#3b82f6", borderWidth: 1 },
              { label: "기관", data: recent.map(r => parseFloat(r[keys[2]]) || 0), backgroundColor: "#10b98188", borderColor: "#10b981", borderWidth: 1 }
            ]
          },
          options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#d1d5db" } } },
            scales: { x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } }, y: { ticks: { color: "#6b7280" } } } }
        });
        chartInstances.push(chart);
      }
    }
    // 고객예탁금 & 신용잔고 (120일, 조원 단위 = 억원 ÷ 10,000)
    const mfRecent = marketFundRows(120);
    if (mfRecent.length) {
      const ctx2 = createChartCanvas("macro-index-futures-charts", "고객예탁금 & 신용잔고 추이 (단위: 조원)");
      if (ctx2) {
        const chart2 = new Chart(ctx2, {
          type: "line",
          data: {
            labels: mfRecent.map(r => String(r._date || "").slice(0, 10)),
            datasets: [
              { label: "고객예탁금(조원)", data: mfRecent.map(r => +((r._customerDeposit || 0) / 1e4).toFixed(1)), borderColor: "#f59e0b", backgroundColor: "#f59e0b20", borderWidth: 2, fill: true, tension: 0.3, pointRadius: 1 },
              { label: "신용잔고(조원)", data: mfRecent.map(r => +((r._creditBalance || 0) / 1e4).toFixed(1)), borderColor: "#ef4444", backgroundColor: "#ef444420", borderWidth: 2, fill: false, tension: 0.3, pointRadius: 1 }
            ]
          },
          options: { responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: "#d1d5db" } },
              tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}조원` } }
            },
            scales: { x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } }, y: { ticks: { color: "#6b7280" } } } }
        });
        chartInstances.push(chart2);
      }
    }
  }

  // ── 비철금속 현재가 테이블
  const nfEl = document.getElementById("macro-commodity-nonferrous-table");
  if (nfEl) {
    const nfData = macroData.stooq_nonferrous_metals_latest;
    if (Array.isArray(nfData) && nfData.length) {
      const rows = nfData.map(r => {
        const chg = String(r.change_pct || "");
        const isPos = chg.startsWith("+");
        const color = isPos ? "#10b981" : "#ef4444";
        return `<tr style="border-bottom:1px solid var(--card-border)">
          <td style="padding:8px 12px;font-weight:600">${r.metal || ""}</td>
          <td style="padding:8px 12px;text-align:right">${r.last || ""}</td>
          <td style="padding:8px 12px;text-align:right;color:${color};font-weight:600">${chg}</td>
        </tr>`;
      }).join("");
      nfEl.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:0.9rem">
        <thead><tr style="background:var(--th-bg)">
          <th style="padding:8px 12px;text-align:left;color:#10b981">금속</th>
          <th style="padding:8px 12px;text-align:right;color:#10b981">현재가</th>
          <th style="padding:8px 12px;text-align:right;color:#10b981">등락률</th>
        </tr></thead><tbody>${rows}</tbody>
      </table>`;
    }
  }
}

function renderMoneyFlowChart() {
  const flowData = window.QUANT_DATA?.money_flow;
  if (!flowData || !window.Chart) return;

  const createBarChart = (containerId, title, dataArray, dateKey, series, limit = 120, type = "bar") => {
    if (!Array.isArray(dataArray) || dataArray.length === 0) return;
    const ctx = createChartCanvas(containerId, title);
    if (!ctx) return;
    const recent = dataArray.slice(-limit);
    const isLine = type === "line";

    const chart = new Chart(ctx, {
      type,
      data: {
        labels: recent.map((d) => d[dateKey]),
        datasets: series.map((s) => ({
          label: s.label,
          data: recent.map((d) => numericValue(d, s.key)),
          backgroundColor: isLine ? s.color + "20" : s.color,
          borderColor: s.color,
          borderWidth: isLine ? 2 : 1,
          fill: false,
          tension: 0.3,
          pointRadius: isLine ? 2 : undefined,
          pointHoverRadius: isLine ? 4 : undefined,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: isLine ? { mode: "index", intersect: false } : {},
        plugins: { legend: { labels: { color: "#d1d5db" } } },
        scales: {
          x: { ticks: { maxTicksLimit: 10, color: "#6b7280" } },
          y: {
            ticks: { color: "#6b7280" },
            grid: isLine ? { color: "#374151" } : {},
          },
        },
      },
    });
    chartInstances.push(chart);
  };

  const investorSeries = [
    { label: "개인", key: "개인", color: "#ef4444" },
    { label: "외국인", key: "외국인합계", color: "#3b82f6" },
    { label: "기관", key: "기관합계", color: "#10b981" },
  ];
  createBarChart("macro-index-charts", "KOSPI 투자자별 순매수 (1개월, 단위: 억원)", flowData.market_trading_value_kospi_20y, "date", investorSeries, 20, "line");
  createBarChart("macro-index-charts", "KOSDAQ 투자자별 순매수 (1개월, 단위: 억원)", flowData.market_trading_value_kosdaq_20y, "date", investorSeries, 20, "line");

  const programSeries = [
    { label: "차익", key: "차익거래_순매수", color: "#8b5cf6" },
    { label: "비차익", key: "비차익거래_순매수", color: "#06b6d4" },
  ];
  createBarChart("macro-index-charts", "KOSPI 프로그램 순매수", [...(flowData.program_kospi || [])].reverse(), "시간_시간", programSeries, 80, "line");
  createBarChart("macro-index-charts", "KOSDAQ 프로그램 순매수", [...(flowData.program_kosdaq || [])].reverse(), "시간_시간", programSeries, 80, "line");
}

// ─────────────────────────────────────────────────────────────────────────────
// 시장 내부 지표 (Breadth): TRIN / ADL  →  주가 지표 탭
// ─────────────────────────────────────────────────────────────────────────────
function renderBreadthCharts() {
  const sentiment = window.QUANT_DATA?.sentiment;
  if (!sentiment || !window.Chart) return;

  const containerId = "macro-index-charts";

  // 섹션 헤더
  const container = document.getElementById(containerId);
  if (!container) return;
  const header = document.createElement("h3");
  header.style.cssText = "color: var(--primary); margin: 30px 0 15px; grid-column: 1 / -1; font-size: 1rem;";
  header.innerHTML = '<i class="fa-solid fa-wave-square"></i> 시장 내부 지표 (Breadth Indicators)';
  container.appendChild(header);

  // 데이터가 없으면 플레이스홀더 표시
  const hasData = [sentiment.trin, sentiment.us_adl, sentiment.kr_trin, sentiment.kr_adl]
    .some((d) => Array.isArray(d) && d.length > 0);
  if (!hasData) {
    const ph = document.createElement("div");
    ph.style.cssText = "grid-column:1/-1; padding:24px; color:var(--text-secondary); text-align:center; font-size:0.9rem; border:1px dashed var(--border); border-radius:8px;";
    ph.innerHTML = '<i class="fa-solid fa-circle-info" style="margin-right:6px;"></i>데이터 없음 — 파이프라인 실행 후 표시됩니다 (<code>python scripts/pipeline.py</code>)';
    container.appendChild(ph);
    return;
  }

  // 라인 차트 공통 생성기
  const addLineChart = (title, dataArray, dateKey, series, limit = 120) => {
    if (!Array.isArray(dataArray) || dataArray.length === 0) return;
    const ctx = createChartCanvas(containerId, title);
    if (!ctx) return;
    const recent = dataArray.slice(-limit);

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: recent.map((d) => String(d[dateKey] ?? "").substring(0, 10)),
        datasets: series.map((s) => ({
          label: s.label,
          data: recent.map((d) => {
            const v = parseFloat(String(d[s.key] ?? "").replace(/,/g, ""));
            return isFinite(v) ? v : null;
          }),
          borderColor: s.color,
          backgroundColor: s.color + "20",
          borderWidth: 1.5,
          fill: s.fill ?? false,
          tension: 0.1,
          pointRadius: 0,
          yAxisID: s.yAxis ?? "y",
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#d1d5db", font: { size: 11 } } },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(3) ?? "—"}` } },
        },
        scales: {
          x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } },
          y: { ticks: { color: "#6b7280" }, title: { display: !!series[0].yLabel, text: series[0].yLabel ?? "", color: "#9ca3af", font: { size: 10 } } },
        },
      },
    });
    chartInstances.push(chart);
  };

  // 기준선(1.0) 추가 레이어를 위한 TRIN 전용 차트
  const addTrinChart = (title, dataArray, limit = 120) => {
    if (!Array.isArray(dataArray) || dataArray.length === 0) return;
    const ctx = createChartCanvas(containerId, title);
    if (!ctx) return;
    const recent = dataArray.slice(-limit);
    const labels = recent.map((d) => String(d.date ?? "").substring(0, 10));
    const values = recent.map((d) => {
      const v = parseFloat(String(d.trin ?? "").replace(/,/g, ""));
      return isFinite(v) ? v : null;
    });

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "TRIN",
            data: values,
            borderColor: "#f59e0b",
            backgroundColor: "#f59e0b15",
            borderWidth: 1.5,
            fill: true,
            tension: 0.1,
            pointRadius: 0,
          },
          {
            label: "기준선 (1.0)",
            data: labels.map(() => 1.0),
            borderColor: "#ef444480",
            borderWidth: 1,
            borderDash: [4, 4],
            fill: false,
            pointRadius: 0,
            tension: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#d1d5db", font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.datasetIndex === 1) return null;
                const v = ctx.parsed.y;
                const signal = v < 0.85 ? "📈 Bullish" : v > 1.25 ? "📉 Bearish" : "➡️ Neutral";
                return ` TRIN: ${v?.toFixed(3)} (${signal})`;
              },
            },
          },
        },
        scales: {
          x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } },
          y: { ticks: { color: "#6b7280" }, title: { display: true, text: "< 1.0 강세  /  > 1.0 약세", color: "#9ca3af", font: { size: 10 } } },
        },
      },
    });
    chartInstances.push(chart);
  };

  // ── 미국 TRIN
  addTrinChart("미국 TRIN (NYSE Arms Index, 최근 120일)", sentiment.trin, 120);

  // ── 미국 ADL (Cumulative A/D Line)
  addLineChart(
    "미국 ADL (NYSE Cumulative Advance-Decline Line)",
    sentiment.us_adl,
    "date",
    [{ label: "ADL", key: "Close", color: "#3b82f6", fill: true, yLabel: "누적 A/D" }],
    200
  );

  // ── 한국 TRIN
  addTrinChart("한국 TRIN (KOSPI, 최근 120일)", sentiment.kr_trin, 120);

  // ── 헬퍼: EMA / MA 계산
  const calcEMA = (data, period) => {
    const k = 2 / (period + 1);
    let ema = null;
    return data.map((v) => {
      if (v === null || !isFinite(v)) return null;
      ema = ema === null ? v : v * k + ema * (1 - k);
      return ema;
    });
  };
  const calcMA = (data, period) => data.map((_, i) => {
    if (i < period - 1) return null;
    const slice = data.slice(i - period + 1, i + 1).filter((v) => v !== null && isFinite(v));
    return slice.length === period ? slice.reduce((a, b) => a + b, 0) / period : null;
  });

  // ── 한국 ADL + MA20
  if (Array.isArray(sentiment.kr_adl) && sentiment.kr_adl.length > 0) {
    const adlData  = sentiment.kr_adl.slice(-200);
    const adlVals  = adlData.map((d) => parseFloat(d.adl_cumulative) || 0);
    const ma20     = calcMA(adlVals, 20);
    const labels   = adlData.map((d) => String(d.date ?? "").substring(0, 10));
    const ctx = createChartCanvas(containerId, "한국 ADL (KOSPI Advance-Decline Line) + MA20");
    if (ctx) {
      chartInstances.push(new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [
            { label: "ADL 누적", data: adlVals, borderColor: "#10b981", backgroundColor: "#10b98120", borderWidth: 1.5, fill: true, tension: 0.1, pointRadius: 0 },
            { label: "MA20",    data: ma20,    borderColor: "#fbbf24", backgroundColor: "transparent", borderWidth: 1.5, borderDash: [4, 3], fill: false, tension: 0.1, pointRadius: 0 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { labels: { color: "#d1d5db", font: { size: 11 } } } },
          scales: {
            x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } },
            y: { ticks: { color: "#6b7280" }, title: { display: true, text: "누적합 / MA20 이탈 = 약세", color: "#9ca3af", font: { size: 10 } } },
          },
        },
      }));
    }
  }

  // ── McClellan Oscillator (EMA19 - EMA39 of A-D net)
  if (Array.isArray(sentiment.kr_adl) && sentiment.kr_adl.length > 0) {
    const full    = sentiment.kr_adl;
    const netAll  = full.map((d) => (parseFloat(d.advancing) || 0) - (parseFloat(d.declining) || 0));
    const ema19   = calcEMA(netAll, 19);
    const ema39   = calcEMA(netAll, 39);
    const mco     = ema19.map((v, i) => (v !== null && ema39[i] !== null) ? parseFloat((v - ema39[i]).toFixed(2)) : null);
    const recent  = mco.slice(-200);
    const labels  = full.slice(-200).map((d) => String(d.date ?? "").substring(0, 10));
    const ctx = createChartCanvas(containerId, "McClellan Oscillator (EMA19 - EMA39)");
    if (ctx) {
      chartInstances.push(new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [
            { label: "McClellan",  data: recent, borderColor: "#a78bfa", backgroundColor: "#a78bfa20", borderWidth: 1.5, fill: true, tension: 0.2, pointRadius: 0 },
            { label: "+100 (과매수)", data: labels.map(() =>  100), borderColor: "#ef444460", borderWidth: 1, borderDash: [4, 4], fill: false, pointRadius: 0, tension: 0 },
            { label: "0",          data: labels.map(() =>    0), borderColor: "#6b728060", borderWidth: 1, borderDash: [2, 2], fill: false, pointRadius: 0, tension: 0 },
            { label: "-100 (과매도)", data: labels.map(() => -100), borderColor: "#10b98160", borderWidth: 1, borderDash: [4, 4], fill: false, pointRadius: 0, tension: 0 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { labels: { color: "#d1d5db", font: { size: 11 } } },
            tooltip: { callbacks: { label: (c) => c.datasetIndex === 0 ? ` McClellan: ${c.parsed.y?.toFixed(1)}` : null } },
          },
          scales: {
            x: { ticks: { maxTicksLimit: 6, color: "#6b7280" } },
            y: { ticks: { color: "#6b7280" }, title: { display: true, text: "+100 과매수 / -100 과매도", color: "#9ca3af", font: { size: 10 } } },
          },
        },
      }));
    }
  }

  // ── 한국 KOSPI 상승·하락 종목수
  addLineChart(
    "한국 KOSPI 상승·하락 종목수",
    sentiment.kr_adl,
    "date",
    [
      { label: "상승", key: "advancing", color: "#10b981" },
      { label: "하락", key: "declining", color: "#ef4444" },
    ],
    120
  );
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
    thead.innerHTML = `<th>종목명 (코드)</th><th>최근 가치지표</th><th>최근 연도 영업이익<br><small style="font-weight:400; color:var(--text-sub);">(억원)</small></th><th>올해 예상<br><small style="font-weight:400; color:var(--text-sub);">(억원 / 전년비)</small></th><th>내년 예상<br><small style="font-weight:400; color:var(--text-sub);">(억원 / 올해비)</small></th>`;
  }

  const formatNum = (value) => {
    const num = Number(String(value ?? "").replace(/,/g, ""));
    return Number.isFinite(num) ? num.toLocaleString("ko-KR") : "-";
  };

  const calcPct = (curr, prev) => {
    const c = Number(curr), p = Number(prev);
    if (!Number.isFinite(c) || !Number.isFinite(p) || p === 0) return null;
    return ((c - p) / Math.abs(p)) * 100;
  };

  const fmtPct = (pct) => {
    if (pct === null) return "";
    const sign = pct >= 0 ? "+" : "";
    const color = pct >= 0 ? "#10b981" : "#ef4444";
    return `<div style="font-size:0.75rem; color:${color}; font-weight:700; margin-top:2px;">${sign}${pct.toFixed(1)}%</div>`;
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
      const lastOp = raw[lastYearCol][opRow];
      const thisOp = raw[thisYearCol][opRow];
      const nextOp = raw[nextYearCol][opRow];
      const thisPct = calcPct(thisOp, lastOp);
      const nextPct = calcPct(nextOp, thisOp);

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
          <td>${formatNum(lastOp)}</td>
          <td style="font-weight:700; color:#10b981;">${formatNum(thisOp)}${fmtPct(thisPct)}</td>
          <td style="font-weight:700; color:#3b82f6;">${formatNum(nextOp)}${fmtPct(nextPct)}</td>
        </tr>
      `);
    } catch (_) {
      // Skip malformed source rows.
    }
  });

  tbody.innerHTML = rows.join("") || '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-sub);">실적 컨센서스 데이터가 없습니다.</td></tr>';
}


const STOCK_SCENARIOS = {
  market_attractiveness_score: {
    label: "종합 매력도",
    horizon: "공통 스크리닝",
    desc: "기본 5팩터·가치퀄리티·모멘텀수급·저평가반등·숏커버 보조 점수의 평균입니다. 한 종목을 처음 볼 때 가장 보편적인 1차 정렬 기준으로 사용합니다.",
    factors: ["가치", "모멘텀", "시총", "유동성", "ROE", "수급", "공매도"]
  },
  scenario_a_momentum: {
    label: "A 단기 모멘텀",
    horizon: "1~3개월 공격형",
    desc: "가격·거래량 모멘텀 35%, 수급 30%, 유동성 20%, 실적 모멘텀 15%를 결합합니다. 빠르게 움직이는 종목을 찾되 거래대금과 수급 확인을 같이 하는 단기/스윙 후보군입니다.",
    factors: ["가격·거래량", "외국인·기관 수급", "유동성", "실적 모멘텀"]
  },
  scenario_b_value_quality: {
    label: "B 가치+퀄리티",
    horizon: "3~12개월 중기",
    desc: "기존 밸류, 섹터상대 가치품질, ROE, Piotroski, ㊳ Balance Sheet Quality(부채/순부채/이자보상/유동비율/자본잠식), ㊴ Cash Flow Quality(FCF margin/yield·accrual·현금전환), ㊵ Earnings Stability(매출·마진·적자·ROE 안정성), 실적 모멘텀, 선행 밸류를 결합합니다. PER/PBR이 싸기만 한 value trap보다 재무상태표·현금흐름·이익 안정성이 동반된 저평가 후보를 우선합니다.",
    factors: ["밸류", "섹터상대 가치", "ROE", "㊳ BS품질", "㊴ CF품질", "㊵ 이익안정", "실적"]
  },

  scenario_c_reversal: {
    label: "C 저평가 반등",
    horizon: "1~6개월 역발상",
    desc: "평균회귀 30%, 밸류 20%, 섹터상대 가치 20%, 수급 20%, 숏커버 압력 10%를 결합합니다. 낙폭 이후 수급이 돌아서는 반등 후보를 찾는 보조 시나리오입니다.",
    factors: ["과매도", "저평가", "섹터대비 할인", "수급개선", "숏커버"]
  },
  scenario_d_large_stable: {
    label: "D 대형 안정",
    horizon: "방어형/코어",
    desc: "시총 규모 25%, 유동성 20%, ROE 20%, 밸류 15%, 수급 10%, 재무건전성 10%를 결합합니다. 급등주보다 실제 매매 가능성과 방어력을 우선하는 코어 후보군입니다.",
    factors: ["대형주", "거래 유동성", "ROE", "밸류", "수급", "재무건전성"]
  },
  score_base_5factor: {
    label: "기본 5팩터",
    horizon: "1~6개월",
    desc: "valuation_score, momentum_score, size_percentile_cross, liquidity_score, roe_score를 같은 비중으로 결합합니다. 표본 수가 가장 안정적인 기본 모델입니다.",
    factors: ["밸류", "가격 모멘텀", "시가총액", "유동성", "ROE"]
  },
  score_value_quality: {
    label: "가치+퀄리티",
    horizon: "6개월~1년",
    desc: "싸면서 ROE/재무점수/실적모멘텀이 괜찮은 종목을 찾습니다. 단순 저PER·저PBR 함정 가치주를 줄이는 목적입니다.",
    factors: ["밸류", "ROE", "Piotroski", "실적 모멘텀", "Forward 밸류"]
  },
  score_momentum_flow: {
    label: "모멘텀+수급",
    horizon: "1~6개월",
    desc: "가격 모멘텀, 외국인/기관 수급, 거래대금 유동성을 결합합니다. 앞선 회귀 진단에서 KOSPI200 3개월 horizon에서 상대적으로 유효했습니다.",
    factors: ["가격 모멘텀", "수급", "거래대금"]
  },
  score_reversal_value_flow: {
    label: "저평가 반등",
    horizon: "1~6개월",
    desc: "저평가, 과매도/평균회귀, 수급 개선을 함께 봅니다. 급락 후 반등 후보를 찾는 보조 시나리오입니다.",
    factors: ["저평가", "과매도", "수급 개선"]
  },
  score_short_squeeze_addon: {
    label: "숏커버 보조",
    horizon: "1~3개월",
    desc: "모멘텀·수급에 공매도 압력/숏스퀴즈 플래그를 더합니다. 단독 모델보다 이벤트성 보조 필터로 해석합니다.",
    factors: ["모멘텀", "수급", "공매도"]
  },
  horizon_6m: {
    label: "6개월 관점",
    horizon: "중기",
    desc: "현재 데이터 길이상 6개월은 충분히 분석 가능합니다. 모멘텀+ROE+밸류+유동성 조합을 우선 봅니다.",
    factors: ["기본 5팩터", "모멘텀", "ROE", "밸류"]
  },
  horizon_1y: {
    label: "1년 관점",
    horizon: "중장기",
    desc: "1년은 가능하지만 최근 구간 검증력이 줄어듭니다. 가치+퀄리티, ROE, PBR 리레이팅을 중심으로 봅니다.",
    factors: ["가치+퀄리티", "ROE", "PBR 리레이팅"]
  },
  horizon_2y: {
    label: "2년 관점",
    horizon: "참고용",
    desc: "2년은 표본이 작아 회귀보다 분위별 성과/상위하위 비교가 적합합니다. 장기 방향성 참고용으로만 사용합니다.",
    factors: ["저PBR", "ROE", "장기 모멘텀"]
  },
  regime_adj_score: {
    label: "레짐 조정 점수",
    horizon: "현재 레짐 최적화",
    desc: "Fama-MacBeth 회귀에서 현재 레짐(risk_on/risk_off/other)에 유의한 팩터를 IC 크기에 비례해 가중한 종목 점수입니다. 시장 국면 변화 시 가장 민감하게 반응하는 실험적 시나리오입니다.",
    factors: ["레짐 조건부 팩터 가중", "IC 비례 가중치", "현재 시점 최적화"]
  },
  pullback_rebound_score: {
    label: "눌림목 반등",
    horizon: "단타 1~5일",
    desc: "중기 모멘텀 30% + 평균회귀(과매도) 30% + 수급 20% + 뉴스감성 10% + 분봉 체결강도 10%. 중기 방향이 살아있는데 단기 눌린 종목을 잡는 단타/스윙 진입 시나리오입니다.",
    factors: ["중기 모멘텀", "단기 과매도", "외국인·기관 수급", "뉴스 감성", "분봉 체결강도"]
  },
  breakout_continuation_score: {
    label: "신고가 돌파",
    horizon: "단타·스윙 1~10일",
    desc: "모멘텀 35% + 수급 25% + 유동성 15% + 분봉 체결강도 15% + 뉴스감성 10%. 52주 고가 돌파 직후 거래량·수급이 받쳐주는 돌파 추세 추종 시나리오입니다.",
    factors: ["가격 모멘텀", "외국인·기관 수급", "거래 유동성", "분봉 체결강도", "뉴스 감성"]
  },
  short_squeeze_candidate_score: {
    label: "쇼트스퀴즈",
    horizon: "단타 이벤트성",
    desc: "공매도 잔고 압력 35% + 모멘텀 25% + 뉴스감성 15% + 숏스퀴즈 플래그 15% + 분봉 체결강도 10%. 공매도 잔고가 높은 상황에서 주가 강세+거래량 급증이 겹칠 때 스퀴즈 발생 후보를 포착합니다.",
    factors: ["공매도 잔고 압력", "가격 모멘텀", "뉴스 감성", "숏스퀴즈 플래그", "분봉 체결강도"]
  },
  turnaround_recovery_score: {
    label: "실적 턴어라운드",
    horizon: "스윙 1~3개월",
    desc: "실적 모멘텀 30% + 목표주가 상향 25% + 밸류에이션 20% + 내부자 신호 15% + 주주환원 이벤트 10%. 영업이익 흑자전환·EPS 컨센서스 상향이 시작되는 초기 단계 턴어라운드 스윙 시나리오입니다.",
    factors: ["실적 모멘텀", "목표주가 상향", "저평가 밸류", "내부자 순매수/자사주", "주주환원 공시"]
  }
};
const STOCK_BACKTEST_SUMMARY = [{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":20,"horizon_m":1,"periods":12,"avg_forward_return":0.076694,"avg_benchmark_return":0.044439,"avg_excess_return":0.032255,"hit_rate_vs_benchmark":0.583333,"max_drawdown_chain":-0.053629},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":20,"horizon_m":1,"periods":35,"avg_forward_return":0.046846,"avg_benchmark_return":0.024174,"avg_excess_return":0.022672,"hit_rate_vs_benchmark":0.485714,"max_drawdown_chain":-0.173072},{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":30,"horizon_m":1,"periods":12,"avg_forward_return":0.060948,"avg_benchmark_return":0.044439,"avg_excess_return":0.016508,"hit_rate_vs_benchmark":0.666667,"max_drawdown_chain":-0.105099},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":30,"horizon_m":1,"periods":35,"avg_forward_return":0.038326,"avg_benchmark_return":0.024174,"avg_excess_return":0.014152,"hit_rate_vs_benchmark":0.514286,"max_drawdown_chain":-0.16701},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":20,"horizon_m":1,"periods":12,"avg_forward_return":0.04992,"avg_benchmark_return":0.044439,"avg_excess_return":0.005481,"hit_rate_vs_benchmark":0.583333,"max_drawdown_chain":-0.109645},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":20,"horizon_m":1,"periods":35,"avg_forward_return":0.02893,"avg_benchmark_return":0.024174,"avg_excess_return":0.004756,"hit_rate_vs_benchmark":0.4,"max_drawdown_chain":-0.199582},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":20,"horizon_m":1,"periods":33,"avg_forward_return":0.02921,"avg_benchmark_return":0.027027,"avg_excess_return":0.002183,"hit_rate_vs_benchmark":0.454545,"max_drawdown_chain":-0.171149},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":30,"horizon_m":1,"periods":35,"avg_forward_return":0.024763,"avg_benchmark_return":0.024174,"avg_excess_return":0.000589,"hit_rate_vs_benchmark":0.428571,"max_drawdown_chain":-0.188473},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":30,"horizon_m":1,"periods":33,"avg_forward_return":0.027248,"avg_benchmark_return":0.027027,"avg_excess_return":0.000221,"hit_rate_vs_benchmark":0.484848,"max_drawdown_chain":-0.16335},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":30,"horizon_m":1,"periods":12,"avg_forward_return":0.038316,"avg_benchmark_return":0.044439,"avg_excess_return":-0.006123,"hit_rate_vs_benchmark":0.5,"max_drawdown_chain":-0.125426},{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":20,"horizon_m":3,"periods":10,"avg_forward_return":0.223871,"avg_benchmark_return":0.152107,"avg_excess_return":0.071764,"hit_rate_vs_benchmark":0.7,"max_drawdown_chain":0.0},{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":30,"horizon_m":3,"periods":10,"avg_forward_return":0.206249,"avg_benchmark_return":0.152107,"avg_excess_return":0.054142,"hit_rate_vs_benchmark":0.7,"max_drawdown_chain":0.0},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":20,"horizon_m":3,"periods":33,"avg_forward_return":0.133166,"avg_benchmark_return":0.079048,"avg_excess_return":0.054118,"hit_rate_vs_benchmark":0.666667,"max_drawdown_chain":-0.184317},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":30,"horizon_m":3,"periods":33,"avg_forward_return":0.119177,"avg_benchmark_return":0.079048,"avg_excess_return":0.040129,"hit_rate_vs_benchmark":0.636364,"max_drawdown_chain":-0.214582},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":30,"horizon_m":3,"periods":33,"avg_forward_return":0.09231,"avg_benchmark_return":0.079048,"avg_excess_return":0.013262,"hit_rate_vs_benchmark":0.454545,"max_drawdown_chain":-0.347494},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":20,"horizon_m":3,"periods":33,"avg_forward_return":0.090575,"avg_benchmark_return":0.079048,"avg_excess_return":0.011527,"hit_rate_vs_benchmark":0.454545,"max_drawdown_chain":-0.330506},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":30,"horizon_m":3,"periods":31,"avg_forward_return":0.097089,"avg_benchmark_return":0.088703,"avg_excess_return":0.008386,"hit_rate_vs_benchmark":0.483871,"max_drawdown_chain":-0.288919},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":20,"horizon_m":3,"periods":31,"avg_forward_return":0.095503,"avg_benchmark_return":0.088703,"avg_excess_return":0.0068,"hit_rate_vs_benchmark":0.516129,"max_drawdown_chain":-0.289683},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":20,"horizon_m":3,"periods":10,"avg_forward_return":0.153806,"avg_benchmark_return":0.152107,"avg_excess_return":0.001699,"hit_rate_vs_benchmark":0.6,"max_drawdown_chain":0.0},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":30,"horizon_m":3,"periods":10,"avg_forward_return":0.131828,"avg_benchmark_return":0.152107,"avg_excess_return":-0.020279,"hit_rate_vs_benchmark":0.5,"max_drawdown_chain":0.0},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":20,"horizon_m":6,"periods":30,"avg_forward_return":0.264517,"avg_benchmark_return":0.177009,"avg_excess_return":0.087508,"hit_rate_vs_benchmark":0.666667,"max_drawdown_chain":-0.192694},{"scoreKey":"score_base_5factor","scenario":"base_5factor","label":"기본 5팩터","topn":30,"horizon_m":6,"periods":30,"avg_forward_return":0.250908,"avg_benchmark_return":0.177009,"avg_excess_return":0.073899,"hit_rate_vs_benchmark":0.7,"max_drawdown_chain":-0.202618},{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":20,"horizon_m":6,"periods":7,"avg_forward_return":0.419391,"avg_benchmark_return":0.360002,"avg_excess_return":0.059389,"hit_rate_vs_benchmark":0.714286,"max_drawdown_chain":0.0},{"scoreKey":"score_momentum_flow","scenario":"momentum_flow","label":"모멘텀+수급","topn":30,"horizon_m":6,"periods":7,"avg_forward_return":0.393795,"avg_benchmark_return":0.360002,"avg_excess_return":0.033793,"hit_rate_vs_benchmark":0.571429,"max_drawdown_chain":0.0},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":20,"horizon_m":6,"periods":30,"avg_forward_return":0.199176,"avg_benchmark_return":0.177009,"avg_excess_return":0.022167,"hit_rate_vs_benchmark":0.466667,"max_drawdown_chain":-0.442576},{"scoreKey":"market_attractiveness_score","scenario":"composite_attractiveness","label":"종합 매력도","topn":30,"horizon_m":6,"periods":30,"avg_forward_return":0.199068,"avg_benchmark_return":0.177009,"avg_excess_return":0.022059,"hit_rate_vs_benchmark":0.533333,"max_drawdown_chain":-0.368338},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":30,"horizon_m":6,"periods":28,"avg_forward_return":0.191079,"avg_benchmark_return":0.189451,"avg_excess_return":0.001629,"hit_rate_vs_benchmark":0.285714,"max_drawdown_chain":-0.416693},{"scoreKey":"score_value_quality","scenario":"value_quality","label":"가치+퀄리티","topn":20,"horizon_m":6,"periods":28,"avg_forward_return":0.188207,"avg_benchmark_return":0.189451,"avg_excess_return":-0.001244,"hit_rate_vs_benchmark":0.357143,"max_drawdown_chain":-0.475373},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":20,"horizon_m":6,"periods":7,"avg_forward_return":0.311828,"avg_benchmark_return":0.360002,"avg_excess_return":-0.048174,"hit_rate_vs_benchmark":0.428571,"max_drawdown_chain":0.0},{"scoreKey":"score_reversal_value_flow","scenario":"reversal_value_flow","label":"저평가 반등","topn":30,"horizon_m":6,"periods":7,"avg_forward_return":0.307367,"avg_benchmark_return":0.360002,"avg_excess_return":-0.052634,"hit_rate_vs_benchmark":0.428571,"max_drawdown_chain":0.0}];

window.activeStockQuickFilters = window.activeStockQuickFilters || new Set();
window.activeStockScenario = window.activeStockScenario || "market_attractiveness_score";

function stockNum(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

function fmtCompact(value, unit = "") {
  const n = stockNum(value);
  if (n === null) return "-";
  if (Math.abs(n) >= 1_0000_0000_0000) return `${(n / 1_0000_0000_0000).toFixed(1)}조${unit}`;
  if (Math.abs(n) >= 1_0000_0000) return `${(n / 1_0000_0000).toFixed(1)}억${unit}`;
  return `${Math.round(n).toLocaleString("ko-KR")}${unit}`;
}

function fmtNum(value, digits = 1) {
  const n = stockNum(value);
  if (n === null) return "-";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtPctValue(value, digits = 1) {
  const n = stockNum(value);
  if (n === null) return "";
  const color = n >= 0 ? "#10b981" : "#ef4444";
  const sign = n >= 0 ? "+" : "";
  return `<div style="font-size:0.75rem; color:${color}; font-weight:700; margin-top:2px;">${sign}${n.toFixed(digits)}%</div>`;
}

function scenarioScore(row) {
  const key = window.activeStockScenario || "market_attractiveness_score";
  if (key.startsWith("horizon_")) return row.market_attractiveness_score;
  return row[key] ?? row.market_attractiveness_score;
}

function fmtPctNumber(value, digits = 1, missing = "-") {
  const n = stockNum(value);
  if (n === null) return missing;
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtOpProfit(value) {
  const n = stockNum(value);
  if (n === null) return "-";
  return `${Math.round(n).toLocaleString("ko-KR")}억`;
}

function fmtBacktestPct(value, digits = 1) {
  const n = stockNum(value);
  if (n === null) return "-";
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(digits)}%`;
}

function selectedScenarioKey() {
  const key = window.activeStockScenario || "market_attractiveness_score";
  return key.startsWith("horizon_") ? "market_attractiveness_score" : key;
}

function buildScenarioRanks(rows, scoreKey) {
  const ranked = rows
    .map(row => ({ row, score: stockNum(row[scoreKey]) }))
    .filter(item => item.score !== null)
    .sort((a, b) => b.score - a.score);
  const ranks = new Map();
  const sectorRanks = new Map();
  ranked.forEach((item, idx) => ranks.set(item.row.ticker, idx + 1));
  const groups = new Map();
  ranked.forEach(item => {
    const sector = item.row.sector || "업종 미분류";
    if (!groups.has(sector)) groups.set(sector, []);
    groups.get(sector).push(item);
  });
  groups.forEach(items => items.forEach((item, idx) => sectorRanks.set(item.row.ticker, idx + 1)));
  return { ranks, sectorRanks, validCount: ranked.length, ranked };
}

function fmtRawMetric(label, value) {
  const n = stockNum(value);
  if (n === null) return `${html(label)} -`;
  if (/성장/.test(label)) return `${html(label)} ${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
  const isRatio = /ROE|수익률|외국인|FCF|부채/.test(label);
  if (isRatio) return `${html(label)} ${(n * 100).toFixed(1)}%`;
  if (/거래대금/.test(label)) return `${html(label)} ${fmtCompact(n)}`;
  return `${html(label)} ${fmtNum(n, 2)}`;
}

function stockFactorByKey(row, key) {
  const profile = Array.isArray(row.factor_profile) ? row.factor_profile : [];
  return profile.find(p => p.key === key);
}

function scenarioFactorKeys(scoreKey) {
  const map = {
    market_attractiveness_score: ["valuation", "momentum", "flow", "roe", "liquidity"],
    scenario_a_momentum: ["momentum", "flow", "liquidity", "earnings"],
    scenario_b_value_quality: ["valuation", "sector_value", "roe", "bs_quality", "cf_quality", "earnings"],
    scenario_c_reversal: ["reversal", "valuation", "sector_value", "flow"],
    scenario_d_large_stable: ["liquidity", "roe", "valuation", "flow", "bs_quality"],
    score_base_5factor: ["valuation", "momentum", "liquidity", "roe"],
    score_value_quality: ["valuation", "roe", "bs_quality", "cf_quality", "earnings"],
    score_momentum_flow: ["momentum", "flow", "liquidity"],
    score_reversal_value_flow: ["reversal", "valuation", "flow"],
    score_short_squeeze_addon: ["momentum", "flow"],
    regime_adj_score: ["momentum", "flow", "valuation", "roe"],
    pullback_rebound_score: ["momentum", "reversal", "flow", "news_sentiment", "minute_tick"],
    breakout_continuation_score: ["momentum", "flow", "liquidity", "minute_tick", "news_sentiment"],
    short_squeeze_candidate_score: ["shorting_pressure", "momentum", "news_sentiment"],
    turnaround_recovery_score: ["earnings", "target_price", "valuation", "insider_signal", "shareholder_return_event"]
  };
  return map[scoreKey] || map.market_attractiveness_score;
}

function buildWhyHtml(row, scoreKey, rank, sectorRank, sectorCount) {
  const keys = scenarioFactorKeys(scoreKey);
  const factors = keys.map(k => stockFactorByKey(row, k)).filter(Boolean)
    .sort((a, b) => (stockNum(b.score) ?? -Infinity) - (stockNum(a.score) ?? -Infinity))
    .slice(0, 4);
  const reasons = factors.map(f => {
    const s = f.score == null ? "-" : `${Number(f.score).toFixed(1)}점`;
    return `<li><b>${html(f.label)}</b> ${s}<span style="color:var(--text-sub);"> · ${fmtRawMetric(f.raw_label || "원값", f.raw)}</span></li>`;
  }).join("");
  const riskFlags = Array.isArray(row.risk_flags) ? row.risk_flags : [];
  const risks = riskFlags.length
    ? riskFlags.map(v => `<span class="tag" style="border-color:rgba(239,68,68,0.45); color:#fca5a5;">${html(v)}</span>`).join(" ")
    : '<span class="tag" style="border-color:rgba(16,185,129,0.35); color:#86efac;">주요 리스크 플래그 없음</span>';
  const rankText = rank ? `전체 #${rank.toLocaleString("ko-KR")}` : "전체 순위 산정불가";
  const sectorText = sectorRank ? `${html(row.sector || "업종 미분류")} 내 #${sectorRank.toLocaleString("ko-KR")}/${sectorCount.toLocaleString("ko-KR")}` : "섹터 순위 산정불가";
  const ret3m = stockNum(row.ret_3m);
  const retText = ret3m === null ? "3개월 변화 -" : `최근 3개월 ${ret3m >= 0 ? "+" : ""}${(ret3m * 100).toFixed(1)}%`;
  return `
    <div class="stock-why-box">
      <div style="font-size:0.72rem; color:var(--text-sub); margin-bottom:5px;">${rankText} · ${sectorText} · ${retText}</div>
      <div style="font-size:0.75rem; color:var(--text-heading); font-weight:800; margin-bottom:4px;">왜 선정됐나</div>
      <ul>${reasons || "<li>표시 가능한 팩터 breakdown이 부족합니다.</li>"}</ul>
      <div style="display:flex; gap:4px; flex-wrap:wrap;">${risks}</div>
    </div>`;
}

function hasRisk(row, pattern = null) {
  const flags = Array.isArray(row.risk_flags) ? row.risk_flags : [];
  if (!pattern) return flags.length > 0;
  return flags.some(flag => pattern.test(String(flag)));
}

function stockActionScore(row, keys) {
  const vals = keys.map(k => stockNum(row[k])).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function buildActionCandidateBuckets(rows, scoreKey, rankInfo) {
  const rankedRows = rows.filter(r => stockNum(r[scoreKey]) !== null);
  const rankOf = row => rankInfo?.ranks?.get(row.ticker) || 999999;
  const noSevereRisk = row => !hasRisk(row, /거래대금|유동성|과열|급등|공매도|데이터 부족|결측|변동성/i);
  const enoughLiquidity = row => (stockNum(row.trading_value) ?? 0) >= 1_000_000_000 || (stockNum(row.liquidity_score) ?? 0) >= 0.55;
  const positiveFlow = row => (stockNum(row.flow_score) ?? 0) >= 0.55 || (stockNum(row.foreign_net_ratio_change) ?? -999) > 0 || (stockNum(row.inst_net_ratio_change) ?? -999) > 0;

  const candidateDefs = [
    {
      key: "buy",
      title: "매수 후보",
      icon: "fa-cart-shopping",
      color: "#10b981",
      desc: "가치+퀄리티·모멘텀/수급·유동성이 동시에 양호한 우선 점검군",
      rows: rankedRows.filter(row => {
        const blend = stockActionScore(row, ["scenario_b_value_quality", "score_momentum_flow", scoreKey]);
        return blend !== null && blend >= 0.58 && enoughLiquidity(row) && positiveFlow(row) && noSevereRisk(row) && rankOf(row) <= 120;
      }).sort((a, b) => (stockActionScore(b, ["scenario_b_value_quality", "score_momentum_flow", scoreKey]) ?? -1) - (stockActionScore(a, ["scenario_b_value_quality", "score_momentum_flow", scoreKey]) ?? -1))
    },
    {
      key: "watch",
      title: "관찰 후보",
      icon: "fa-eye",
      color: "#3b82f6",
      desc: "점수는 높지만 리스크 플래그/품질 결측/추가 확인이 필요한 후보",
      rows: rankedRows.filter(row => {
        const s = stockNum(row[scoreKey]);
        const qualityMissing = row.balance_sheet_quality_score == null || row.cashflow_quality_score == null || row.earnings_stability_score == null;
        return s !== null && s >= 0.6 && (hasRisk(row) || qualityMissing) && rankOf(row) <= 160;
      }).sort((a, b) => (stockNum(b[scoreKey]) ?? -1) - (stockNum(a[scoreKey]) ?? -1))
    },
    {
      key: "chase_risk",
      title: "급등 추격 주의",
      icon: "fa-triangle-exclamation",
      color: "#ef4444",
      desc: "최근 상승/과열 신호가 강해 신규 진입 전 눌림·거래대금 확인 필요",
      rows: rankedRows.filter(row => {
        const ret3m = stockNum(row.ret_3m);
        const ret6m = stockNum(row.ret_6m);
        const rsi = stockNum(row.rsi_14);
        const momentum = stockNum(row.momentum_score);
        return (ret3m !== null && ret3m >= 0.3) || (ret6m !== null && ret6m >= 0.7) || (rsi !== null && rsi >= 70) || (momentum !== null && momentum >= 0.85 && hasRisk(row, /과열|급등|추격/i));
      }).sort((a, b) => (stockNum(b.ret_3m) ?? stockNum(b.ret_6m) ?? -1) - (stockNum(a.ret_3m) ?? stockNum(a.ret_6m) ?? -1))
    },
    {
      key: "recovery",
      title: "저평가 회복 후보",
      icon: "fa-seedling",
      color: "#f59e0b",
      desc: "저PBR/저PER·평균회귀·수급 개선이 함께 보이는 반등 후보",
      rows: rankedRows.filter(row => {
        const pbr = stockNum(row.pbr ?? row.consensus_pbr);
        const per = stockNum(row.per ?? row.consensus_per);
        const reversal = stockNum(row.score_reversal_value_flow ?? row.scenario_c_reversal);
        const meanrev = stockNum(row.meanrev_score);
        const value = stockNum(row.valuation_score ?? row.sector_value_score ?? row.value_composite_score);
        return ((pbr !== null && pbr > 0 && pbr <= 1.2) || (per !== null && per > 0 && per <= 12) || (value !== null && value >= 0.6))
          && ((reversal !== null && reversal >= 0.55) || (meanrev !== null && meanrev >= 0.55))
          && positiveFlow(row);
      }).sort((a, b) => (stockActionScore(b, ["score_reversal_value_flow", "scenario_c_reversal", "valuation_score", "flow_score"]) ?? -1) - (stockActionScore(a, ["score_reversal_value_flow", "scenario_c_reversal", "valuation_score", "flow_score"]) ?? -1))
    }
  ];
  return candidateDefs.map(def => ({ ...def, rows: def.rows.slice(0, 5) }));
}

function renderActionCandidateCard(def, scoreKey, rankInfo) {
  const items = def.rows.map((row, idx) => {
    const rank = rankInfo?.ranks?.get(row.ticker);
    const score = stockNum(row[scoreKey]);
    const ret3m = stockNum(row.ret_3m);
    const riskFlags = Array.isArray(row.risk_flags) ? row.risk_flags.slice(0, 2) : [];
    const tags = [
      row.sector || "업종 미분류",
      rank ? `#${rank}` : null,
      score !== null ? `${(score * 100).toFixed(1)}점` : null,
      row.model_score != null ? `모델 ${String(row.model_decision || "-")} ${(Number(row.model_score) * 100).toFixed(1)}점` : null,
      ret3m !== null ? `3M ${ret3m >= 0 ? "+" : ""}${(ret3m * 100).toFixed(1)}%` : null,
    ].filter(Boolean);
    const riskHtml = riskFlags.length ? `<div style="margin-top:5px; display:flex; gap:4px; flex-wrap:wrap;">${riskFlags.map(v => `<span class="tag" style="border-color:rgba(239,68,68,0.35); color:#fca5a5;">${html(v)}</span>`).join("")}</div>` : "";

    return `<div style="padding:9px 0; border-top:${idx === 0 ? "0" : "1px solid var(--card-border)"};">
      <div style="display:flex; justify-content:space-between; gap:8px; align-items:flex-start;">
        <div>
          <div style="font-weight:900; color:var(--text-heading);">${html(row.name || row.ticker)} <span style="font-size:0.72rem; color:var(--text-sub);">${html(row.ticker)}</span></div>
          <div style="font-size:0.72rem; color:var(--text-sub); margin-top:3px;">${tags.map(html).join(" · ")}</div>
        </div>
        <button class="filter-btn" onclick="openStockFromCandidate('${html(row.ticker)}')" style="padding:4px 7px; font-size:0.7rem;">보기</button>
      </div>
      ${riskHtml}
    </div>`;
  }).join("");
  return `<div style="border:1px solid ${def.color}55; border-radius:10px; padding:12px; background:${def.color}0f; min-height:190px;">
    <div style="display:flex; justify-content:space-between; gap:8px; align-items:center; margin-bottom:7px;">
      <div style="font-weight:900; color:${def.color};"><i class="fa-solid ${def.icon}"></i> ${html(def.title)}</div>
      <span class="tag" style="border-color:${def.color}55; color:${def.color};">${def.rows.length}개</span>
    </div>
    <div style="font-size:0.74rem; color:var(--text-sub); line-height:1.45; margin-bottom:6px;">${html(def.desc)}</div>
    ${items || `<div style="color:var(--text-sub); font-size:0.78rem; padding:14px 0;">현재 조건에 맞는 종목이 없습니다.</div>`}
  </div>`;
}

function renderStockActionCandidates(filtered, scoreKey, rankInfo) {
  const el = document.getElementById("stock-action-candidates");
  const meta = document.getElementById("stock-action-candidates-meta");
  if (!el) return;
  const buckets = buildActionCandidateBuckets(filtered, scoreKey, rankInfo);
  el.innerHTML = buckets.map(def => renderActionCandidateCard(def, scoreKey, rankInfo)).join("");
  if (meta) {
    const total = buckets.reduce((acc, def) => acc + def.rows.length, 0);
    meta.textContent = `분류 후보 ${total.toLocaleString("ko-KR")}개 · 현재 필터 기준`;
  }
}

function populateActionCandidateSectorFilter(rows) {
  const select = document.getElementById("action-candidate-sector");
  if (!select || select.dataset.ready === "1") return;
  const sectors = [...new Set(rows.map(r => r.sector).filter(Boolean))].sort();
  select.innerHTML = '<option value="all">전체</option>' + sectors.map(s => `<option value="${html(s)}">${html(s)}</option>`).join("");
  select.dataset.ready = "1";
}

function renderStockActionCandidatesTab() {
  const payload = window.QUANT_DATA?.stock_attractiveness || {};
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const el = document.getElementById("stock-action-candidates");
  if (!el) return;
  populateActionCandidateSectorFilter(rows);

  const market = document.getElementById("action-candidate-market")?.value || "B_PROJECT_DEFAULT";
  const size = document.getElementById("action-candidate-size")?.value || "all";
  const sector = document.getElementById("action-candidate-sector")?.value || "all";
  const scoreKey = document.getElementById("action-candidate-sort")?.value || "market_attractiveness_score";

  const universeRows = rows.filter(row => passesUniverseFilter(row, market));
  const filtered = universeRows.filter(row => {
    if (size !== "all" && row.size_bucket !== size) return false;
    if (sector !== "all" && row.sector !== sector) return false;
    return true;
  }).sort((a, b) => (stockNum(b[scoreKey]) ?? -Infinity) - (stockNum(a[scoreKey]) ?? -Infinity));

  const rankInfo = buildScenarioRanks(universeRows, scoreKey);
  renderStockActionCandidates(filtered, scoreKey, rankInfo);

  const meta = document.getElementById("stock-action-candidates-meta");
  if (meta) {
    const label = STOCK_SCENARIOS[scoreKey]?.label || scoreKey;
    meta.innerHTML = `기준일 ${html(payload.as_of || "-")}<br>${universeLabel(market)} · ${filtered.length.toLocaleString("ko-KR")}개 · ${html(label)}`;
  }
}
window.renderStockActionCandidatesTab = renderStockActionCandidatesTab;

function openStockFromCandidate(ticker) {
  document.getElementById("btn-tab-analysis")?.click();
  const btn = document.querySelector("#nav-sub-analysis .sub-tab-btn[onclick*=\"analysis-market-attractiveness\"]");
  btn?.click();
  setTimeout(() => {
    const search = document.getElementById("stock-attractiveness-search");
    if (search) search.value = ticker;
    renderStockAttractiveness();
  }, 60);
}
window.openStockFromCandidate = openStockFromCandidate;

function renderStockRankingInsights(filtered, scoreKey, rankInfo) {
  const summary = document.getElementById("stock-ranking-summary");
  const leaders = document.getElementById("stock-sector-leaders");
  if (summary) {
    const top = filtered.find(r => stockNum(r[scoreKey]) !== null);
    const avg = filtered.map(r => stockNum(r[scoreKey])).filter(v => v !== null);
    const avgScore = avg.length ? (avg.reduce((a,b) => a + b, 0) / avg.length * 100).toFixed(1) : "-";
    summary.innerHTML = [
      ["표시 종목", `${filtered.length.toLocaleString("ko-KR")}개`],
      ["선택 기준", STOCK_SCENARIOS[scoreKey]?.label || scoreKey],
      ["평균 점수", `${avgScore}${avgScore === "-" ? "" : "점"}`],
      ["현재 1위", top ? `${html(top.name)} (${html(top.ticker)})` : "-"],
    ].map(([k,v]) => `<div style="padding:10px; border:1px solid var(--card-border); border-radius:8px; background:var(--btn-bg);"><div style="font-size:0.72rem; color:var(--text-sub);">${k}</div><div style="font-weight:900; color:var(--text-heading); margin-top:3px;">${v}</div></div>`).join("");
  }
  if (leaders) {
    const bySector = new Map();
    filtered.forEach(row => {
      const sector = row.sector || "업종 미분류";
      const score = stockNum(row[scoreKey]);
      if (score === null) return;
      if (!bySector.has(sector) || score > bySector.get(sector).score) bySector.set(sector, { row, score });
    });
    const cards = [...bySector.entries()].sort((a,b) => b[1].score - a[1].score).slice(0, 12).map(([sector, item]) => {
      const rank = rankInfo.ranks.get(item.row.ticker);
      return `<div style="padding:10px; border:1px solid var(--card-border); border-radius:8px; background:var(--btn-bg);">
        <div style="font-size:0.72rem; color:var(--text-sub);">${html(sector)}</div>
        <div style="font-weight:900; color:var(--text-heading); margin-top:3px;">${html(item.row.name)} <span style="color:var(--text-sub); font-size:0.75rem;">${html(item.row.ticker)}</span></div>
        <div style="font-size:0.76rem; color:#10b981; margin-top:4px;">${(item.score * 100).toFixed(1)}점 · 전체 #${rank || "-"}</div>
      </div>`;
    }).join("");
    leaders.innerHTML = cards || '<div style="color:var(--text-sub); font-size:0.84rem;">조건에 맞는 섹터 상위 종목이 없습니다.</div>';
  }
}

function passesUniverseFilter(row, market) {
  if (market === "B_PROJECT_DEFAULT") return !!row.project_universe_b;
  if (market === "A_KOSPI200_PROXY" || market === "KOSPI200_PROXY") return !!row.kospi200_proxy;
  if (market === "C_SCREENABLE") return !!row.all_listed_screenable;
  if (market === "KOSPI" || market === "KOSDAQ") return row.market === market;
  return true;
}

function universeLabel(value) {
  const labels = {
    B_PROJECT_DEFAULT: "B 기본: KOSPI200+KOSDAQ150",
    A_KOSPI200_PROXY: "A KOSPI200 proxy",
    C_SCREENABLE: "C 전체상장 스크리닝",
    all: "전체 상장사",
    KOSPI: "KOSPI 전체",
    KOSDAQ: "KOSDAQ 전체",
  };
  return labels[value] || value;
}

function renderStockUniverseSummary(rows, market) {
  const el = document.getElementById("stock-universe-summary");
  if (!el) return;
  const payload = window.QUANT_DATA?.stock_attractiveness || {};
  const counts = payload.universe?.counts || {};
  const cards = [
    ["B 기본", counts.b_project_default ?? rows.filter(r => r.project_universe_b).length, "KOSPI200 proxy + KOSDAQ150 proxy · 현재 프로젝트 기본"],
    ["A 별도 플래그", counts.a_kospi200_proxy ?? rows.filter(r => r.kospi200_proxy).length, "KOSPI 시총 상위 200 proxy · 안정적 백테스팅"],
    ["C 스크리닝", counts.c_screenable ?? rows.filter(r => r.all_listed_screenable).length, "전체 상장사 중 최소 시총/거래대금 필터 통과"],
    ["현재 선택", rows.filter(r => passesUniverseFilter(r, market)).length, universeLabel(market)],
  ];
  el.innerHTML = cards.map(([title, value, desc]) => `<div style="padding:10px; border:1px solid var(--card-border); border-radius:8px; background:var(--btn-bg);">
    <div style="font-size:0.72rem; color:var(--text-sub);">${html(title)}</div>
    <div style="font-weight:900; color:var(--text-heading); margin-top:3px;">${Number(value || 0).toLocaleString("ko-KR")}개</div>
    <div style="font-size:0.72rem; color:var(--text-sub); margin-top:4px; line-height:1.45;">${html(desc)}</div>
  </div>`).join("");
}

function renderScenarioBacktestSummary(scoreKey, validCount, totalCount) {
  const el = document.getElementById("scenario-backtest-summary");
  if (!el) return;
  const metrics = STOCK_BACKTEST_SUMMARY
    .filter(r => r.scoreKey === scoreKey)
    .sort((a, b) => a.horizon_m - b.horizon_m || a.topn - b.topn);
  if (!metrics.length) {
    el.innerHTML = `
      <div style="color:var(--text-sub); font-size:0.84rem;">현재 선택 시나리오는 별도 TopN 백테스트 요약이 없습니다.</div>
      <div style="color:var(--text-sub); font-size:0.78rem; margin-top:6px;">점수 산정 가능 종목 ${validCount.toLocaleString("ko-KR")}개 / 전체 ${totalCount.toLocaleString("ko-KR")}개</div>
    `;
    return;
  }
  const best = metrics.reduce((acc, r) => (!acc || r.avg_excess_return > acc.avg_excess_return ? r : acc), null);
  el.innerHTML = `
    <div style="display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px;">
      <div>
        <div style="font-weight:900; color:var(--text-heading);">TopN 백테스트 요약 · 전체 종목 시나리오 순위 적용</div>
        <div style="color:var(--text-sub); font-size:0.78rem; margin-top:3px;">점수 산정 가능 종목 ${validCount.toLocaleString("ko-KR")}개 / 전체 ${totalCount.toLocaleString("ko-KR")}개 · 결측은 임의 보정하지 않음</div>
      </div>
      <div style="color:#10b981; font-weight:900;">최고 초과수익 ${fmtBacktestPct(best?.avg_excess_return)}</div>
    </div>
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr)); gap:8px;">
      ${metrics.map(r => `
        <div style="border:1px solid var(--card-border); border-radius:8px; padding:10px; background:var(--btn-bg);">
          <div style="font-weight:800; color:var(--text-heading);">Top${r.topn} · ${r.horizon_m}개월</div>
          <div style="font-size:0.78rem; color:var(--text-sub); margin-top:5px;">평균 ${fmtBacktestPct(r.avg_forward_return)} / 벤치 ${fmtBacktestPct(r.avg_benchmark_return)}</div>
          <div style="font-size:0.78rem; color:${r.avg_excess_return >= 0 ? "#10b981" : "#ef4444"}; font-weight:800;">초과 ${fmtBacktestPct(r.avg_excess_return)} · 승률 ${fmtBacktestPct(r.hit_rate_vs_benchmark, 0)}</div>
          <div style="font-size:0.72rem; color:var(--text-sub);">표본 ${r.periods}개월 · MDD ${fmtBacktestPct(r.max_drawdown_chain)}</div>
        </div>
      `).join("")}
    </div>
  `;
}

const ENTRY_TIMING_KEYS = new Set(["pullback_rebound_score", "breakout_continuation_score", "short_squeeze_candidate_score", "turnaround_recovery_score"]);

function renderScenarioToggles() {
  const wrap = document.getElementById("regression-scenario-toggles");
  const detail = document.getElementById("regression-scenario-detail");
  if (!wrap || !detail) return;

  const baseEntries = Object.entries(STOCK_SCENARIOS).filter(([k]) => !ENTRY_TIMING_KEYS.has(k));
  const timingEntries = Object.entries(STOCK_SCENARIOS).filter(([k]) => ENTRY_TIMING_KEYS.has(k));

  function btnHtml([key, s]) {
    return `<button class="filter-btn ${window.activeStockScenario === key ? "active" : ""}" onclick="setStockScenario('${key}')" style="height:auto; display:flex; flex-direction:column; align-items:flex-start; gap:4px; padding:10px 12px;">
      <span style="font-weight:800; color:var(--text-heading);">${html(s.label)}</span>
      <span style="font-size:0.75rem; color:var(--text-sub);">${html(s.horizon)}</span>
    </button>`;
  }

  wrap.innerHTML = `
    <div style="grid-column:1/-1; display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:10px;">
      ${baseEntries.map(btnHtml).join("")}
    </div>
    <div style="grid-column:1/-1; margin-top:10px; padding:10px 0 4px; border-top:1px solid var(--card-border);">
      <span style="font-size:0.75rem; font-weight:700; color:var(--primary); letter-spacing:0.05em;">단타/스윙 진입 타이밍</span>
    </div>
    <div style="grid-column:1/-1; display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:10px;">
      ${timingEntries.map(btnHtml).join("")}
    </div>
  `;

  const s = STOCK_SCENARIOS[window.activeStockScenario] || STOCK_SCENARIOS.market_attractiveness_score;
  const isTimingScenario = ENTRY_TIMING_KEYS.has(window.activeStockScenario);
  detail.innerHTML = `
    <div style="font-weight:800; color:var(--text-heading); margin-bottom:5px;">${html(s.label)} · ${html(s.horizon)}${isTimingScenario ? ' <span style="font-size:0.72rem; color:#f59e0b; border:1px solid #f59e0b; padding:2px 6px; border-radius:4px; font-weight:600;">진입 타이밍</span>' : ""}</div>
    <div>${html(s.desc)}</div>
    <div style="margin-top:8px; display:flex; gap:6px; flex-wrap:wrap;">
      ${s.factors.map(f => `<span class="tag">${html(f)}</span>`).join("")}
    </div>
  `;
}

function setStockScenario(key) {
  window.activeStockScenario = key;
  const sort = document.getElementById("stock-filter-sort");
  if (sort && !key.startsWith("horizon_")) sort.value = key;
  renderStockAttractiveness();
}
window.setStockScenario = setStockScenario;

function toggleStockQuickFilter(key, btn) {
  window.activeStockQuickFilters = window.activeStockQuickFilters || new Set();
  if (window.activeStockQuickFilters.has(key)) {
    window.activeStockQuickFilters.delete(key);
    btn?.classList.remove("active");
  } else {
    window.activeStockQuickFilters.add(key);
    btn?.classList.add("active");
  }
  renderStockAttractiveness();
}
window.toggleStockQuickFilter = toggleStockQuickFilter;

function passesStockQuickFilters(row) {
  const filters = window.activeStockQuickFilters || new Set();
  for (const f of filters) {
    if (f === "low-pbr" && !(stockNum(row.pbr) > 0 && stockNum(row.pbr) <= 1)) return false;
    if (f === "low-per" && !(stockNum(row.per) > 0 && stockNum(row.per) <= 12)) return false;
    if (f === "op-growth" && !(stockNum(row.this_year_op_growth_pct) > 0 || stockNum(row.next_year_op_growth_pct) > 0 || stockNum(row.op_profit_yoy) > 0)) return false;
    if (f === "high-roe" && !(stockNum(row.roe_score) >= 0.7 || stockNum(row.roe) >= 0.1)) return false;
    if (f === "high-liquidity" && !(stockNum(row.trading_value) >= 10_000_000_000 || stockNum(row.liquidity_score) >= 0.7)) return false;
    if (f === "consensus" && row.recent_op_profit == null && row.this_year_op_profit_est == null && row.next_year_op_profit_est == null) return false;
  }
  return true;
}

function populateStockSectorFilter(rows) {
  const select = document.getElementById("stock-filter-sector");
  if (!select || select.dataset.ready === "1") return;
  const sectors = [...new Set(rows.map(r => r.sector).filter(Boolean))].sort();
  select.innerHTML = '<option value="all">전체</option>' + sectors.map(s => `<option value="${html(s)}">${html(s)}</option>`).join("");
  select.dataset.ready = "1";
}

function renderRegressionPanel() {
  const reg = window.QUANT_DATA?.regression || {};
  const panel = document.getElementById("regression-insight-panel");
  if (!panel) return;
  if (!reg.as_of) return;

  const mt = reg.market_timing || {};
  const fi = reg.factor_ic || {};
  const re = reg.regime || {};
  const staleInputs = Array.isArray(mt.stale_inputs) ? mt.stale_inputs : [];
  const usesForwardFill = !!mt.uses_forward_fill || staleInputs.length > 0;
  const stalePenaltyPct = mt.stale_penalty != null ? Math.round(Number(mt.stale_penalty) * 100) : 0;

  const asOf = document.getElementById("regression-as-of");
  if (asOf) {
    const confidenceLabel = { high: "높음", medium: "중간", low: "낮음" }[mt.signal_confidence] || "-";
    const staleBadge = usesForwardFill
      ? ` <span style="color:#f59e0b; font-weight:800;">⚠ stale ${staleInputs.length}개 · penalty ${stalePenaltyPct}% · 신뢰도 ${confidenceLabel}</span>`
      : "";
    asOf.innerHTML = `예측 기준: ${mt.pred_period || reg.as_of} / 완성 입력: ${mt.complete_period || reg.as_of}${staleBadge}`;
  }

  // 시그널 색상
  const sigColor = mt.signal === "bullish" ? "#10b981" : mt.signal === "bearish" ? "#ef4444" : "#f59e0b";
  const sigLabel = { bullish: "강세 진입", neutral: "중립 대기", bearish: "약세 회피" }[mt.signal] || mt.signal;
  const sigIcon  = { bullish: "fa-arrow-trend-up", neutral: "fa-minus", bearish: "fa-arrow-trend-down" }[mt.signal] || "fa-minus";

  const regimeLabelMap = { risk_on: "위험선호", risk_off: "위험회피", growth_on: "성장랠리", dollar_pressure: "달러압박", export_recovery: "수출회복", neutral: "중립", other: "기타" };
  const regimeColor = re.current_bucket === "risk_on" ? "#10b981" : re.current_bucket === "risk_off" ? "#ef4444" : "#f59e0b";

  const topCards = document.getElementById("regression-top-cards");
  if (topCards) topCards.innerHTML = `
    <div style="border:1px solid ${sigColor}40; border-radius:10px; padding:16px; background:${sigColor}08;">
      <div style="font-size:0.75rem; color:var(--text-sub); font-weight:700; margin-bottom:6px;">시장 타이밍 신호</div>
      <div style="display:flex; align-items:center; gap:10px;">
        <i class="fa-solid ${sigIcon}" style="font-size:1.6rem; color:${sigColor};"></i>
        <div>
          <div style="font-size:1.25rem; font-weight:900; color:${sigColor};">${sigLabel}</div>
          <div style="font-size:0.78rem; color:var(--text-sub); margin-top:2px;">예측 ${mt.pred_pct != null ? (mt.pred_pct >= 0 ? "+" : "") + mt.pred_pct.toFixed(2) + "%" : "-"}${usesForwardFill && mt.raw_pred_pct != null ? ` <span style="color:#f59e0b;">(raw ${(mt.raw_pred_pct >= 0 ? "+" : "") + mt.raw_pred_pct.toFixed(2)}%)</span>` : ""} / R² ${mt.r2 != null ? (mt.r2 * 100).toFixed(1) + "%" : "-"} · ${mt.periods || 0}개월 기간</div>
          ${usesForwardFill ? `<div style="font-size:0.72rem; color:#f59e0b; margin-top:6px; line-height:1.45;">실전형 최신화: 완성 입력 ${mt.complete_period || "-"} → 예측 ${mt.pred_period || reg.as_of}; 누락 입력 ${staleInputs.length}개 forward-fill · penalty ${stalePenaltyPct}%</div>` : ""}
        </div>
      </div>
    </div>
    <div style="border:1px solid ${regimeColor}40; border-radius:10px; padding:16px; background:${regimeColor}08;">
      <div style="font-size:0.75rem; color:var(--text-sub); font-weight:700; margin-bottom:6px;">현재 시장 레짐</div>
      <div style="font-size:1.25rem; font-weight:900; color:${regimeColor};">${regimeLabelMap[re.current_regime] || re.current_regime || "-"}</div>
      <div style="font-size:0.78rem; color:var(--text-sub); margin-top:4px;">
        버킷: ${regimeLabelMap[re.current_bucket] || re.current_bucket || "-"} · ${re.current_period || ""}
      </div>
    </div>
    <div style="border:1px solid var(--card-border); border-radius:10px; padding:16px; background:var(--btn-bg);">
      <div style="font-size:0.75rem; color:var(--text-sub); font-weight:700; margin-bottom:6px;">Fama-MacBeth 분석</div>
      <div style="font-size:1.1rem; font-weight:700; color:var(--text-heading);">${fi.periods || 0}개월 / ${fi.stock_count || 0}종목</div>
      <div style="font-size:0.78rem; color:var(--text-sub); margin-top:4px;">횡단면 회귀 × Newey-West t-stat</div>
    </div>
  `;

  // 시장 타이밍 팩터 바
  const factorBars = document.getElementById("regression-factor-bars");
  if (factorBars && mt.factors) {
    const maxAbs = Math.max(...mt.factors.map(f => Math.abs(f.coef_ols || 0)), 0.01);
    factorBars.innerHTML = mt.factors.slice().sort((a, b) => Math.abs(b.coef_ols) - Math.abs(a.coef_ols)).map(f => {
      const pct = Math.abs((f.coef_ols || 0) / maxAbs) * 100;
      const c = f.coef_ols >= 0 ? "#10b981" : "#ef4444";
      const sig = f.significant ? "★" : "";
      const staleMark = f.stale ? ` <span style="color:#f59e0b; font-size:0.68rem; font-weight:800;">STALE ${html(f.source_period || "")}</span>` : "";
      return `<div style="display:flex; align-items:center; gap:8px; font-size:0.77rem;">
        <div style="min-width:116px; color:var(--text-sub); text-align:right;">${f.label || f.key}${staleMark}</div>
        <div style="flex:1; background:var(--card-border); border-radius:4px; height:10px; overflow:hidden;">
          <div style="width:${pct.toFixed(1)}%; background:${c}; height:100%; border-radius:4px;"></div>
        </div>
        <div style="min-width:60px; color:${f.significant ? c : "var(--text-sub)"}; font-weight:${f.significant ? "700" : "400"};">${sig}t=${f.t_stat?.toFixed(2) || "-"}</div>
      </div>`;
    }).join("");
  }

  // Fama-MacBeth IC 바
  const fmBars = document.getElementById("fm-factor-bars");
  if (fmBars && fi.factors) {
    const maxIC = Math.max(...fi.factors.map(f => Math.abs(f.ic_mean || 0)), 0.01);
    fmBars.innerHTML = fi.factors.slice().sort((a, b) => Math.abs(b.ic_mean) - Math.abs(a.ic_mean)).map(f => {
      const pct = Math.abs((f.ic_mean || 0) / maxIC) * 100;
      const c = (f.ic_mean || 0) >= 0 ? "#10b981" : "#ef4444";
      const sig = f.significant ? "★" : "";
      return `<div style="display:flex; align-items:center; gap:8px; font-size:0.77rem;">
        <div style="min-width:90px; color:var(--text-sub); text-align:right;">${f.label || f.key}</div>
        <div style="flex:1; background:var(--card-border); border-radius:4px; height:10px; overflow:hidden;">
          <div style="width:${pct.toFixed(1)}%; background:${c}; height:100%; border-radius:4px;"></div>
        </div>
        <div style="min-width:80px; color:${f.significant ? c : "var(--text-sub)"}; font-weight:${f.significant ? "700" : "400"};">${sig}IC=${f.ic_mean?.toFixed(4) || "-"} t=${f.ic_t?.toFixed(2) || "-"}</div>
      </div>`;
    }).join("");
  }

  // 레짐별 팩터 IC 테이블
  const regTable = document.getElementById("regime-factor-table");
  if (regTable && re.regimes) {
    const regimes = Object.keys(re.regimes);
    const allFactorKeys = fi.factors?.map(f => ({ key: f.key, label: f.label })) || [];
    const regimeLabelKo = { risk_on: "위험선호(Risk-On)", risk_off: "위험회피(Risk-Off)", other: "중립/기타" };
    regTable.innerHTML = `
      <table style="width:100%; border-collapse:collapse; font-size:0.78rem;">
        <thead>
          <tr>
            <th style="border:1px solid var(--card-border); padding:6px 8px; background:var(--th-bg); color:var(--text-sub);">팩터</th>
            ${regimes.map(r => `<th style="border:1px solid var(--card-border); padding:6px 8px; background:var(--th-bg); color:${r === re.current_bucket ? "var(--primary)" : "var(--text-sub)"};">${regimeLabelKo[r] || r}${r === re.current_bucket ? " ◀현재" : ""}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${allFactorKeys.map(fac => `
            <tr>
              <td style="border:1px solid var(--card-border); padding:6px 8px; color:var(--text-sub);">${fac.label}</td>
              ${regimes.map(r => {
                const rf = (re.regimes[r]?.factors || []).find(x => x.key === fac.key);
                const ic = rf?.ic;
                const sig = rf?.sig;
                const t = rf?.t_stat;
                const c = ic == null ? "var(--text-sub)" : ic >= 0 ? "#10b981" : "#ef4444";
                return `<td style="border:1px solid var(--card-border); padding:6px 8px; text-align:center; color:${c}; font-weight:${sig ? "800" : "400"};">
                  ${ic != null ? (sig ? "★" : "") + ic.toFixed(4) + (t != null ? `<br><span style="font-size:0.7rem;">t=${t.toFixed(2)}</span>` : "") : "-"}
                </td>`;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }
}
window.renderRegressionPanel = renderRegressionPanel;

function renderStockAttractiveness() {
  const payload = window.QUANT_DATA?.stock_attractiveness || {};
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const tbody = document.querySelector("#stock-attractiveness-table tbody");
  if (!tbody) return;
  populateStockSectorFilter(rows);

  const meta = document.getElementById("stock-attractiveness-meta");
  if (meta) meta.innerHTML = `기준일 ${html(payload.as_of || "-")}<br>${rows.length.toLocaleString("ko-KR")}개 종목`;

  const term = (document.getElementById("stock-attractiveness-search")?.value || "").trim().toLowerCase();
  const market = document.getElementById("stock-filter-market")?.value || "all";
  const size = document.getElementById("stock-filter-size")?.value || "all";
  const sector = document.getElementById("stock-filter-sector")?.value || "all";
  const sortKey = document.getElementById("stock-filter-sort")?.value || window.activeStockScenario || "market_attractiveness_score";
  if (!window.activeStockScenario || (!window.activeStockScenario.startsWith("horizon_") && window.activeStockScenario !== sortKey)) {
    window.activeStockScenario = sortKey;
  }
  renderScenarioToggles();
  const scoreKey = selectedScenarioKey();
  renderStockUniverseSummary(rows, market);
  const universeRows = rows.filter(row => passesUniverseFilter(row, market));
  const { ranks: scenarioRanks, sectorRanks: scenarioSectorRanks, validCount: scenarioValidCount } = buildScenarioRanks(universeRows, scoreKey);
  renderScenarioBacktestSummary(scoreKey, scenarioValidCount, universeRows.length);

  let filtered = universeRows.filter(row => {
    if (term && !(`${row.name || ""} ${row.ticker || ""}`.toLowerCase().includes(term))) return false;
    if (size !== "all" && row.size_bucket !== size) return false;
    if (sector !== "all" && row.sector !== sector) return false;
    return passesStockQuickFilters(row);
  });

  filtered.sort((a, b) => (stockNum(b[sortKey]) ?? -Infinity) - (stockNum(a[sortKey]) ?? -Infinity));
  const rankInfo = { ranks: scenarioRanks, sectorRanks: scenarioSectorRanks };
  renderStockRankingInsights(filtered, scoreKey, rankInfo);
  const sectorCounts = new Map();
  universeRows.forEach(row => {
    if (stockNum(row[scoreKey]) === null) return;
    const sectorName = row.sector || "업종 미분류";
    sectorCounts.set(sectorName, (sectorCounts.get(sectorName) || 0) + 1);
  });
  const display = filtered.slice(0, 300);
  const scenario = STOCK_SCENARIOS[window.activeStockScenario] || STOCK_SCENARIOS.market_attractiveness_score;

  tbody.innerHTML = display.map(row => {
    const score = scenarioScore(row);
    const rank = scenarioRanks.get(row.ticker);
    const sectorRank = scenarioSectorRanks.get(row.ticker);
    const sectorCount = sectorCounts.get(row.sector || "업종 미분류") || 0;
    const whyHtml = buildWhyHtml(row, scoreKey, rank, sectorRank, sectorCount);
    const scorePct = score == null ? "-" : `${(score * 100).toFixed(1)}점`;
    const scoreColor = score == null ? "var(--text-sub)" : score >= 0.65 ? "#10b981" : score >= 0.5 ? "#f59e0b" : "#ef4444";
    const growthThis = fmtPctValue(row.this_year_op_growth_pct);
    const growthNext = fmtPctValue(row.next_year_op_growth_pct);
    const universeBadges = [row.kospi200_proxy ? "A K200" : null, row.project_universe_b ? "B 기본" : null, row.all_listed_screenable ? "C 스크리닝" : null];
    const badges = [row.market, row.size_bucket, ...universeBadges].filter(Boolean).map(v => `<span class="tag">${html(v)}</span>`).join(" ");
    return `
      <tr onclick="openStockModal('${html(row.name || row.ticker)}')" style="cursor:pointer;" onmouseover="this.style.background='var(--tr-hover-bg)'" onmouseout="this.style.background=''">
        <td>
          <div class="company-name" style="font-size:0.95rem; font-weight:800;">${html(row.name || row.ticker)}</div>
          <div class="company-code" style="font-size:0.75rem; color:var(--text-sub);">${html(row.ticker)} · ${html(row.sector || "업종 미분류")}</div>
          <div style="margin-top:5px; display:flex; gap:4px; flex-wrap:wrap;">${badges}</div>
        </td>
        <td>
          ${(() => {
            // PER 섹터 대비 색상: sector_relative_per < 1 = 섹터보다 싸다
            const perRel = row.sector_relative_per;
            const perColor = perRel == null ? "#3b82f6" : perRel < 0.9 ? "#10b981" : perRel > 1.2 ? "#ef4444" : "#f59e0b";
            const perTip = perRel == null ? "" : perRel < 0.9 ? " ↓싸다" : perRel > 1.2 ? " ↑비싸다" : "";
            const pbrRel = row.sector_relative_pbr;
            const pbrColor = pbrRel == null ? "#8b5cf6" : pbrRel < 0.9 ? "#10b981" : pbrRel > 1.2 ? "#ef4444" : "#f59e0b";
            const roe = row.roe;
            const roeColor = roe == null ? "var(--text-sub)" : roe >= 0.15 ? "#10b981" : roe >= 0.08 ? "#f59e0b" : "#ef4444";
            return `
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:4px 8px; font-size:0.83rem; margin-bottom:6px;">
              <div style="color:var(--text-sub);">PER <b style="color:${perColor};">${fmtNum(row.per ?? row.consensus_per)}<span style="font-size:0.65rem;">${perTip}</span></b></div>
              <div style="color:var(--text-sub);">PBR <b style="color:${pbrColor};">${fmtNum(row.pbr ?? row.consensus_pbr)}</b></div>
              <div style="color:var(--text-sub);">ROE <b style="color:${roeColor};">${fmtPctNumber(row.roe)}</b></div>
            </div>
            <details onclick="event.stopPropagation()">
              <summary style="font-size:0.75rem; color:var(--text-main); cursor:pointer; user-select:none; font-weight:500;">재무 상세 ▾</summary>
              <div class="stock-metric-grid" style="margin-top:6px;">
                <div>부채 <b>${fmtPctNumber(row.debt_ratio, 0)}</b></div>
                <div>FCF <b style="color:#10b981;">${fmtPctNumber(row.fcf_to_assets)}</b></div>
                <div>BS <b>${row.balance_sheet_quality_score == null ? "-" : `${(row.balance_sheet_quality_score * 100).toFixed(0)}점`}</b></div>
                <div>CF <b>${row.cashflow_quality_score == null ? "-" : `${(row.cashflow_quality_score * 100).toFixed(0)}점`}</b></div>
                <div>이익안정 <b>${row.earnings_stability_score == null ? "-" : `${(row.earnings_stability_score * 100).toFixed(0)}점`}</b></div>
                <div>DIV <b>${fmtPctNumber(row.div_yield)}</b></div>
              </div>
            </details>`;
          })()}
        </td>
        <td>
          <div style="display:grid; gap:4px; font-size:0.78rem;">
            <div>최근 <b>${fmtOpProfit(row.recent_op_profit)}</b></div>
            <div>올해 <b style="color:#10b981;">${fmtOpProfit(row.this_year_op_profit_est)}</b>${growthThis}</div>
            <div>내년 <b style="color:#3b82f6;">${fmtOpProfit(row.next_year_op_profit_est)}</b>${growthNext}</div>
          </div>
        </td>
        <td>
          <div>시총 <b>${fmtCompact(row.market_cap)}</b></div>
          <div style="font-size:0.75rem; color:var(--text-sub);">거래대금 ${fmtCompact(row.trading_value)}</div>
          <div style="font-size:0.75rem; color:var(--text-sub);">${html(row.market || "")} ${row.market_cap_rank ? `#${row.market_cap_rank}` : ""}</div>
          ${(() => {
            const rs = row.regime_adj_score;
            if (rs == null) return '<div style="color:var(--text-sub); font-size:0.72rem; margin-top:4px;">레짐 -</div>';
            const c = rs >= 0.65 ? "#10b981" : rs >= 0.45 ? "#f59e0b" : "#ef4444";
            return `<div style="font-size:0.72rem; color:var(--text-sub); margin-top:4px;">레짐 <b style="color:${c};">${(rs * 100).toFixed(1)}</b></div>`;
          })()}
        </td>
        <td>
          <!-- 개선 #6: 종합 매력도 시각적 강조 -->
          <div style="font-size:1.6rem; font-weight:900; color:${scoreColor}; line-height:1;">${scorePct}</div>
          <div style="width:100%; height:12px; background:var(--card-border); border-radius:6px; margin:6px 0; overflow:hidden;">
            <div style="height:100%; width:${score == null ? 0 : Math.round(score*100)}%; background:${scoreColor}; border-radius:6px; transition:width 0.4s ease;"></div>
          </div>
          <div style="font-size:0.72rem; color:var(--text-sub);">${html(scenario.label)}</div>
          <div style="font-size:0.7rem; color:var(--text-sub); margin-top:2px;">전체 ${rank ? `#${rank}/${scenarioValidCount}` : "산정불가"}</div>
          ${row.market_attractiveness_score != null && scoreKey !== "market_attractiveness_score" ? `<div style="font-size:0.7rem; color:var(--text-sub); margin-top:2px;">종합 <b style="color:${row.market_attractiveness_score >= 0.65 ? "var(--c-green)" : row.market_attractiveness_score >= 0.5 ? "var(--c-yellow)" : "var(--c-red)"};">${(row.market_attractiveness_score * 100).toFixed(0)}</b></div>` : ""}
          ${whyHtml}
        </td>
      </tr>
    `;
  }).join("") || '<tr><td colspan="5" style="text-align:center; padding:22px; color:var(--text-sub);">조건에 맞는 종목이 없습니다.</td></tr>';

  const count = document.getElementById("stock-attractiveness-count");
  if (count) count.textContent = `${universeLabel(market)} · 검색 결과 ${filtered.length.toLocaleString("ko-KR")}개 / 화면 표시 ${display.length.toLocaleString("ko-KR")}개 · ${scenario.label} 산정 가능 ${scenarioValidCount.toLocaleString("ko-KR")}개`;
}
window.renderStockAttractiveness = renderStockAttractiveness;

function renderSectorMap() {
  const sectorData = window.QUANT_DATA?.money_flow?.sector_returns;
  const container = document.getElementById("sector-map");
  if (!Array.isArray(sectorData) || !container) return;

  container.innerHTML = "";
  sectorData.forEach((sector) => {
    const name = sector["업종명"];
    const pct = sector["전일대비"];
    if (!name || !pct) return;

    const val = Number.parseFloat(pct) || 0;
    const isUp = val > 0;
    const isDown = val < 0;
    const absVal = Math.abs(val);
    // 강도: 0.3%미만=40%, 1%미만=60%, 2%미만=80%, 2%이상=100%
    const intensity = absVal < 0.3 ? 0.35 : absVal < 1 ? 0.55 : absVal < 2 ? 0.78 : 1.0;
    const bg = isUp
      ? `rgba(239,68,68,${intensity})`
      : isDown
      ? `rgba(59,130,246,${intensity})`
      : "rgba(107,114,128,0.4)";
    const fontSize = absVal >= 2 ? "1.2rem" : absVal >= 1 ? "1.05rem" : "0.95rem";
    const box = document.createElement("div");
    box.className = "sector-box";
    box.style.background = bg;
    box.innerHTML = `<div style="font-size:0.85rem;">${html(name)}</div><div style="font-size:${fontSize}; margin-top:5px; font-weight:${absVal >= 1 ? 800 : 600};">${html(pct)}</div>`;
    container.appendChild(box);
  });
}

function renderLeadingIndicatorCharts() {
  const macro = window.QUANT_DATA?.macro || {};

  ["macro-leading-cli-charts", "macro-leading-sentiment-charts", "macro-leading-derived-charts"]
    .forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ""; });

  if (!window.Chart) return;

  // ── OECD 복합선행지수 (CLI) — 9개국 (FRED 갱신 중단: 2024-01-01 이후 없음)
  const _cliEl = document.getElementById("macro-leading-cli-charts");
  if (_cliEl && !_cliEl.dataset.cliNotice) {
    _cliEl.insertAdjacentHTML("beforebegin",
      "<div style='color:#f59e0b;font-size:0.78rem;margin-bottom:6px;padding:6px 10px;background:rgba(245,158,11,0.08);border-radius:6px;border:1px solid rgba(245,158,11,0.25);'>⚠️ OECD CLI: FRED 원천 갱신 중단 (2024-01-01 이후 업데이트 없음). 최신 경기 동향은 BSI / CCSI / PMI 등 대체지표를 참고하세요.</div>");
    _cliEl.dataset.cliNotice = "1";
  }
  createNormalizedLineChart("macro-leading-cli-charts", "한국 CLI (OECD 진폭조정) ~2024.01", macro.KOR_CLI, "KORLOLITONOSTSAM", "#10b981");
  createNormalizedLineChart("macro-leading-cli-charts", "미국 CLI", macro.USA_CLI, "USALOLITONOSTSAM", "#3b82f6");
  createNormalizedLineChart("macro-leading-cli-charts", "중국 CLI (한국 수출 최대국)", macro.CHN_CLI, "CHNLOLITONOSTSAM", "#ef4444");
  createNormalizedLineChart("macro-leading-cli-charts", "일본 CLI", macro.JPN_CLI, "JPNLOLITONOSTSAM", "#f59e0b");
  createNormalizedLineChart("macro-leading-cli-charts", "독일 CLI", macro.DEU_CLI, "DEULOLITONOSTSAM", "#6b7280");
  createNormalizedLineChart("macro-leading-cli-charts", "영국 CLI", macro.GBR_CLI, "GBRLOLITONOSTSAM", "#a78bfa");
  createNormalizedLineChart("macro-leading-cli-charts", "프랑스 CLI", macro.FRA_CLI, "FRALOLITONOSTSAM", "#f472b6");
  createNormalizedLineChart("macro-leading-cli-charts", "인도 CLI", macro.IND_CLI, "INDLOLITONOSTSAM", "#fb923c");
  createNormalizedLineChart("macro-leading-cli-charts", "브라질 CLI", macro.BRA_CLI, "BRALOLITONOSTSAM", "#a3e635");

  // ── 심리 & 공포 지수
  createNormalizedLineChart("macro-leading-sentiment-charts", "VIX 공포지수 (>30=극도 공포)", macro.VIX, "Close", "#ef4444");
  createNormalizedLineChart("macro-leading-sentiment-charts", "시카고 NFCI 금융환경 (음수=완화)", macro.NFCI, "NFCI", "#8b5cf6");
  createNormalizedLineChart("macro-leading-sentiment-charts", "세인트루이스 STLFSI4 금융스트레스", macro.STLFSI4, "STLFSI4", "#ec4899");
  createNormalizedLineChart("macro-leading-sentiment-charts", "AAII Bull-Bear Spread (%p, 역발상)", macro.aaii_bull_bear, "value", "#06b6d4");

  // ── 신용 & 파생 지표
  createNormalizedLineChart("macro-leading-derived-charts", "미국 Credit Impulse (% of GDP, 9~12M 선행)", macro.us_credit_impulse, "value", "#10b981");
  createNormalizedLineChart("macro-leading-derived-charts", "구리/금 비율 (경기 낙관 방향)", macro.copper_gold_ratio, "value", "#f59e0b");
  createNormalizedLineChart("macro-leading-derived-charts", "SOXX/EEM (반도체 vs 신흥국 상대강도)", macro.soxx_eem_ratio, "value", "#3b82f6");
  createNormalizedLineChart("macro-leading-derived-charts", "한국 회사채 스프레드 AA- (%, ECOS 설정 시)", macro.kor_corp_spread, "value", "#ef4444");

  // ── NAVER DataLab 테마 관심도
  const naverEl = document.getElementById("macro-leading-naver-charts");
  if (naverEl) naverEl.innerHTML = "";
  const naverData = window.QUANT_DATA?.sentiment?.naver_naver_datalab_theme_interest_month;
  if (naverData && Array.isArray(naverData) && window.Chart) {
    const groups = [...new Set(naverData.map(r => r.group_name))];
    const colors = ["#10b981","#3b82f6","#ef4444","#f59e0b","#8b5cf6","#ec4899"];
    groups.forEach((grp, i) => {
      const rows = naverData.filter(r => r.group_name === grp).slice(-36);
      if (!rows.length) return;
      const ctx = createChartCanvas("macro-leading-naver-charts", grp.replace(/_/g," "));
      if (!ctx) return;
      const chart = new Chart(ctx, {
        type: "line",
        data: {
          labels: rows.map(r => r.period?.slice(0,7)),
          datasets: [{ label: grp.replace(/_/g," "), data: rows.map(r => parseFloat(r.ratio)||0),
            borderColor: colors[i % colors.length], backgroundColor: colors[i % colors.length] + "20",
            borderWidth: 2, fill: true, tension: 0.3, pointRadius: 2 }]
        },
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{ legend:{labels:{color:"#d1d5db"}} },
          scales:{ x:{ticks:{maxTicksLimit:6,color:"#6b7280"}}, y:{ticks:{color:"#6b7280"}} } }
      });
      chartInstances.push(chart);
    });
  }
}
window.renderLeadingIndicatorCharts = renderLeadingIndicatorCharts;

function renderSectorMomentumCharts() {
  const el = document.getElementById("quant-sector-momentum-charts");
  if (el) el.innerHTML = "";
  if (!window.Chart) return;

  const sentiment = window.QUANT_DATA?.sentiment || {};
  const rawData = sentiment["naver_naver_datalab_sector_interest_factor_month"];
  if (!Array.isArray(rawData) || !rawData.length) return;

  // 최신 월 데이터만 추출
  const periods = [...new Set(rawData.map(r => r.period))].sort();
  const latestPeriod = periods[periods.length - 1];
  const latest = rawData
    .filter(r => r.period === latestPeriod)
    .sort((a, b) => parseFloat(b.anchor_relative_ratio || 0) - parseFloat(a.anchor_relative_ratio || 0));

  const labels = latest.map(r => r.group_name?.replace(/_/g, " ") || "");
  const ratios = latest.map(r => parseFloat(r.anchor_relative_ratio) || 0);
  const mom1 = latest.map(r => parseFloat(r.momentum_1p) || 0);
  const mom3 = latest.map(r => parseFloat(r.momentum_3p) || 0);

  // 색상: 양수=초록, 음수=빨강
  const barColors = ratios.map(v => v > 1 ? "#10b981" : v > 0 ? "#6ee7b7" : "#ef444488");

  // 차트1: 시장 대비 상대 관심도 (anchor_relative_ratio)
  const ctx1 = createChartCanvas("quant-sector-momentum-charts", `섹터 상대 관심도 (${latestPeriod.slice(0,7)}, 시장 대비 배율)`);
  if (ctx1) {
    const chart1 = new Chart(ctx1, {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "시장 대비 관심도", data: ratios, backgroundColor: barColors, borderColor: barColors, borderWidth: 1 }]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { color: "#6b7280" } }, y: { ticks: { color: "#d1d5db", font: { size: 11 } } } }
      }
    });
    chartInstances.push(chart1);
  }

  // 차트2: 1개월 모멘텀 vs 3개월 모멘텀 산점도
  const ctx2 = createChartCanvas("quant-sector-momentum-charts", "섹터 모멘텀 비교 (1M vs 3M)");
  if (ctx2) {
    const colors2 = latest.map((_, i) => `hsl(${(i / latest.length) * 240}, 70%, 55%)`);
    const chart2 = new Chart(ctx2, {
      type: "scatter",
      data: {
        datasets: [{ label: "섹터", data: latest.map((_, i) => ({ x: mom1[i], y: mom3[i], label: labels[i] })),
          backgroundColor: colors2, pointRadius: 6, pointHoverRadius: 8 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => `${ctx.raw.label}: 1M=${ctx.raw.x?.toFixed(2)}, 3M=${ctx.raw.y?.toFixed(2)}` } }
        },
        scales: {
          x: { title: { display: true, text: "1개월 모멘텀", color: "#6b7280" }, ticks: { color: "#6b7280" } },
          y: { title: { display: true, text: "3개월 모멘텀", color: "#6b7280" }, ticks: { color: "#6b7280" } }
        }
      }
    });
    chartInstances.push(chart2);
  }

  // 차트3: Regime-Adjusted 섹터 점수 (최종 점수)
  const adjData = window.QUANT_DATA?.sentiment?.factors?.regime_adjusted_sector_interest_month;
  if (Array.isArray(adjData) && adjData.length) {
    const adjPeriods = [...new Set(adjData.map(r => r.period))].sort();
    const adjLatest = adjData.filter(r => r.period === adjPeriods[adjPeriods.length - 1])
      .sort((a, b) => parseFloat(b.regime_adjusted_interest_score || 0) - parseFloat(a.regime_adjusted_interest_score || 0));
    if (adjLatest.length) {
      const adjLabels = adjLatest.map(r => r.group_name?.replace(/_/g, " ") || "");
      const adjScores = adjLatest.map(r => parseFloat(r.regime_adjusted_interest_score) || 0);
      const bucketColor = { very_strong: "#10b981", strong: "#34d399", neutral: "#f59e0b", weak: "#f97316", very_weak: "#ef4444" };
      const adjColors = adjLatest.map(r => bucketColor[r.regime_adjusted_bucket] || "#6b7280");
      const ctx_adj = createChartCanvas("quant-sector-momentum-charts", `레짐 조정 섹터 점수 (${adjPeriods[adjPeriods.length-1].slice(0,7)}, Regime: ${adjLatest[0]?.market_regime || ""})`);
      if (ctx_adj) {
        const chart_adj = new Chart(ctx_adj, {
          type: "bar",
          data: {
            labels: adjLabels,
            datasets: [{ label: "Regime-Adjusted Score", data: adjScores, backgroundColor: adjColors, borderColor: adjColors, borderWidth: 1 }]
          },
          options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false },
              tooltip: { callbacks: { afterLabel: ctx => `  → ${adjLatest[ctx.dataIndex]?.regime_adjusted_bucket || ""}` } }
            },
            scales: { x: { min: 0, max: 1, ticks: { color: "#6b7280" } }, y: { ticks: { color: "#d1d5db", font: { size: 11 } } } }
          }
        });
        chartInstances.push(chart_adj);
      }
    }
  }

  // 차트4: 12개월 Z-Score (현재 위치)
  const zscore = latest.map(r => parseFloat(r.zscore_12p) || 0);
  const zColors = zscore.map(v => v > 1 ? "#10b981" : v > 0 ? "#34d399" : v > -1 ? "#f59e0b" : "#ef4444");
  const ctx3 = createChartCanvas("quant-sector-momentum-charts", "섹터 12개월 Z-Score (현재 관심도 위치)");
  if (ctx3) {
    const chart3 = new Chart(ctx3, {
      type: "bar",
      data: {
        labels,
        datasets: [{ label: "Z-Score", data: zscore, backgroundColor: zColors, borderColor: zColors, borderWidth: 1 }]
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { color: "#6b7280" } }, y: { ticks: { color: "#d1d5db", font: { size: 11 } } } }
      }
    });
    chartInstances.push(chart3);
  }
}
window.renderSectorMomentumCharts = renderSectorMomentumCharts;

function renderIndustryCharts() {
  const sentiment = window.QUANT_DATA?.sentiment || {};
  if (!window.Chart) return;

  ["macro-industry-trends-charts", "macro-industry-trends-monthly-charts"].forEach(id => {
    const el = document.getElementById(id); if (el) el.innerHTML = "";
  });

  // 일별 (90일) — 테마 그룹
  const dailyGroups = [
    { label: "반도체", key: "pytrends_반도체_daily", color: "#10b981" },
    { label: "2차전지", key: "pytrends_2차전지_daily", color: "#3b82f6" },
    { label: "AI",    key: "pytrends_AI_daily",               color: "#8b5cf6" },
    { label: "바이오", key: "pytrends_바이오_daily", color: "#ef4444" },
    { label: "방산",  key: "pytrends_방산_daily",       color: "#f59e0b" },
  ];

  dailyGroups.forEach(({ label, key, color }) => {
    const data = sentiment[key];
    if (!Array.isArray(data) || !data.length) return;
    const recent = data.slice(-90);
    const ctx = createChartCanvas("macro-industry-trends-charts", `${label} 검색량 (일별)`);
    if (!ctx) return;
    const chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: recent.map(r => r.date),
        datasets: [{ label, data: recent.map(r => parseFloat(r.trend_score)||0),
          backgroundColor: color + "99", borderColor: color, borderWidth: 1 }]
      },
      options: { responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{labels:{color:"#d1d5db"}} },
        scales:{ x:{ticks:{maxTicksLimit:8,color:"#6b7280"}}, y:{min:0,max:100,ticks:{color:"#6b7280"}} } }
    });
    chartInstances.push(chart);
  });

  // 월별 (5년) — 투자심리 키워드
  const monthlyGroups = [
    { label: "주식",    key: "pytrends_주식_monthly",    color: "#10b981" },
    { label: "금리",    key: "pytrends_금리_monthly",    color: "#ef4444" },
    { label: "환율",    key: "pytrends_환율_monthly",    color: "#3b82f6" },
    { label: "경기침체", key: "pytrends_경기침체_monthly", color: "#6b7280" },
    { label: "미국주식", key: "pytrends_미국주식_monthly", color: "#f59e0b" },
  ];

  monthlyGroups.forEach(({ label, key, color }) => {
    const data = sentiment[key];
    if (!Array.isArray(data) || !data.length) return;
    const ctx = createChartCanvas("macro-industry-trends-monthly-charts", `${label} 검색 트렌드 (월별 5년)`);
    if (!ctx) return;
    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.map(r => r.date?.slice(0,7)),
        datasets: [{ label, data: data.map(r => parseFloat(r.trend_score)||0),
          borderColor: color, backgroundColor: color + "20",
          borderWidth: 2, fill: true, tension: 0.4, pointRadius: 1 }]
      },
      options: { responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{labels:{color:"#d1d5db"}} },
        scales:{ x:{ticks:{maxTicksLimit:10,color:"#6b7280"}}, y:{min:0,max:100,ticks:{color:"#6b7280"}} } }
    });
    chartInstances.push(chart);
  });
}
window.renderIndustryCharts = renderIndustryCharts;

function renderRegimeCard() {
  const el = document.getElementById("regime-card");
  if (!el) return;
  const factors = window.QUANT_DATA?.sentiment?.factors;
  if (!factors) return;
  const regimeData = factors.market_macro_regime_month;
  if (!Array.isArray(regimeData) || !regimeData.length) return;

  const latest = regimeData[regimeData.length - 1];
  const regime = latest.market_regime || "unknown";
  const regimeColor = { risk_on: "#10b981", neutral: "#f59e0b", risk_off: "#ef4444" }[regime] || "#6b7280";
  const regimeKor = { risk_on: "리스크 온", neutral: "중립", risk_off: "리스크 오프" }[regime] || regime;

  const flags = [
    { key: "risk_on_flag",          label: "Risk On",     trueColor: "#10b981" },
    { key: "risk_off_flag",         label: "Risk Off",    trueColor: "#ef4444" },
    { key: "dollar_pressure_flag",  label: "달러 강세",   trueColor: "#f59e0b" },
    { key: "growth_on_flag",        label: "성장 On",     trueColor: "#3b82f6" },
    { key: "export_recovery_flag",  label: "수출 회복",   trueColor: "#8b5cf6" },
  ];

  const flagHtml = flags.map(f => {
    const on = latest[f.key] === true || latest[f.key] === "True";
    const color = on ? f.trueColor : "#374151";
    const icon = on ? "●" : "○";
    return `<span style="margin-right:12px;font-size:0.85rem;color:${color}"><b>${icon}</b> ${f.label}</span>`;
  }).join("");

  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
      <div>
        <div style="font-size:0.75rem;color:var(--text-sub);margin-bottom:4px">현재 시장 레짐 (${latest.period?.slice(0,7)})</div>
        <div style="font-size:1.8rem;font-weight:800;color:${regimeColor}">${regimeKor.toUpperCase()}</div>
      </div>
      <div style="flex:1;min-width:200px">
        <div style="font-size:0.75rem;color:var(--text-sub);margin-bottom:6px">주요 신호</div>
        <div>${flagHtml}</div>
      </div>
      <div style="text-align:right;min-width:120px">
        <div style="font-size:0.75rem;color:var(--text-sub);margin-bottom:4px">Risk-Off 점수</div>
        <div style="font-size:1.4rem;font-weight:700;color:${regimeColor}">${Number(latest.risk_off_score || 0).toFixed(2)}</div>
      </div>
    </div>`;
}
window.renderRegimeCard = renderRegimeCard;

function renderScorecard() {
  const container = document.getElementById("scorecard-container");
  if (!container) return;

  const macro = window.QUANT_DATA?.macro || {};
  const dxy = latestValue(macro.DXY, "Close");
  const tnx = latestValue(macro.DGS10, "DGS10") ?? latestValue(macro.TNX, "Close");
  const dgs10 = latestValue(macro.DGS10, "DGS10");
  const dgs2 = latestValue(macro.DGS2, "DGS2");
  const hy = latestValue(macro.BAMLH0A0HYM2, "BAMLH0A0HYM2");
  const ig = latestValue(macro.BAMLC0A0CM, "BAMLC0A0CM");
  const unrate = latestValue(macro.UNRATE, "UNRATE");
  const usdKrw = latestValue(macro.USD_KRW, "Close");

  const calcYoy = (arr, key) => {
    if (!arr || arr.length < 13) return null;
    const latest = Number(arr[arr.length - 1][key]);
    const yearAgo = Number(arr[arr.length - 13][key]);
    return Number.isFinite(latest) && Number.isFinite(yearAgo) && yearAgo !== 0
      ? ((latest / yearAgo) - 1) * 100 : null;
  };

  const m2Yoy      = calcYoy(macro.M2SL, "M2SL");
  const cpiYoy     = calcYoy(macro.CPIAUCSL, "CPIAUCSL");
  const exportsYoy = calcYoy(macro.KOR_EXPORTS, "XTEXVA01KRM667S");

  const vix        = latestValue(macro.VIX, "Close");
  const stlfsi     = latestValue(macro.STLFSI4, "STLFSI4");
  const korCli     = latestValue(macro.KOR_CLI, "KORLOLITONOSTSAM");
  const umSent     = latestValue(macro.UMCSENT, "UMCSENT");

  const yieldSpread = dgs10 !== null && dgs2 !== null ? dgs10 - dgs2 : null;
  const signal = {
    dxy:     dxy === null ? null : dxy < 99 ? 1 : dxy < 102 ? 0 : -1,
    tnx:     tnx === null ? null : tnx < 4.2 ? 1 : tnx < 4.5 ? 0 : -1,
    spread:  yieldSpread === null ? null : yieldSpread > 0.5 ? 1 : yieldSpread > 0 ? 0 : -1,
    hy:      hy === null ? null : hy < 3.5 ? 1 : hy < 4.5 ? 0 : -1,
    ig:      ig === null ? null : ig < 1.2 ? 1 : ig < 1.8 ? 0 : -1,
    unrate:  unrate === null ? null : unrate < 4 ? 1 : unrate < 5 ? 0 : -1,
    m2:      m2Yoy === null ? null : m2Yoy > 3 ? 1 : m2Yoy > -1 ? 0 : -1,
    cpi:     cpiYoy === null ? null : cpiYoy < 2 ? 1 : cpiYoy < 3.5 ? 0 : -1,
    usdKrw:  usdKrw === null ? null : usdKrw < 1350 ? 1 : usdKrw < 1500 ? 0 : -1,
    exports: exportsYoy === null ? null : exportsYoy > 5 ? 1 : exportsYoy > -5 ? 0 : -1,
    vix:     vix === null ? null : vix < 20 ? 1 : vix < 30 ? 0 : -1,
    stlfsi:  stlfsi === null ? null : stlfsi < 0 ? 1 : stlfsi < 1 ? 0 : -1,
    korCli:  korCli === null ? null : korCli > 100.2 ? 1 : korCli > 99.5 ? 0 : -1,
    umSent:  umSent === null ? null : umSent > 80 ? 1 : umSent > 60 ? 0 : -1,
  };

  const pct = (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  const indicators = [
    { name: "달러 인덱스",            value: dxy,         fmt: (v) => v.toFixed(2),                         sig: signal.dxy,     criterion: "↑ <99  →  99~102  ↓ >102" },
    { name: "미국 10년물 금리",        value: tnx,         fmt: (v) => `${v.toFixed(2)}%`,                   sig: signal.tnx,     criterion: "↑ <4.2%  →  4.2~4.5%  ↓ >4.5%" },
    { name: "미국 장단기 금리차",      value: yieldSpread, fmt: (v) => `${v.toFixed(2)}%p`,                  sig: signal.spread,  criterion: "↑ >+0.5%p  →  0~0.5%p  ↓ 역전(<0)" },
    { name: "미국 하이일드 스프레드",  value: hy,          fmt: (v) => `${v.toFixed(2)}%p`,                  sig: signal.hy,      criterion: "↑ <3.5%p  →  3.5~4.5%p  ↓ >4.5%p" },
    { name: "미국 IG 회사채 스프레드", value: ig,          fmt: (v) => `${v.toFixed(2)}%p`,                  sig: signal.ig,      criterion: "↑ <1.2%p  →  1.2~1.8%p  ↓ >1.8%p" },
    { name: "미국 CPI YoY",           value: cpiYoy,      fmt: pct,                                          sig: signal.cpi,     criterion: "↑ <2%  →  2~3.5%  ↓ >3.5%" },
    { name: "미국 소비자심리지수",     value: umSent,      fmt: (v) => v.toFixed(1),                         sig: signal.umSent,  criterion: "↑ >80  →  60~80  ↓ <60" },
    { name: "미국 실업률",            value: unrate,      fmt: (v) => `${v.toFixed(1)}%`,                   sig: signal.unrate,  criterion: "↑ <4%  →  4~5%  ↓ >5%" },
    { name: "미국 M2 YoY",            value: m2Yoy,       fmt: pct,                                          sig: signal.m2,      criterion: "↑ >+3%  →  -1~+3%  ↓ <-1%" },
    { name: "원달러 환율",            value: usdKrw,      fmt: (v) => `₩${Math.round(v).toLocaleString()}`,  sig: signal.usdKrw,  criterion: "↑ <1,350  →  1,350~1,500  ↓ >1,500" },
    { name: "한국 수출 YoY",          value: exportsYoy,  fmt: pct,                                          sig: signal.exports, criterion: "↑ >+5%  →  -5~+5%  ↓ <-5%" },
    { name: "VIX 공포지수",           value: vix,         fmt: (v) => v.toFixed(2),                         sig: signal.vix,     criterion: "↑ <20(안정)  →  20~30  ↓ >30(공포)" },
    { name: "STLFSI 금융스트레스",    value: stlfsi,      fmt: (v) => v.toFixed(3),                         sig: signal.stlfsi,  criterion: "↑ <0(완화)  →  0~1  ↓ >1(스트레스)" },
    { name: "한국 CLI",               value: korCli,      fmt: (v) => v.toFixed(2),                         sig: signal.korCli,  criterion: "↑ >100.2  →  99.5~100.2  ↓ <99.5" },
  ];

  const valid = indicators.map((i) => i.sig).filter((s) => s !== null);
  const score = valid.reduce((sum, s) => sum + s, 0);
  const label = score >= 2 ? "RISK ON" : score <= -2 ? "RISK OFF" : "NEUTRAL";
  const color = score >= 2 ? "#10b981" : score <= -2 ? "#ef4444" : "#f59e0b";
  const sigLabel = (s) => s === 1 ? "Risk On" : s === -1 ? "Risk Off" : s === 0 ? "Neutral" : "No Data";

  const rows = indicators.map((ind) => `
    <tr>
      <td style="font-weight:600; color:var(--text-heading);">
        ${html(ind.name)}
        <div style="font-size:0.72rem; color:var(--text-sub); font-weight:400; margin-top:2px;">${html(ind.criterion)}</div>
      </td>
      <td style="font-weight:700; color:#d1d5db; text-align:right;">${ind.value !== null && !Number.isNaN(ind.value) ? html(ind.fmt(ind.value)) : "-"}</td>
      <td style="text-align:center; color:${ind.sig === 1 ? "#10b981" : ind.sig === -1 ? "#ef4444" : "#f59e0b"}; font-weight:700;">${sigLabel(ind.sig)}</td>
    </tr>
  `).join("");

  const macroFactors = window.QUANT_DATA?.macro_factors || {};
  const mfSummary = macroFactors.summary || {};
  const latestDaily = Array.isArray(macroFactors.quant_daily_latest) ? macroFactors.quant_daily_latest.slice(0, 8) : [];
  const latestMonthly = Array.isArray(macroFactors.quant_monthly_latest) ? macroFactors.quant_monthly_latest.slice(0, 6) : [];
  const latestSpread = Array.isArray(macroFactors.macro_spread_month) && macroFactors.macro_spread_month.length ? macroFactors.macro_spread_month[macroFactors.macro_spread_month.length - 1] : null;
  const factorRows = latestDaily.concat(latestMonthly).map((r) => {
    const v = Number(r.value);
    return `<tr><td>${html(r.factor || "")}</td><td>${html(r.date || "")}</td><td style="text-align:right;font-weight:700;">${Number.isFinite(v) ? v.toFixed(4) : html(r.value ?? "-")}</td></tr>`;
  }).join("");
  const spreadCards = latestSpread ? `
    <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:12px 0 18px;">
      <div class="data-card"><h3>Macro Risk</h3><div class="value">${Number(latestSpread.macro_risk_score || 0).toFixed(3)}</div><div class="desc">${html(latestSpread.period || "")}</div></div>
      <div class="data-card"><h3>VIX Regime</h3><div class="value">${html(latestSpread.vix_regime || "-")}</div><div class="desc">VIX ${Number(latestSpread.vix || 0).toFixed(2)}</div></div>
      <div class="data-card"><h3>HY Spread</h3><div class="value">${Number(latestSpread.hy_spread || 0).toFixed(2)}</div><div class="desc">Credit score ${Number(latestSpread.credit_score || 0).toFixed(3)}</div></div>
      <div class="data-card"><h3>KR 10Y-1Y</h3><div class="value">${Number(latestSpread.kor_spread_10y1y || 0).toFixed(3)}</div><div class="desc">Yield spread</div></div>
    </div>` : `<div style="color:var(--text-sub); margin:12px 0;">macro_spread_month payload가 없습니다.</div>`;

  container.innerHTML = `
    <div style="background:${color}1f; border:1px solid ${color}66; border-radius:12px; padding:24px; text-align:center; margin-bottom:24px;">
      <div style="font-size:0.85rem; color:${color}; font-weight:700; letter-spacing:2px; margin-bottom:8px;">종합 매크로 신호</div>
      <div style="font-size:1.8rem; font-weight:800; color:${color};">${label}</div>
      <div style="font-size:0.88rem; color:var(--text-sub); margin-top:8px;">
        긍정 ${valid.filter((s) => s === 1).length}개 · 중립 ${valid.filter((s) => s === 0).length}개 · 부정 ${valid.filter((s) => s === -1).length}개
      </div>
      <div style="font-size:0.78rem; color:var(--text-sub); margin-top:10px;">
        Macro factor latest: daily ${html(mfSummary.quant_daily_latest || "-")} · monthly ${html(mfSummary.quant_monthly_latest || "-")} · spread ${html(mfSummary.macro_spread_latest || "-")} · regime ${html(mfSummary.regime_latest || "-")}
      </div>
    </div>
    <h4 style="margin:0 0 8px; color:var(--text-heading);">매크로 팩터 패널 최신값</h4>
    ${spreadCards}
    <div class="table-responsive" style="margin-bottom:22px;">
      <table class="alerts-table">
        <thead><tr><th>팩터</th><th>최신일</th><th style="text-align:right;">값</th></tr></thead>
        <tbody>${factorRows || '<tr><td colspan="3" style="text-align:center; color:var(--text-sub); padding:18px;">매크로 팩터 최신값 payload가 없습니다.</td></tr>'}</tbody>
      </table>
    </div>
    <div class="table-responsive">
      <table class="alerts-table">
        <thead><tr><th style="width:240px;">지표 · 기준 (↑ On / → Neutral / ↓ Off)</th><th style="text-align:right;">현재값</th><th style="text-align:center;">신호</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p style="color:var(--text-sub); font-size:0.8rem; margin-top:16px; text-align:right;">
      * 마지막 수집 데이터 기준 참고용 지표이며 투자 권유가 아닙니다.
    </p>
  `;
}
window.renderScorecard = renderScorecard;


// ─────────────────────────────────────────────────────────────────────────────
// 팩터 심사표
// ─────────────────────────────────────────────────────────────────────────────
function fvFmtPct(x, p = 2) {
  const n = Number(x);
  return Number.isFinite(n) ? `${(n * 100).toFixed(p)}%` : "—";
}
function fvFmtNum(x, p = 3) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(p) : "—";
}
function fvFmtScore(x) {
  const n = Number(x);
  return Number.isFinite(n) ? (n * 100).toFixed(1) : "—";
}
function fvFmtFactorBase(row) {
  const raw = Number(row?.raw_value);
  if (!Number.isFinite(raw)) return "—";
  const pctScore = `${(raw * 100).toFixed(1)}점`;
  const ratio = `${raw.toFixed(2)}배`;
  const z = `${raw.toFixed(2)}σ`;
  const factor = String(row?.factor || "");
  const label = String(row?.label || "");
  if (factor === "momentum_score") return `모멘텀 ${pctScore}`;
  if (factor === "valuation_score") return `밸류 ${pctScore}`;
  if (factor === "flow_score") return `수급 ${pctScore}`;
  if (factor === "liquidity_score") return `유동성 ${pctScore}`;
  if (factor === "small_cap_score") return `소형주 ${pctScore}`;
  if (factor === "value_quality_score") return `품질 ${pctScore}`;
  if (factor === "pbr_roe_adjusted_score") return `ROE조정 ${pctScore}`;
  if (factor === "sector_relative_per") return `섹터 PER 대비 ${ratio}`;
  if (factor === "sector_relative_pbr") return `섹터 PBR 대비 ${ratio}`;
  if (factor === "sector_value_zscore") return `섹터 밸류 ${z}`;
  if (factor === "pbr_roe_residual_sector") return `PBR/ROE 잔차 ${z}`;
  if (factor.includes("percentile") || label.includes("백분위")) return `백분위 ${pctScore}`;
  return raw >= 0 && raw <= 1 ? pctScore : fvFmtNum(raw, 3);
}
function fvFmtFactorInterpretation(row) {
  const factor = String(row?.factor || "");
  const score = Number(row?.score);
  const raw = Number(row?.raw_value);
  const tier = Number.isFinite(score) ? (score >= 0.95 ? "최상위" : score >= 0.85 ? "상위" : score >= 0.65 ? "양호" : "중립") : "참고";
  if (factor === "momentum_score") return `${tier} 가격·거래량 추세`;
  if (factor === "valuation_score") return `${tier} 저평가 복합 신호`;
  if (factor === "flow_score") return `${tier} 수급 유입 신호`;
  if (factor === "liquidity_score") return `${tier} 거래 유동성`;
  if (factor === "small_cap_score") return `${tier} 소형주 성격`;
  if (factor === "value_quality_score") return `${tier} 가치+ROE 품질`;
  if (factor === "pbr_roe_adjusted_score") return `${tier} ROE 대비 PBR 매력`;
  if (factor === "sector_relative_per") return Number.isFinite(raw) && raw < 1 ? "섹터 중위 PER보다 낮음" : "섹터 PER 대비 확인 필요";
  if (factor === "sector_relative_pbr") return Number.isFinite(raw) && raw < 1 ? "섹터 중위 PBR보다 낮음" : "섹터 PBR 대비 확인 필요";
  if (factor === "sector_value_zscore") return Number.isFinite(raw) && raw < 0 ? "섹터 역사 대비 저평가" : "섹터 역사 대비 고평가권";
  if (factor === "pbr_roe_residual_sector") return Number.isFinite(raw) && raw < 0 ? "ROE 대비 PBR 낮음" : "ROE 대비 PBR 높음";
  return `${tier} 신호`;
}
function fvFmtInt(x) {
  const n = Number(x);
  return Number.isFinite(n) ? Math.round(n).toLocaleString() : "—";
}
function fvTable(rows, cols) {
  return `<table class="alerts-table"><thead><tr>${cols.map((c) => `<th>${html(c[1])}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td>${c[2](r[c[0]], r)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function fvCard(label, value, sub = "") {
  return `<div class="data-card" style="padding:14px;"><div style="color:var(--text-sub); font-size:0.78rem; font-weight:700;">${html(label)}</div><div style="font-size:1.5rem; font-weight:800; color:var(--text-heading); margin-top:4px;">${value}</div>${sub ? `<div style="color:var(--text-sub); font-size:0.78rem; margin-top:4px;">${sub}</div>` : ""}</div>`;
}

function fmNum(v) {
  const n = Number(String(v ?? "").replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}
function fmPct(v) {
  const n = fmNum(v);
  return n === null ? "—" : `${(n * 100).toFixed(1)}%`;
}
function fmScore(v) {
  const n = fmNum(v);
  return n === null ? "—" : (n * 100).toFixed(1);
}
function fmTicker(v) {
  return String(v ?? "").replace(/\.0$/, "").padStart(6, "0");
}
function fmWhy(row) {
  const parts = [];
  const scoreMap = [
    ["value_score", "밸류"], ["quality_score", "퀄리티"], ["momentum_score", "모멘텀"],
    ["flow_score", "수급"], ["sentiment_score", "심리"], ["macro_regime_score", "매크로"],
  ];
  scoreMap.forEach(([key, label]) => {
    const n = fmNum(row[key]);
    if (n !== null && n >= 0.65) parts.push(`${label} 우수(${(n * 100).toFixed(0)}점)`);
  });
  if (fmNum(row.stale_factor_flag) > 0) parts.push("일부 스냅샷 노후");
  if (!parts.length) parts.push("종합 점수와 커버리지 기준 후보");
  return parts.slice(0, 4).join(" · ");
}
function renderFactorMaster() {
  const payload = window.QUANT_DATA?.factor_master || {};
  const rowsAll = Array.isArray(payload.latest_rows) ? payload.latest_rows : [];
  const summary = payload.summary || {};
  const cards = document.getElementById("factor-master-cards");
  const table = document.getElementById("factor-master-table");
  const healthEl = document.getElementById("factor-master-health-table");
  const sourceEl = document.getElementById("factor-master-source-table");
  const qualityEl = document.getElementById("factor-master-quality-table");
  if (!cards || !table) return;
  const asOf = document.getElementById("factor-master-as-of");
  if (asOf) asOf.textContent = payload.as_of ? `최신월: ${payload.as_of}` : "팩터 마스터 데이터 없음";
  if (!rowsAll.length) {
    cards.innerHTML = fvCard("상태", "데이터 없음", "window.QUANT_DATA.factor_master payload를 확인하세요.");
    table.innerHTML = "<p style='color:var(--text-sub);'>factor_master 데이터가 없습니다.</p>";
    return;
  }
  const q = (document.getElementById("factor-master-search")?.value || "").toLowerCase().trim();
  const sortKey = document.getElementById("factor-master-sort")?.value || "composite_score";
  const limit = Number(document.getElementById("factor-master-limit")?.value || 30);
  const filtered = rowsAll.filter((r) => {
    const hay = [fmTicker(r.ticker), r.name, r.market, r.sector, r.size_bucket].map((x) => String(x ?? "")).join(" ").toLowerCase();
    return !q || hay.includes(q);
  }).sort((a, b) => (fmNum(b[sortKey]) ?? -Infinity) - (fmNum(a[sortKey]) ?? -Infinity)).slice(0, limit);
  const top = rowsAll.slice().sort((a, b) => (fmNum(b.composite_score) ?? -Infinity) - (fmNum(a.composite_score) ?? -Infinity))[0] || {};
  cards.innerHTML = [
    fvCard("최신월", html(payload.as_of || summary.latest_period || "—"), `${fvFmtInt(summary.latest_row_count || rowsAll.length)}종목`),
    fvCard("전체 패널", fvFmtInt(summary.row_count), `${fvFmtInt(summary.ticker_count)}종목 · ${fvFmtInt(summary.period_count)}개월`),
    fvCard("평균 신뢰도", fmPct(summary.avg_confidence_score), `평균 커버리지 ${fvFmtNum(summary.avg_coverage_count, 1)}개`),
    fvCard("품질 페널티", fmPct(summary.avg_data_quality_penalty), `사용가능 ${fvFmtInt(summary.usable_for_trading_count)}종목`),
    fvCard("Source Failure", fvFmtInt(summary.source_failure_rows), `노후 ${fvFmtInt(summary.stale_factor_rows)}종목`),
    fvCard("1위 종목", `${html(top.name || fmTicker(top.ticker))}`, `종합 ${fmScore(top.composite_score)}점 · ${html(fmTicker(top.ticker))}`),
  ].join("");
  table.innerHTML = fvTable(filtered, [
    ["ticker", "코드", (v) => html(fmTicker(v))],
    ["name", "종목명", (v, r) => html(v || fmTicker(r.ticker))],
    ["sector", "섹터", (v) => html(v || "—")],
    ["composite_score", "종합", fmScore],
    ["value_score", "밸류", fmScore],
    ["quality_score", "퀄리티", fmScore],
    ["momentum_score", "모멘텀", fmScore],
    ["flow_score", "수급", fmScore],
    ["sentiment_score", "심리", fmScore],
    ["coverage_count", "커버", fvFmtInt],
    ["confidence_score", "신뢰도", fmScore],
    ["data_quality_penalty", "품질페널티", fmScore],
    ["stale_factor_flag", "노후", (v) => fmNum(v) > 0 ? "⚠️" : "OK"],
    ["_why", "왜 후보인가", (_v, r) => html(fmWhy(r))],
  ]);
  const health = Array.isArray(payload.health) ? payload.health : [];
  if (healthEl) {
    healthEl.innerHTML = health.length ? fvTable(health, [
      ["factor_name", "팩터", (v) => html(v)],
      ["coverage_mean", "평균커버", fvFmtPct],
      ["top_bottom_spread_mean", "상하위스프레드", fvFmtPct],
      ["rank_ic_mean", "Rank IC", fvFmtNum],
      ["recent_3m_spread", "최근3M", fvFmtPct],
      ["recent_effectiveness_score", "유효성", fmScore],
      ["health_bucket", "상태", (v) => html(v)],
    ]) : "<p style='color:var(--text-sub);'>헬스 리포트 데이터 없음</p>";
  }
  const sources = Array.isArray(payload.source_staleness) ? payload.source_staleness : [];
  if (sourceEl) {
    sourceEl.innerHTML = sources.length ? fvTable(sources, [
      ["source_name", "소스", (v) => html(v)],
      ["latest_date", "최신일자", (v) => html(v || "—")],
      ["age_days", "지연일", fvFmtInt],
      ["allowed_lag_days", "허용", fvFmtInt],
      ["row_count", "rows", fvFmtInt],
      ["ticker_count", "tickers", fvFmtInt],
      ["source_quality_score", "신뢰도", fmScore],
      ["source_failure_flag", "Failure", (v) => fmNum(v) > 0 ? "⚠️" : "OK"],
      ["guidance", "조치/해석", (v) => html(v)],
    ]) : "<p style='color:var(--text-sub);'>소스별 스테일니스 데이터 없음</p>";
  }
  const qualityRows = Array.isArray(payload.quality_latest) ? payload.quality_latest : [];
  if (qualityEl) {
    const worst = qualityRows.slice()
      .sort((a, b) => (fmNum(b.data_quality_penalty) ?? -Infinity) - (fmNum(a.data_quality_penalty) ?? -Infinity))
      .slice(0, 30);
    qualityEl.innerHTML = worst.length ? fvTable(worst, [
      ["ticker", "코드", (v) => html(fmTicker(v))],
      ["factor_coverage_score", "커버리지", fmScore],
      ["data_freshness_score", "신선도", fmScore],
      ["data_quality_penalty", "페널티", fmScore],
      ["ticker_missing_rate", "결측률", fmScore],
      ["stale_factor_count", "노후수", fvFmtInt],
      ["source_failure_count", "Failure수", fvFmtInt],
      ["usable_for_trading_flag", "거래사용", (v) => fmNum(v) > 0 ? "OK" : "금지/축소"],
      ["minute_usable_for_trading_flag", "분봉", (v) => fmNum(v) > 0 ? "OK" : "당일없음"],
    ]) : "<p style='color:var(--text-sub);'>종목별 품질 데이터 없음</p>";
  }
}


function renderDataQualityDashboard() {
  const payload = window.QUANT_DATA?.factor_master || {};
  const summary = payload.summary || {};
  const cards = document.getElementById("data-quality-cards");
  const sourceEl = document.getElementById("data-quality-source-table");
  const stockEl = document.getElementById("data-quality-stock-table");
  const asOf = document.getElementById("data-quality-as-of");
  if (asOf) asOf.textContent = payload.as_of ? `최신월: ${payload.as_of}` : "데이터 없음";
  if (!cards || !sourceEl || !stockEl) return;

  const sources = Array.isArray(payload.source_staleness) ? payload.source_staleness : [];
  const qualityRows = Array.isArray(payload.quality_latest) ? payload.quality_latest : [];
  if (!sources.length && !qualityRows.length) {
    cards.innerHTML = fvCard("상태", "데이터 없음", "factor_master.source_staleness / quality_latest payload를 확인하세요.");
    sourceEl.innerHTML = "<p style='color:var(--text-sub);'>소스별 데이터 없음</p>";
    stockEl.innerHTML = "<p style='color:var(--text-sub);'>종목별 품질 데이터 없음</p>";
    return;
  }

  const sourceFailures = sources.filter((r) => fmNum(r.source_failure_flag) > 0).length;
  const staleSources = sources.filter((r) => fmNum(r.latest_date_stale_flag) > 0).length;
  cards.innerHTML = [
    fvCard("최신월", html(payload.as_of || summary.latest_period || "—"), `${fvFmtInt(summary.latest_row_count)}종목`),
    fvCard("평균 신뢰도", fmPct(summary.avg_confidence_score), `사용가능 ${fvFmtInt(summary.usable_for_trading_count)}종목`),
    fvCard("품질 페널티", fmPct(summary.avg_data_quality_penalty), "종합점수에 반영"),
    fvCard("Source Failure", fvFmtInt(sourceFailures), `노후 소스 ${fvFmtInt(staleSources)}개`),
    fvCard("노후 종목", fvFmtInt(summary.stale_factor_rows), `failure row ${fvFmtInt(summary.source_failure_rows)}`),
  ].join("");

  sourceEl.innerHTML = sources.length ? fvTable(sources, [
    ["source_name", "소스", (v) => html(v)],
    ["latest_date", "최신일자", (v) => html(v || "—")],
    ["age_days", "지연일", fvFmtInt],
    ["allowed_lag_days", "허용", fvFmtInt],
    ["row_count", "rows", fvFmtInt],
    ["ticker_count", "tickers", fvFmtInt],
    ["source_quality_score", "신뢰도", fmScore],
    ["latest_date_stale_flag", "Stale", (v) => fmNum(v) > 0 ? "⚠️" : "OK"],
    ["source_failure_flag", "Failure", (v) => fmNum(v) > 0 ? "⚠️" : "OK"],
    ["guidance", "조치/해석", (v) => html(v)],
  ]) : "<p style='color:var(--text-sub);'>소스별 스테일니스 데이터 없음</p>";

  const worst = qualityRows.slice()
    .sort((a, b) => (fmNum(b.data_quality_penalty) ?? -Infinity) - (fmNum(a.data_quality_penalty) ?? -Infinity))
    .slice(0, 50);
  stockEl.innerHTML = worst.length ? fvTable(worst, [
    ["ticker", "코드", (v) => html(fmTicker(v))],
    ["factor_coverage_score", "커버리지", fmScore],
    ["data_freshness_score", "신선도", fmScore],
    ["data_quality_penalty", "페널티", fmScore],
    ["ticker_missing_rate", "결측률", fmScore],
    ["stale_factor_count", "노후수", fvFmtInt],
    ["source_failure_count", "Failure수", fvFmtInt],
    ["usable_for_trading_flag", "거래사용", (v) => fmNum(v) > 0 ? "OK" : "금지/축소"],
    ["minute_usable_for_trading_flag", "분봉", (v) => fmNum(v) > 0 ? "OK" : "당일없음"],
    ["news_age_days", "뉴스지연", fvFmtInt],
    ["minute_age_days", "분봉지연", fvFmtInt],
    ["target_age_days", "목표가지연", fvFmtInt],
  ]) : "<p style='color:var(--text-sub);'>종목별 품질 데이터 없음</p>";
}

function renderFactorValidation() {
  const payload = window.QUANT_DATA?.factor_validation || {};
  const summary = Array.isArray(payload.summary) ? payload.summary : [];
  const current = Array.isArray(payload.current_top) ? payload.current_top : [];
  const cards = document.getElementById("factor-validation-cards");
  if (!cards) return;
  const asOf = document.getElementById("factor-validation-as-of");
  if (asOf) asOf.textContent = payload.as_of ? `검증 기준: ${payload.as_of}` : "검증 데이터 없음";
  if (!summary.length) {
    cards.innerHTML = fvCard("상태", "데이터 없음", "factor_validation payload를 확인하세요.");
    return;
  }
  const base = summary.filter((r) => r.horizon === "1m" && Number(r.topn) === 30)
    .sort((a, b) => Number(b.avg_excess ?? -999) - Number(a.avg_excess ?? -999));
  const best = base[0] || {};
  const factorCount = new Set(summary.map((r) => r.factor)).size;
  const hitBest = base.reduce((m, r) => Math.max(m, Number(r.hit_rate || 0)), 0);
  cards.innerHTML = [
    fvCard("검증 팩터", fvFmtInt(factorCount), `요약 행 ${summary.length.toLocaleString()}개`),
    fvCard("최고 1M Top30 초과", `<span style="color:${Number(best.avg_excess) >= 0 ? '#10b981' : '#ef4444'}">${fvFmtPct(best.avg_excess)}</span>`, html(best.label || "")),
    fvCard("최고 Hit Rate", fvFmtPct(hitBest), "1M Top30 기준"),
    fvCard("현재 Top 종목", fvFmtInt(current.length), "팩터별 Top30 후보"),
  ].join("");
  const summaryEl = document.getElementById("factor-validation-summary-table");
  if (summaryEl) summaryEl.innerHTML = fvTable(base.slice(0, 15), [
    ["label", "팩터", (v) => html(v)],
    ["months", "개월", fvFmtInt],
    ["avg_return", "평균수익", fvFmtPct],
    ["avg_benchmark", "벤치", fvFmtPct],
    ["avg_excess", "초과", fvFmtPct],
    ["hit_rate", "승률", fvFmtPct],
    ["ic_mean", "IC", fvFmtNum],
    ["coverage_latest", "최신커버", fvFmtInt],
  ]);
  const factorSel = document.getElementById("factor-validation-factor");
  if (factorSel && !factorSel.dataset.loaded) {
    const labels = [...new Set(current.map((r) => r.label).filter(Boolean))];
    factorSel.innerHTML = [`<option value="">전체 팩터</option>`]
      .concat(labels.map((label) => `<option value="${html(label)}">${html(label)}</option>`))
      .join("");
    factorSel.dataset.loaded = "1";
  }
  renderFactorValidationTopn();
  renderFactorTopnQuintile();
  renderFactorValidationCurrent();
  renderFactorValidationCorr();
  renderFactorValidationCoverage();
  renderFactorIcDecay();
}
function renderFactorValidationTopn() {
  const payload = window.QUANT_DATA?.factor_validation || {};
  const summary = Array.isArray(payload.summary) ? payload.summary : [];
  const h = document.getElementById("factor-validation-horizon")?.value || "1m";
  const n = Number(document.getElementById("factor-validation-topn")?.value || 30);
  const rows = summary.filter((r) => r.horizon === h && Number(r.topn) === n)
    .sort((a, b) => Number(b.avg_excess ?? -999) - Number(a.avg_excess ?? -999));
  const el = document.getElementById("factor-validation-topn-table");
  if (el) el.innerHTML = fvTable(rows, [
    ["label", "팩터", (v) => html(v)],
    ["months", "개월", fvFmtInt],
    ["avg_return", "평균수익", fvFmtPct],
    ["avg_benchmark", "벤치", fvFmtPct],
    ["avg_excess", "초과", fvFmtPct],
    ["hit_rate", "승률", fvFmtPct],
    ["max_drawdown", "MDD", fvFmtPct],
    ["avg_turnover", "회전율", fvFmtPct],
  ]);
}
function fvScoreLabel(score) {
  const map = {
    valuation: "밸류에이션",
    momentum: "가격 모멘텀",
    investor_flow: "수급 모멘텀",
    reversal_setup: "반전 셋업",
    roe_quality: "ROE 품질",
    sector_pbr_cheap: "섹터 PBR 저평가",
    value_quality: "가치+품질",
    financial_quality: "재무 품질",
    balance_sheet_quality: "BS 품질",
    cash_flow_quality: "현금흐름 품질",
    earnings_stability: "이익 안정성",
  };
  return map[score] || score || "—";
}
function renderFactorTopnQuintile() {
  const payload = window.QUANT_DATA?.factor_validation?.topn_quintile || {};
  const topn = Array.isArray(payload.topn_summary) ? payload.topn_summary : [];
  const spread = Array.isArray(payload.quintile_spread) ? payload.quintile_spread : [];
  const h = Number(document.getElementById("factor-topnq-horizon")?.value || 1);
  const n = Number(document.getElementById("factor-topnq-topn")?.value || 30);
  const asOf = document.getElementById("factor-topnq-as-of");
  if (asOf) asOf.textContent = payload.as_of ? `최신 스냅샷: ${payload.as_of}` : "TopN/분위수 데이터 없음";

  const topRows = topn
    .filter((r) => Number(r.horizon_m) === h && Number(r.top_n) === n)
    .sort((a, b) => Number(b.avg_excess_ret ?? -999) - Number(a.avg_excess_ret ?? -999));
  const topEl = document.getElementById("factor-topnq-topn-table");
  if (topEl) {
    topEl.innerHTML = topRows.length ? fvTable(topRows.slice(0, 12), [
      ["score", "팩터", (v) => html(fvScoreLabel(v))],
      ["months", "개월", fvFmtInt],
      ["avg_portfolio_ret", "TopN", fvFmtPct],
      ["avg_benchmark_ret", "벤치", fvFmtPct],
      ["avg_excess_ret", "초과", fvFmtPct],
      ["hit_rate", "승률", fvFmtPct],
      ["max_drawdown_path", "MDD", fvFmtPct],
    ]) : "<p style='color:var(--text-sub);'>TopN 백테스트 데이터 없음</p>";
  }

  const spreadRows = spread
    .filter((r) => Number(r.horizon_m) === h)
    .sort((a, b) => Number(b.q1_minus_q5_avg_ret ?? -999) - Number(a.q1_minus_q5_avg_ret ?? -999));
  const spreadEl = document.getElementById("factor-topnq-spread-table");
  if (spreadEl) {
    spreadEl.innerHTML = spreadRows.length ? fvTable(spreadRows.slice(0, 12), [
      ["score", "팩터", (v) => html(fvScoreLabel(v))],
      ["months", "개월", fvFmtInt],
      ["q1_minus_q5_avg_ret", "Q1-Q5", fvFmtPct],
      ["q1_avg_ret", "Q1", fvFmtPct],
      ["q5_avg_ret", "Q5", fvFmtPct],
      ["q1_excess", "Q1초과", fvFmtPct],
    ]) : "<p style='color:var(--text-sub);'>분위수 스프레드 데이터 없음</p>";
  }
}
function renderFactorValidationCurrent() {
  const payload = window.QUANT_DATA?.factor_validation || {};
  const current = Array.isArray(payload.current_top) ? payload.current_top : [];
  const label = document.getElementById("factor-validation-factor")?.value || "";
  const q = (document.getElementById("factor-validation-search")?.value || "").toLowerCase().trim();
  const sortKey = document.getElementById("factor-validation-current-sort-key")?.value || "rank";
  const sortOrder = document.getElementById("factor-validation-current-sort-order")?.value || "desc";
  const normTicker = (v) => String(v ?? "").replace(/\.0$/, "").padStart(6, "0");
  const rows = current
    .filter((r) => {
      const ticker = normTicker(r.ticker);
      const haystack = [
        ticker,
        String(r.ticker ?? ""),
        String(r.name ?? ""),
        String(r.label ?? ""),
        String(r.factor ?? ""),
        String(r.sector ?? ""),
      ].join(" ").toLowerCase();
      return (!label || r.label === label) && (!q || haystack.includes(q));
    })
    .sort((a, b) => {
      const av = Number(a[sortKey]);
      const bv = Number(b[sortKey]);
      let cmp;
      if (Number.isFinite(av) && Number.isFinite(bv)) cmp = av - bv;
      else cmp = String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? ""), "ko");
      return sortOrder === "desc" ? -cmp : cmp;
    })
    .slice(0, 30);
  const el = document.getElementById("factor-validation-current-table");
  if (el) el.innerHTML = fvTable(rows, [
    ["rank", "순위", fvFmtInt],
    ["ticker", "코드", (v) => html(normTicker(v))],
    ["name", "종목명", (v) => html(v || "")],
    ["sector", "섹터", (v) => html(v || "")],
    ["score", "표준점수", fvFmtScore],
    ["raw_value", "기준값", (v, r) => html(fvFmtFactorBase(r))],
    ["factor_note", "해석", (v, r) => html(fvFmtFactorInterpretation(r))],
  ]);
}
function renderFactorValidationCorr() {
  const corr = window.QUANT_DATA?.factor_validation?.correlation || {};
  const keys = Object.keys(corr).slice(0, 15);
  const el = document.getElementById("factor-validation-corr-table");
  if (!el) return;
  if (!keys.length) { el.innerHTML = "<p style='color:var(--text-sub);'>상관관계 데이터 없음</p>"; return; }
  let out = `<table class="alerts-table"><thead><tr><th>팩터</th>${keys.map((k) => `<th>${html(k)}</th>`).join("")}</tr></thead><tbody>`;
  keys.forEach((r) => {
    out += `<tr><th>${html(r)}</th>`;
    keys.forEach((c) => {
      const v = Number(corr[r]?.[c]);
      const hue = Number.isFinite(v) && v >= 0 ? 145 : 0;
      const alpha = Number.isFinite(v) ? Math.min(Math.abs(v), 1) * 0.65 : 0;
      out += `<td><span style="display:inline-block; min-width:48px; padding:3px 6px; border-radius:4px; background:hsla(${hue},70%,35%,${alpha});">${fvFmtNum(v, 2)}</span></td>`;
    });
    out += "</tr>";
  });
  el.innerHTML = out + "</tbody></table>";
}
function renderFactorValidationCoverage() {
  const coverage = window.QUANT_DATA?.factor_validation?.coverage || [];
  const rows = coverage.slice(-12).reverse();
  const el = document.getElementById("factor-validation-coverage-table");
  if (!el) return;
  if (!rows.length) { el.innerHTML = "<p style='color:var(--text-sub);'>커버리지 데이터 없음</p>"; return; }
  const preferred = ["period", "universe", "fwd_1m_available", "valuation_score", "momentum_score", "roe_sector_pct_ts", "sector_relative_per", "sector_relative_pbr", "value_quality_score", "sector_value_zscore", "small_cap_score"];
  const cols = preferred.filter((k) => k in rows[0]).map((k) => [k, k, (v) => k === "period" ? html(v) : fvFmtInt(v)]);
  el.innerHTML = fvTable(rows, cols);
}
function pbLabelUniverse(v) {
  const map = {
    A_KOSPI200_PROXY: "A KOSPI200 proxy",
    B_PROJECT_DEFAULT: "B 기본(350 proxy)",
    C_SCREENABLE: "C 전체 스크리닝",
    D_LARGE: "D 대형",
    D_MID: "D 중형",
    D_SMALL: "D 소형",
  };
  return map[v] || v || "—";
}
function pbEnsureOptions(selectId, values, labelFn, preferred) {
  const el = document.getElementById(selectId);
  if (!el) return "";
  const current = el.value || preferred || values[0] || "";
  const next = values.includes(current) ? current : (values.includes(preferred) ? preferred : values[0] || "");
  el.innerHTML = values.map((v) => `<option value="${html(v)}">${html(labelFn(v))}</option>`).join("");
  el.value = next;
  return next;
}
function pbSummaryRows() {
  return Array.isArray(window.QUANT_DATA?.practical_topn_backtest?.summary) ? window.QUANT_DATA.practical_topn_backtest.summary : [];
}
function pbMonthlyRows() {
  return Array.isArray(window.QUANT_DATA?.practical_topn_backtest?.monthly) ? window.QUANT_DATA.practical_topn_backtest.monthly : [];
}
function pbSelectionRows() {
  return Array.isArray(window.QUANT_DATA?.practical_topn_backtest?.latest_selections) ? window.QUANT_DATA.practical_topn_backtest.latest_selections : [];
}
function renderPracticalBacktest() {
  const payload = window.QUANT_DATA?.practical_topn_backtest || {};
  const summary = pbSummaryRows();
  const monthly = pbMonthlyRows();
  const asOf = document.getElementById("practical-backtest-as-of");
  if (asOf) asOf.textContent = payload.as_of ? `검증 기준: ${payload.as_of}` : "백테스트 데이터 없음";
  const cards = document.getElementById("practical-backtest-cards");
  if (!cards) return;
  if (!summary.length) {
    cards.innerHTML = fvCard("상태", "데이터 없음", "practical_topn_backtest payload를 확인하세요.");
    return;
  }
  const universes = [...new Set(summary.map((r) => r.universe).filter(Boolean))];
  const scenarios = [...new Set(summary.map((r) => r.scenario).filter(Boolean))];
  const universe = pbEnsureOptions("practical-backtest-universe", universes, pbLabelUniverse, "B_PROJECT_DEFAULT");
  const scenario = pbEnsureOptions("practical-backtest-scenario", scenarios, (v) => (summary.find((r) => r.scenario === v)?.scenario_label || v), "market_attractiveness_score");
  const topn = Number(document.getElementById("practical-backtest-topn")?.value || 30);
  const cost = Number(document.getElementById("practical-backtest-cost")?.value || 0.003);
  const row = summary.find((r) => r.universe === universe && r.scenario === scenario && Number(r.topn) === topn && Math.abs(Number(r.cost_rate) - cost) < 0.000001) || {};
  const pos = Number(row.total_return) >= 0;
  cards.innerHTML = [
    fvCard("누적수익률", `<span style="color:${pos ? '#10b981' : '#ef4444'}">${fvFmtPct(row.total_return)}</span>`, `벤치 ${fvFmtPct(row.benchmark_total_return)}`),
    fvCard("초과수익률", `<span style="color:${Number(row.excess_total_return) >= 0 ? '#10b981' : '#ef4444'}">${fvFmtPct(row.excess_total_return)}</span>`, `${fvFmtInt(row.months)}개월 / ${html(row.start_period || '')}~${html(row.end_period || '')}`),
    fvCard("MDD", `<span style="color:#ef4444">${fvFmtPct(row.mdd)}</span>`, `벤치 MDD ${fvFmtPct(row.benchmark_mdd)}`),
    fvCard("월간 승률", fvFmtPct(row.monthly_win_rate), `Hit ${fvFmtPct(row.hit_ratio)} · 회전율 ${fvFmtPct(row.avg_turnover)}`),
  ].join("");
  renderPracticalBacktestChart(universe, scenario, topn, cost);
  renderPracticalBacktestSummary(universe, cost);
  renderPracticalBacktestSelections(universe, scenario, topn, cost);
}
function renderPracticalBacktestChart(universe, scenario, topn, cost) {
  const canvas = document.getElementById("practical-backtest-nav-chart");
  if (!canvas || typeof Chart === "undefined") return;
  const rows = pbMonthlyRows()
    .filter((r) => r.universe === universe && r.scenario === scenario && Number(r.topn) === topn && Math.abs(Number(r.cost_rate) - cost) < 0.000001)
    .sort((a, b) => String(a.period).localeCompare(String(b.period)));
  if (window.practicalBacktestChart) {
    try { window.practicalBacktestChart.destroy(); } catch (_) {}
  }
  window.practicalBacktestChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels: rows.map((r) => r.period),
      datasets: [
        { label: "TopN NAV", data: rows.map((r) => Number(r.nav)), borderColor: "#10b981", backgroundColor: "rgba(16,185,129,0.12)", tension: 0.25, pointRadius: 1.5 },
        { label: "Benchmark NAV", data: rows.map((r) => Number(r.benchmark_nav)), borderColor: "#94a3b8", backgroundColor: "rgba(148,163,184,0.10)", tension: 0.25, pointRadius: 1.5 },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#cbd5e1" } } }, scales: { x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.15)" } }, y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.15)" } } } },
  });
}
function renderPracticalBacktestSummary(universe, cost) {
  const el = document.getElementById("practical-backtest-summary-table");
  if (!el) return;
  const rows = pbSummaryRows()
    .filter((r) => r.universe === universe && Math.abs(Number(r.cost_rate) - cost) < 0.000001)
    .sort((a, b) => Number(b.excess_total_return ?? -999) - Number(a.excess_total_return ?? -999));
  el.innerHTML = rows.length ? fvTable(rows, [
    ["scenario_label", "시나리오", (v) => html(v)],
    ["topn", "TopN", fvFmtInt],
    ["months", "개월", fvFmtInt],
    ["total_return", "누적", fvFmtPct],
    ["benchmark_total_return", "벤치", fvFmtPct],
    ["excess_total_return", "초과", fvFmtPct],
    ["cagr", "CAGR", fvFmtPct],
    ["mdd", "MDD", fvFmtPct],
    ["monthly_win_rate", "승률", fvFmtPct],
    ["avg_turnover", "회전율", fvFmtPct],
  ]) : "<p style='color:var(--text-sub);'>성과표 데이터 없음</p>";
}
function renderPracticalBacktestSelections(universe, scenario, topn, cost) {
  const el = document.getElementById("practical-backtest-selection-table");
  if (!el) return;
  const rows = pbSelectionRows()
    .filter((r) => r.universe === universe && r.scenario === scenario && Number(r.topn) === topn && Math.abs(Number(r.cost_rate) - cost) < 0.000001)
    .sort((a, b) => Number(a.rank) - Number(b.rank))
    .slice(0, topn);
  el.innerHTML = rows.length ? fvTable(rows, [
    ["rank", "순위", fvFmtInt],
    ["name", "종목명", (v, r) => {
      const code = String(r.ticker ?? "").replace(/\.0$/, "").padStart(6, "0");
      return `${html(v || "")}<br><small style="color:var(--text-sub);font-size:0.72em;letter-spacing:0.02em">${code}</small>`;
    }],
    ["sector", "섹터", (v, r) => {
      if (!v || v === (r.name || "")) return "—";
      return html(v);
    }],
    ["score", "점수", fvFmtScore],
    ["fwd_1m_ret", "다음월", fvFmtPct],
    ["market_cap", "시총", (v) => fvFmtInt(Number(v) / 100000000)],
  ]) : "<p style='color:var(--text-sub);'>최근 리밸런싱 종목 데이터 없음</p>";
}
window.renderPracticalBacktest = renderPracticalBacktest;
window.renderFactorMaster = renderFactorMaster;
window.renderDataQualityDashboard = renderDataQualityDashboard;
window.renderFactorValidation = renderFactorValidation;
window.renderFactorValidationTopn = renderFactorValidationTopn;
window.renderFactorTopnQuintile = renderFactorTopnQuintile;
window.renderFactorValidationCurrent = renderFactorValidationCurrent;

// ── 팩터 IC 붕괴 경보 ──────────────────────────────────────────────────────
function renderFactorIcDecay() {
  const el = document.getElementById("factor-ic-decay-table");
  if (!el) return;
  const rows = Array.isArray(window.QUANT_DATA?.factor_master?.ic_summary)
    ? window.QUANT_DATA.factor_master.ic_summary
    : [];
  if (!rows.length) {
    el.innerHTML = "<p style='color:var(--text-sub); font-size:0.82rem;'>IC 데이터 없음 — build_factor_ic_report.py를 먼저 실행하세요.</p>";
    return;
  }
  const BUCKET_COLOR = { effective: "#10b981", neutral: "#94a3b8", weak: "#f59e0b", decay: "#ef4444", insufficient: "#6b7280" };
  const BUCKET_LABEL = { effective: "유효", neutral: "보통", weak: "약함", decay: "붕괴", insufficient: "데이터부족" };
  const sorted = [...rows].sort((a, b) => {
    if (Number(b.decay_warning) !== Number(a.decay_warning)) return Number(b.decay_warning) - Number(a.decay_warning);
    return Number(b.effectiveness_score ?? -1) - Number(a.effectiveness_score ?? -1);
  });
  const fmtIc = (v) => v == null || v === "" ? "N/A" : Number(v).toFixed(3);
  const fmtPct = (v) => v == null || v === "" ? "N/A" : (Number(v) * 100).toFixed(1) + "%";
  const fmtNum = (v, d = 2) => v == null || v === "" ? "N/A" : Number(v).toFixed(d);
  const rows_html = sorted.map((r) => {
    const bucket = r.health_bucket || "insufficient";
    const color = BUCKET_COLOR[bucket] || "#6b7280";
    const warn = Number(r.decay_warning) === 1;
    return `<tr style="background:${warn ? "rgba(239,68,68,0.06)" : ""};">
      <td style="font-weight:600; color:var(--text-heading);">${html(r.factor_label || r.factor_name || "")}</td>
      <td style="font-family:monospace;">${fmtIc(r.ic_mean_all)}</td>
      <td style="font-family:monospace;">${fmtIc(r.ic_mean_12m)}</td>
      <td style="font-family:monospace;">${fmtIc(r.ic_mean_6m)}</td>
      <td style="font-family:monospace; color:${Number(r.ic_mean_3m) < 0 ? "#ef4444" : "inherit"};">${fmtIc(r.ic_mean_3m)}</td>
      <td style="font-family:monospace;">${fmtNum(r.t_stat, 1)}</td>
      <td style="font-family:monospace;">${fmtPct(r.hit_rate)}</td>
      <td style="font-family:monospace;">${fmtNum(r.effectiveness_score)}</td>
      <td><span style="background:${color}22; border:1px solid ${color}; color:${color}; padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:700; white-space:nowrap;">${BUCKET_LABEL[bucket]}</span>${warn ? ' <span style="color:#ef4444; font-size:0.75rem; font-weight:700;">⚠️ 붕괴</span>' : ""}</td>
    </tr>`;
  }).join("");
  el.innerHTML = `<table class="alerts-table"><thead><tr>
    <th>팩터명</th><th>IC 전체</th><th>IC 12m</th><th>IC 6m</th><th>IC 3m</th><th>t-stat</th><th>히트율</th><th>유효성</th><th>상태</th>
  </tr></thead><tbody>${rows_html}</tbody></table>`;
}
window.renderFactorIcDecay = renderFactorIcDecay;

// ── 포지션 사이징 ──────────────────────────────────────────────────────────
const STOP_PCT = { short: 0.02, swing: 0.08, long: 0.15 };


function renderPaperTrading() {
  const payload = window.QUANT_DATA?.paper_trading || {};
  const summary = payload.summary || {};
  const latest = summary.latest || {};
  const account = Array.isArray(payload.account) ? payload.account : [];
  const positions = Array.isArray(payload.positions) ? payload.positions : [];
  const orders = Array.isArray(payload.orders) ? payload.orders : [];
  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  const asOf = document.getElementById("paper-trading-as-of");
  const cards = document.getElementById("paper-trading-cards");
  const posEl = document.getElementById("paper-positions-table");
  const orderEl = document.getElementById("paper-orders-table");
  const acctEl = document.getElementById("paper-account-table");
  if (!cards || !posEl || !orderEl || !acctEl) return;
  if (asOf) asOf.textContent = latest.run_date ? `최근 실행: ${latest.run_date}` : "아직 실행 기록 없음";
  const num = (v, digits=0) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return n.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  };
  const pct = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return `${n.toFixed(2)}%`;
  };
  const cardData = [
    ["총 평가금액", num(latest.equity), "원"],
    ["현금", num(latest.cash), "원"],
    ["포지션 평가", num(latest.position_value), "원"],
    ["누적 수익률", pct(latest.cumulative_return_pct), ""],
    ["보유 종목", String(summary.open_positions ?? positions.length), "개"],
  ];
  cards.innerHTML = cardData.map(([label, value, unit]) => `
    <div class="data-card" style="padding:14px;">
      <div style="color:var(--text-sub); font-size:0.75rem; font-weight:700;">${html(label)}</div>
      <div style="color:var(--primary); font-size:1.35rem; font-weight:800; margin-top:6px;">${html(value)} <span style="font-size:0.75rem; color:var(--text-sub);">${html(unit)}</span></div>
    </div>`).join("");
  if (!positions.length) {
    posEl.innerHTML = `<div style="color:var(--text-sub); padding:12px;">현재 보유 중인 페이퍼 포지션이 없습니다.</div>`;
  } else {
    posEl.innerHTML = `<table><thead><tr><th>종목</th><th>수량</th><th>평단</th><th>현재가</th><th>평가금액</th><th>미실현손익</th><th>수익률</th><th>진입일</th></tr></thead><tbody>${positions.map(r => `
      <tr><td>${html(r.ticker)}</td><td>${num(r.quantity)}</td><td>${num(r.avg_price)}</td><td>${num(r.last_price)}</td><td>${num(r.market_value)}</td><td>${num(r.unrealized_pnl)}</td><td>${pct(Number(r.unrealized_pnl_pct || 0) * 100)}</td><td>${html(r.entry_date)}</td></tr>`).join("")}</tbody></table>`;
  }
  const recentOrders = orders.slice(0, 25);
  const recentDecisions = decisions.slice(-25).reverse();
  orderEl.innerHTML = `<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
    <div><div style="color:var(--text-sub); font-size:0.78rem; font-weight:700; margin-bottom:8px;">주문</div>${recentOrders.length ? `<table><thead><tr><th>일자</th><th>종목</th><th>구분</th><th>수량</th><th>가격</th><th>사유</th></tr></thead><tbody>${recentOrders.map(r => `<tr><td>${html(r.run_date)}</td><td>${html(r.ticker)}</td><td>${html(r.side)}</td><td>${num(r.quantity)}</td><td>${num(r.price)}</td><td>${html(r.reason)}</td></tr>`).join("")}</tbody></table>` : `<div style="color:var(--text-sub);">주문 없음</div>`}</div>
    <div><div style="color:var(--text-sub); font-size:0.78rem; font-weight:700; margin-bottom:8px;">결정 로그</div>${recentDecisions.length ? `<table><thead><tr><th>일자</th><th>종목</th><th>결정</th><th>사유</th></tr></thead><tbody>${recentDecisions.map(r => `<tr><td>${html(r.run_date)}</td><td>${html(r.ticker)}</td><td>${html(r.decision)}</td><td>${html(r.reason)}</td></tr>`).join("")}</tbody></table>` : `<div style="color:var(--text-sub);">결정 로그 없음</div>`}</div>
  </div>`;
  acctEl.innerHTML = account.length ? `<table><thead><tr><th>일자</th><th>현금</th><th>포지션</th><th>총 평가</th><th>보유</th><th>일손익</th><th>누적수익률</th></tr></thead><tbody>${account.slice(-14).reverse().map(r => `<tr><td>${html(r.run_date)}</td><td>${num(r.cash)}</td><td>${num(r.position_value)}</td><td>${num(r.equity)}</td><td>${num(r.invested_count)}</td><td>${num(r.daily_pnl)}</td><td>${pct(r.cumulative_return_pct)}</td></tr>`).join("")}</tbody></table>` : `<div style="color:var(--text-sub); padding:12px;">계좌 스냅샷 없음</div>`;
}

function renderPositionSizing() {
  const account = Math.max(100, Number(document.getElementById("ps-account")?.value || 5000));
  const riskPct = Math.min(5, Math.max(0.1, Number(document.getElementById("ps-risk-pct")?.value || 1))) / 100;
  const stopType = document.getElementById("ps-stop-type")?.value || "swing";
  const topN = Number(document.getElementById("ps-top-n")?.value || 20);
  const stopPct = STOP_PCT[stopType] || 0.08;

  const saRows = Array.isArray(window.QUANT_DATA?.stock_attractiveness?.rows)
    ? window.QUANT_DATA.stock_attractiveness.rows : [];
  if (!saRows.length) {
    const el = document.getElementById("ps-table");
    if (el) el.innerHTML = "<p style='color:var(--text-sub);'>종목 데이터 없음 — export_web_data.py를 실행하세요.</p>";
    return;
  }

  // factor_master.latest_rows에서 month_volatility + composite_score 룩업
  const fmRows = Array.isArray(window.QUANT_DATA?.factor_master?.latest_rows)
    ? window.QUANT_DATA.factor_master.latest_rows : [];
  const fmMap = {};
  fmRows.forEach((r) => {
    const t = String(r.ticker || "").replace(/\.0$/, "").padStart(6, "0");
    fmMap[t] = { month_volatility: r.month_volatility, composite_score: r.composite_score };
  });

  // composite_score 기준 정렬 (더 분별력 있음)
  const sorted = [...saRows]
    .filter((r) => r.name || r.ticker)
    .sort((a, b) => {
      const ta = String(a.ticker || "").replace(/\.0$/, "").padStart(6, "0");
      const tb = String(b.ticker || "").replace(/\.0$/, "").padStart(6, "0");
      const sa2 = Number(fmMap[ta]?.composite_score ?? -1);
      const sb2 = Number(fmMap[tb]?.composite_score ?? -1);
      return sb2 - sa2;
    })
    .slice(0, topN);

  // 포지션 사이징: position_value(만원) = account * riskPct / stopPct
  const positionValue = Math.round((account * riskPct) / stopPct);
  const positionPct = positionValue / account;

  // 섹터 집중도 분석
  const sectorCount = {};
  sorted.forEach((r) => {
    const s = r.sector || "미분류";
    sectorCount[s] = (sectorCount[s] || 0) + 1;
  });
  const warnEl = document.getElementById("ps-sector-warning");
  const warnBody = document.getElementById("ps-sector-warning-body");
  const overloaded = Object.entries(sectorCount).filter(([s, n]) => s !== "미분류" && n >= 3);
  if (warnEl) {
    if (overloaded.length) {
      warnEl.style.display = "";
      if (warnBody) warnBody.innerHTML = overloaded.map(([s, n]) =>
        `<div style="font-size:0.85rem; color:#f59e0b; margin-bottom:4px;"><b>${html(s)}</b> ${n}종목 집중 — 동일 섹터 비중 과다 주의</div>`
      ).join("");
    } else {
      warnEl.style.display = "none";
    }
  }

  // 요약 카드
  const summaryEl = document.getElementById("ps-summary-cards");
  if (summaryEl) {
    summaryEl.innerHTML = [
      `<div class="data-card"><div style="font-size:0.78rem; color:var(--text-sub); margin-bottom:6px;">계좌 총액</div><div style="font-size:1.5rem; font-weight:700; color:var(--text-heading);">${account.toLocaleString()}만원</div></div>`,
      `<div class="data-card"><div style="font-size:0.78rem; color:var(--text-sub); margin-bottom:6px;">손절률 (${stopType === "short" ? "단타" : stopType === "swing" ? "스윙" : "장기"})</div><div style="font-size:1.5rem; font-weight:700; color:#ef4444;">-${(stopPct * 100).toFixed(0)}%</div></div>`,
      `<div class="data-card"><div style="font-size:0.78rem; color:var(--text-sub); margin-bottom:6px;">종목당 제안 비중</div><div style="font-size:1.5rem; font-weight:700; color:#10b981;">${(positionPct * 100).toFixed(1)}%</div><div style="font-size:0.75rem; color:var(--text-sub);">${positionValue.toLocaleString()}만원</div></div>`,
      `<div class="data-card"><div style="font-size:0.78rem; color:var(--text-sub); margin-bottom:6px;">최대 동시 보유 가능</div><div style="font-size:1.5rem; font-weight:700; color:var(--text-heading);">${Math.floor(1 / positionPct)}종목</div></div>`,
    ].join("");
  }

  // 테이블
  const tableEl = document.getElementById("ps-table");
  if (!tableEl) return;
  const fmtVol = (v) => v == null || v === "" ? "N/A" : (Number(v) * 100).toFixed(1) + "%";
  const fmtScore = (v) => v == null || v === "" ? "N/A" : (Number(v) * 100).toFixed(1) + "pt";
  const rowsHtml = sorted.map((r, i) => {
    const ticker = String(r.ticker || "").replace(/\.0$/, "").padStart(6, "0");
    const fm = fmMap[ticker] || {};
    const price = Number(r.price) || 0;
    const stopPrice = price > 0 ? Math.round(price * (1 - stopPct)) : null;
    const monthVol = fm.month_volatility != null ? Number(fm.month_volatility) : null;
    const volBandLow = (price > 0 && monthVol) ? Math.round(price * (1 - monthVol * Math.sqrt(21) * 1.645)) : null;
    const volBandHigh = (price > 0 && monthVol) ? Math.round(price * (1 + monthVol * Math.sqrt(21) * 1.645)) : null;
    const sector = r.sector || "";
    const sectorWarn = sector && (sectorCount[sector] || 0) >= 3;
    const compScore = fm.composite_score;
    return `<tr>
      <td><span style="font-weight:700; color:var(--text-heading);">${i + 1}. ${html(r.name || ticker)}</span><br><span style="font-size:0.72rem; color:var(--text-sub);">${html(ticker)}</span></td>
      <td style="font-size:0.82rem; color:${sectorWarn ? "#f59e0b" : "var(--text-sub)"};">${html(sector || "—")}${sectorWarn ? " ⚠️" : ""}</td>
      <td style="font-family:monospace;">${price > 0 ? price.toLocaleString() + "원" : "N/A"}</td>
      <td style="font-family:monospace; color:#ef4444;">${stopPrice ? stopPrice.toLocaleString() + "원" : "N/A"}</td>
      <td style="font-family:monospace; color:#10b981;">${(positionPct * 100).toFixed(1)}% (${positionValue.toLocaleString()}만)</td>
      <td style="font-family:monospace; font-size:0.78rem; color:var(--text-sub);">${monthVol ? fmtVol(monthVol) : "N/A"}<br><span style="font-size:0.72rem;">${volBandLow ? volBandLow.toLocaleString() + "~" + volBandHigh.toLocaleString() : ""}</span></td>
      <td style="font-family:monospace;">${fmtScore(compScore)}</td>
    </tr>`;
  }).join("");
  tableEl.innerHTML = `<table class="alerts-table"><thead><tr>
    <th>종목</th><th>업종</th><th>현재가</th><th>손절가 (${stopType === "short" ? "-2%" : stopType === "swing" ? "-8%" : "-15%"})</th><th>제안 비중</th><th>월변동성 / 95% 밴드</th><th>종합점수</th>
  </tr></thead><tbody>${rowsHtml}</tbody></table>`;
}
window.renderPositionSizing = renderPositionSizing;
window.renderPaperTrading = renderPaperTrading;

/* =====================================================
   뉴스 & 리서치 패널
   ===================================================== */

const OFFICE_NAME = {
  "001": "연합뉴스", "002": "KBS", "003": "MBC", "004": "SBS",
  "005": "YTN", "009": "매일경제", "011": "서울경제", "014": "파이낸셜뉴스",
  "015": "한국경제", "016": "아시아경제", "018": "이데일리",
  "020": "동아일보", "021": "문화일보", "022": "세계일보",
  "023": "조선비즈", "025": "중앙일보", "028": "한겨레",
  "032": "경향신문", "033": "머니투데이", "034": "뉴시스",
  "038": "한국일보", "047": "오마이뉴스", "050": "스포츠서울",
  "052": "국민일보", "055": "전자신문", "056": "비즈니스워치",
  "081": "서울신문", "082": "조선일보", "105": "디지털타임스",
  "119": "헤럴드경제", "138": "뉴스핌", "214": "뉴스1",
  "215": "한경닷컴", "374": "뉴데일리", "421": "녹색경제신문",
  "421": "비즈니스포스트", "658": "글로벌이코노믹",
};

function officeName(id) {
  return OFFICE_NAME[String(id).padStart(3, "0")] || `언론사#${id}`;
}

function sentimentColor(bucket) {
  if (bucket === "positive") return "#10b981";
  if (bucket === "negative") return "#ef4444";
  return "var(--text-sub)";
}

function sentimentLabel(bucket) {
  if (bucket === "positive") return "긍정";
  if (bucket === "negative") return "부정";
  return "중립";
}

function sentimentBadge(bucket) {
  const color = sentimentColor(bucket);
  const label = sentimentLabel(bucket);
  return `<span style="color:${color}; font-weight:700; font-size:0.8rem;">${label}</span>`;
}

// 상태
window._newsSentimentFilter = "all";

window.setNewsSentimentFilter = function(filter, btn) {
  window._newsSentimentFilter = filter;
  if (btn?.parentElement) {
    btn.parentElement.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  }
  renderNewsSentimentTable();
};

function renderNewsSentiment() {
  const nd = window.NEWS_DATA;
  if (!nd) return;

  // as-of 날짜
  const asOfEl = document.getElementById("news-sentiment-as-of");
  if (asOfEl) asOfEl.textContent = `기준: ${nd.as_of}`;

  // 요약 카드
  const { total_stocks, positive_stocks, negative_stocks, neutral_stocks, total_headlines } = nd.summary;
  const cardsEl = document.getElementById("news-summary-cards");
  if (cardsEl) {
    const cards = [
      { label: "커버리지 종목", value: total_stocks.toLocaleString(), color: "var(--primary)", icon: "fa-database" },
      { label: "긍정 종목", value: positive_stocks, color: "#10b981", icon: "fa-arrow-trend-up" },
      { label: "부정 종목", value: negative_stocks, color: "#ef4444", icon: "fa-arrow-trend-down" },
      { label: "중립 종목", value: neutral_stocks, color: "var(--text-sub)", icon: "fa-minus" },
      { label: "최근 헤드라인", value: total_headlines.toLocaleString() + "건", color: "#60a5fa", icon: "fa-newspaper" },
    ];
    cardsEl.innerHTML = cards.map(c => `
      <div style="background:var(--card-bg); border:1px solid var(--card-border); border-radius:8px; padding:16px; text-align:center;">
        <div style="color:${c.color}; font-size:1.6rem; font-weight:800; margin-bottom:4px;">
          <i class="fa-solid ${c.icon}" style="font-size:1rem; opacity:0.7; margin-right:4px;"></i>${html(String(c.value))}
        </div>
        <div style="color:var(--text-sub); font-size:0.8rem; font-weight:600;">${c.label}</div>
      </div>`).join("");
  }

  // 긍정 Top 10
  const positiveTop = nd.sentiment.filter(s => s.news_sentiment_bucket === "positive").slice(0, 10);
  renderTopSentimentTable("news-positive-top", positiveTop, "positive");

  // 부정 Top 10
  const negativeTop = [...nd.sentiment].filter(s => s.news_sentiment_bucket === "negative")
    .sort((a, b) => a.news_sentiment_score - b.news_sentiment_score).slice(0, 10);
  renderTopSentimentTable("news-negative-top", negativeTop, "negative");
  // 부정 종목 적을 때 인사이트 메시지
  if (negativeTop.length < 5) {
    const negEl = document.getElementById("news-negative-top");
    if (negEl) {
      const ratio = total_stocks ? ((negativeTop.length / total_stocks) * 100).toFixed(1) : 0;
      negEl.insertAdjacentHTML("afterend", `<div id="news-negative-insight" style="margin-top:8px; padding:10px 14px; border-radius:6px; background:var(--c-green-bg); border:1px solid var(--c-green-border); font-size:0.8rem; color:var(--c-green);">✓ 부정 감성 종목 ${negativeTop.length}개 / 전체 ${total_stocks}종목 중 ${ratio}% — 시장 전반 뉴스 분위기 양호</div>`);
    }
  }

  // 전체 테이블
  renderNewsSentimentTable();
}

function renderTopSentimentTable(containerId, rows, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!rows.length) { el.innerHTML = `<p style="color:var(--text-sub); font-size:0.85rem; padding:10px;">데이터 없음</p>`; return; }
  const color = type === "positive" ? "#10b981" : "#ef4444";
  const rowsHtml = rows.map(r => `
    <tr>
      <td><span style="font-weight:700; color:var(--text-heading);">${html(r.name || "종목명 미상")}</span>
          <span style="color:var(--text-sub); font-size:0.75rem; margin-left:4px;">${html(r.ticker)}</span></td>
      <td style="color:${color}; font-weight:700;">${r.news_sentiment_score !== null ? (r.news_sentiment_score * 100).toFixed(0) : "-"}</td>
      <td style="color:var(--text-sub);">${r.article_count}</td>
    </tr>`).join("");
  el.innerHTML = `<table class="alerts-table"><thead><tr>
    <th>종목</th><th>감성점수</th><th>기사수</th>
  </tr></thead><tbody>${rowsHtml}</tbody></table>`;
}

window.renderNewsSentimentTable = function() {
  const nd = window.NEWS_DATA;
  if (!nd) return;
  const el = document.getElementById("news-sentiment-table");
  if (!el) return;

  const searchTerm = (document.getElementById("news-sentiment-search")?.value || "").trim().toLowerCase();
  const filter = window._newsSentimentFilter || "all";

  let rows = nd.sentiment;
  if (filter !== "all") rows = rows.filter(r => r.news_sentiment_bucket === filter);
  if (searchTerm) {
    rows = rows.filter(r =>
      (r.name || "").toLowerCase().includes(searchTerm) ||
      (r.ticker || "").includes(searchTerm)
    );
  }

  if (!rows.length) { el.innerHTML = `<p style="color:var(--text-sub); padding:16px; text-align:center;">해당 조건의 종목이 없습니다.</p>`; return; }

  const rowsHtml = rows.map((r, i) => {
    const score = r.news_sentiment_score !== null ? (r.news_sentiment_score * 100).toFixed(1) : "-";
    const barW = r.news_sentiment_score !== null ? Math.max(0, Math.min(100, r.news_sentiment_score * 100)).toFixed(0) : 0;
    const barColor = r.news_sentiment_bucket === "positive" ? "#10b981" : r.news_sentiment_bucket === "negative" ? "#ef4444" : "var(--text-sub)";
    const posRatio = r.article_count ? ((r.positive_count / r.article_count) * 100).toFixed(0) : 0;
    const negRatio = r.article_count ? ((r.negative_count / r.article_count) * 100).toFixed(0) : 0;
    return `<tr>
      <td style="font-size:0.82rem;">${i + 1}</td>
      <td><span style="font-weight:700; color:var(--text-heading);">${html(r.name || r.ticker)}</span>
          <br><span style="color:var(--text-sub); font-size:0.72rem;">${html(r.ticker)} ${html(r.sector || "")}</span></td>
      <td>${sentimentBadge(r.news_sentiment_bucket)}</td>
      <td>
        <div style="display:flex; align-items:center; gap:6px;">
          <div style="flex:1; height:10px; background:var(--card-border); border-radius:5px;">
            <div style="width:${barW}%; height:100%; background:${barColor}; border-radius:5px;"></div>
          </div>
          <span style="font-size:0.8rem; color:${barColor}; font-weight:700; min-width:30px;">${score}</span>
        </div>
      </td>
      <td style="font-size:0.8rem; color:var(--text-sub);">${r.article_count}</td>
      <td style="font-size:0.78rem;">
        <span style="color:#10b981;">${posRatio}%↑</span>
        <span style="color:var(--text-sub); margin:0 2px;">/</span>
        <span style="color:#ef4444;">${negRatio}%↓</span>
      </td>
      <td style="font-size:0.78rem; color:var(--text-sub);">${r.latest_headline_date || "-"}</td>
    </tr>`;
  }).join("");

  el.innerHTML = `<table class="alerts-table"><thead><tr>
    <th>#</th><th>종목</th><th>감성</th><th>감성점수 (0~100)</th><th>기사수</th><th>긍정/부정비율</th><th>최신기사</th>
  </tr></thead><tbody>${rowsHtml}</tbody></table>`;
};

window.renderNewsHeadlinesFeed = function() {
  const nd = window.NEWS_DATA;
  if (!nd) return;
  const feedEl = document.getElementById("news-headlines-feed");
  const countEl = document.getElementById("news-headlines-count");
  if (!feedEl) return;

  const searchTerm = (document.getElementById("news-headlines-search")?.value || "").trim().toLowerCase();
  const limit = parseInt(document.getElementById("news-headlines-limit")?.value || "100");

  let rows = nd.headlines;
  if (searchTerm) {
    rows = rows.filter(h =>
      (h.name || "").toLowerCase().includes(searchTerm) ||
      (h.ticker || "").includes(searchTerm) ||
      (h.title || "").toLowerCase().includes(searchTerm)
    );
  }

  const total = rows.length;
  rows = rows.slice(0, limit);

  if (countEl) countEl.textContent = `총 ${total.toLocaleString()}건 / 표시 ${rows.length}건`;

  if (!rows.length) {
    feedEl.innerHTML = `<div style="color:var(--text-sub); text-align:center; padding:30px;">검색 결과가 없습니다.</div>`;
    return;
  }

  // 날짜별 그룹핑
  const grouped = {};
  rows.forEach(h => {
    const d = h.date || "미상";
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(h);
  });

  const sections = Object.keys(grouped).sort().reverse().map(date => {
    const items = grouped[date];
    const itemsHtml = items.map(h => {
      const ticker = h.ticker || "";
      const name = h.name || ticker;
      // 관련 종목 뱃지 (중복 제거 후 tickers 목록 표시)
      const related = h.related || [{ ticker, name }];
      const tickerBadges = related.slice(0, 4).map(r => {
        const n = r.name || r.ticker;
        return `<span style="background:var(--c-green-bg); border:1px solid var(--c-green-border); color:var(--c-green); font-size:0.72rem; font-weight:700; padding:2px 7px; border-radius:4px; white-space:nowrap; margin-right:3px;">${html(n)}</span>`;
      }).join("");
      const moreCount = related.length > 4 ? `<span style="color:var(--text-sub); font-size:0.72rem; margin-left:2px;">+${related.length - 4}</span>` : "";
      return `<div style="display:flex; align-items:flex-start; gap:10px; padding:11px 14px; border-bottom:1px solid var(--card-border); transition:background 0.15s;"
              onmouseover="this.style.background='var(--btn-hover-bg)'" onmouseout="this.style.background=''">
        <div style="flex:1; min-width:0;">
          <div style="color:var(--text-heading); font-size:0.875rem; font-weight:500; line-height:1.5; word-break:keep-all; margin-bottom:5px;">${html(h.title)}</div>
          <div style="display:flex; align-items:center; flex-wrap:wrap; gap:3px;">
            ${tickerBadges}${moreCount}
          </div>
        </div>
      </div>`;
    }).join("");

    return `<div style="margin-bottom:16px;">
      <div style="font-size:0.8rem; font-weight:700; color:var(--primary); padding:6px 12px; background:rgba(16,185,129,0.07); border-radius:6px; margin-bottom:4px; display:inline-block;">
        <i class="fa-regular fa-calendar"></i> ${date}
      </div>
      <div style="background:var(--card-bg); border:1px solid var(--card-border); border-radius:8px; overflow:hidden;">${itemsHtml}</div>
    </div>`;
  }).join("");

  feedEl.innerHTML = sections;
};

window.renderNewsSentiment = renderNewsSentiment;

// ── 개선 #2: 상태바 초기화 ──────────────────────────────────────────────────
function renderStatusBar() {
  const d = window.QUANT_DATA;
  if (!d) return;

  // 레짐 배지 — 가장 중요한 신호를 dominant하게 표시
  const regimeRows = d.macro_factors?.market_macro_regime_month;
  const latestRegime = regimeRows?.slice(-1)[0];
  const regimeBadge = document.getElementById("status-regime-badge");
  if (regimeBadge && latestRegime) {
    const isRiskOn = latestRegime.market_regime === "risk_on";
    regimeBadge.textContent = isRiskOn ? "📈 Risk-ON" : "🛡 Risk-OFF";
    regimeBadge.style.color = isRiskOn ? "var(--c-green)" : "var(--c-yellow)";
    regimeBadge.style.background = isRiskOn ? "rgba(16,185,129,0.15)" : "rgba(245,158,11,0.15)";
    regimeBadge.style.borderRight = `1px solid ${isRiskOn ? "var(--c-green-border)" : "var(--c-yellow-border)"}`;
  }

  // KOSPI 60d
  const k60 = latestRegime?.korea_kospi_ret_60d_pct;
  const statusKospi = document.getElementById("status-kospi");
  if (statusKospi && k60 != null) {
    const sign = k60 >= 0 ? "+" : "";
    statusKospi.innerHTML = `<span style="color:var(--text-sub);">KOSPI 60d </span><span style="font-weight:700; color:${k60 >= 0 ? "var(--c-green)" : "var(--c-red)"};">${sign}${k60.toFixed(1)}%</span>`;
  }

  // DGS10
  const dgs10rows = d.macro?.DGS10;
  const dgs10 = dgs10rows?.slice(-1)[0]?.DGS10;
  const statusDgs10 = document.getElementById("status-dgs10");
  if (statusDgs10 && dgs10 != null) {
    statusDgs10.innerHTML = `<span style="color:var(--text-sub);">미 10Y </span><span style="font-weight:700; color:var(--c-yellow);">${dgs10.toFixed(2)}%</span>`;
  }

  // 날짜
  const statusDate = document.getElementById("status-date");
  if (statusDate) {
    const now = new Date();
    const m = now.getMonth() + 1;
    const d = now.getDate();
    const wd = ["일","월","화","수","목","금","토"][now.getDay()];
    statusDate.textContent = `${m}.${d}(${wd})`;
  }
}
window.renderStatusBar = renderStatusBar;

// ── 개선 #3: 홈 대시보드 ────────────────────────────────────────────────────
function renderHomeDashboard() {
  const d = window.QUANT_DATA;
  if (!d) return;

  // 레짐 배너
  const regimeRows = d.macro_factors?.market_macro_regime_month;
  const lr = regimeRows?.slice(-1)[0];
  if (lr) {
    const isRiskOn = lr.market_regime === "risk_on";
    const banner = document.getElementById("home-regime-banner");
    if (banner) {
      banner.style.borderColor = isRiskOn ? "var(--c-green-border)" : "var(--c-yellow-border)";
      banner.style.background = isRiskOn ? "rgba(16,185,129,0.04)" : "rgba(245,158,11,0.04)";
    }
    const labelEl = document.getElementById("home-regime-label");
    if (labelEl) {
      labelEl.textContent = isRiskOn ? "📈 Risk-ON" : "🛡 Risk-OFF";
      labelEl.style.color = isRiskOn ? "var(--c-green)" : "var(--c-yellow)";
    }
    const detailEl = document.getElementById("home-regime-detail");
    if (detailEl) {
      const flags = [];
      if (lr.dollar_pressure_flag) flags.push("달러 강세 압력");
      if (lr.export_recovery_flag) flags.push("수출 회복");
      if (lr.growth_on_flag) flags.push("성장 신호");
      if (lr.risk_off_flag) flags.push("리스크 오프");
      detailEl.textContent = flags.length ? flags.join(" · ") : "주요 이벤트 없음";
    }
    // 지표 값들
    const setEl = (id, val, decimals = 2) => {
      const el = document.getElementById(id);
      if (el && val != null) el.textContent = typeof val === "number" ? val.toFixed(decimals) : val;
    };
    setEl("home-dxy", lr.dxy_zscore_252d);
    setEl("home-vix", lr.vix_zscore_252d);
    const dgs10Raw = d.macro?.DGS10?.slice(-1)[0]?.DGS10;
    const dgs10 = (dgs10Raw != null && dgs10Raw !== "") ? Number(dgs10Raw) : null;
    if (dgs10 != null && isFinite(dgs10)) {
      const el = document.getElementById("home-dgs10");
      if (el) el.textContent = dgs10.toFixed(2) + "%";
    }
    const k60Raw = lr.korea_kospi_ret_60d_pct;
    const k60 = (k60Raw != null && k60Raw !== "") ? Number(k60Raw) : null;
    if (k60 != null && isFinite(k60)) {
      const el = document.getElementById("home-kospi-60d");
      if (el) {
        el.textContent = (k60 >= 0 ? "+" : "") + k60.toFixed(1) + "%";
        el.style.color = k60 >= 0 ? "var(--c-green)" : "var(--c-red)";
      }
    }
    const kq60Raw = lr.korea_kosdaq_ret_60d_pct;
    const kq60 = (kq60Raw != null && kq60Raw !== "") ? Number(kq60Raw) : null;
    if (kq60 != null && isFinite(kq60)) {
      const el = document.getElementById("home-kosdaq-60d");
      if (el) {
        el.textContent = (kq60 >= 0 ? "+" : "") + kq60.toFixed(1) + "%";
        el.style.color = kq60 >= 0 ? "var(--c-green)" : "var(--c-red)";
      }
    }
    setEl("home-regime-date", lr.period?.slice(0, 7) || "--", 0);
  }


  // Decision OS: 홈 최상단 결론/행동 신호
  const stockRows = Array.isArray(d.stock_attractiveness?.rows) ? d.stock_attractiveness.rows : [];
  const bRows = stockRows.filter(r => r.project_universe_b === 1);
  const buyCount = bRows.filter(r => String(r.model_decision || "").toUpperCase() === "BUY").length;
  const watchCount = bRows.filter(r => String(r.model_decision || "").toUpperCase() === "WATCH").length;
  const rejectCount = bRows.filter(r => String(r.model_decision || "").toUpperCase() === "REJECT").length;
  const marketFundLatest = d.money_flow?.market_funds_trend?.slice(-1)[0]?.date || lr?.period?.slice(0, 10) || "--";
  const riskScore = lr ? [lr.risk_off_flag, lr.dollar_pressure_flag, (lr.vix_zscore_252d || 0) > 1.2, (lr.korea_kospi_ret_60d_pct || 0) < 0].filter(Boolean).length : 0;
  const riskLabel = riskScore >= 3 ? "HIGH" : riskScore >= 1 ? "MID" : "LOW";
  const isRiskOnDecision = lr?.market_regime === "risk_on" && riskScore <= 1;
  const actionLabel = isRiskOnDecision && buyCount > 0 ? "BUY 가능 · 선별 진입" : buyCount > 0 ? "WATCH 우선 · 조건부 진입" : "방어 우선 · 관찰";
  const decisionTitle = document.getElementById("home-decision-title");
  if (decisionTitle) {
    decisionTitle.textContent = actionLabel;
    decisionTitle.style.color = riskLabel === "HIGH" ? "var(--c-yellow)" : isRiskOnDecision ? "var(--c-green)" : "var(--text-heading)";
  }
  const setDecisionValue = (id, value, color) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    if (color) el.style.color = color;
  };
  setDecisionValue("home-buy-count", buyCount || "0", buyCount > 0 ? "var(--c-green)" : "var(--text-sub)");
  setDecisionValue("home-watch-count", watchCount || "0", "var(--c-yellow)");
  setDecisionValue("home-risk-level", riskLabel, riskLabel === "HIGH" ? "var(--c-red)" : riskLabel === "MID" ? "var(--c-yellow)" : "var(--c-green)");
  setDecisionValue("home-data-date", marketFundLatest === "--" ? "--" : marketFundLatest.slice(5), "var(--accent)");
  const reasonEl = document.getElementById("home-decision-reasons");
  if (reasonEl) {
    const reasons = [];
    reasons.push(lr?.market_regime === "risk_on" ? "Risk-ON: 공격 가능하지만 후보별 진입 조건 확인" : "Risk-OFF: 신규 매수보다 WATCH/리스크 관리 우선");
    reasons.push(`모델 분류: BUY ${buyCount} · WATCH ${watchCount} · REJECT ${rejectCount}`);
    if (lr?.dollar_pressure_flag) reasons.push("달러 압력 플래그: 외국인 수급/환율 민감도 체크");
    if ((lr?.korea_kospi_ret_60d_pct || 0) < 0) reasons.push("KOSPI 60일 모멘텀 음수: 추격매수 금지");
    if (window.NEWS_DATA?.summary) reasons.push(`뉴스 감성: 긍정 ${window.NEWS_DATA.summary.positive_stocks || 0} / 부정 ${window.NEWS_DATA.summary.negative_stocks || 0}`);
    reasonEl.innerHTML = reasons.slice(0, 5).map((reason, i) => `<div><span style="color:${i === 0 ? 'var(--accent)' : 'var(--text-sub)'}; font-weight:900;">${i === 0 ? '→' : '•'}</span><span>${html(reason)}</span></div>`).join("");
  }

  // Top 5 후보 (개선 #5/#6: 색상 코딩 + 매력도 점수 시각적 강조)
  const top5El = document.getElementById("home-top5");
  if (top5El && d.stock_attractiveness?.rows) {
    const top5 = d.stock_attractiveness.rows
      .filter(r => r.project_universe_b === 1)
      .sort((a, b) => (b.market_attractiveness_score || 0) - (a.market_attractiveness_score || 0))
      .slice(0, 5);

    top5El.innerHTML = top5.map((r, i) => {
      const score = r.market_attractiveness_score || 0;
      const pct = Math.round(score * 100);
      const scoreColor = pct >= 70 ? "var(--c-green)" : pct >= 40 ? "var(--c-yellow)" : "var(--c-red)";
      const scenarioA = r.scenario_a_momentum;
      const scenarioB = r.scenario_b_value_quality;
      const riskFlags = (r.risk_flags || []).slice(0, 2);
      const riskHtml = riskFlags.length
        ? `<span style="color:var(--c-red); font-size:0.7rem; margin-left:6px;">⚠ ${riskFlags[0]}</span>`
        : "";

      return `<div style="display:flex; align-items:center; gap:12px; padding:10px 12px; background:var(--btn-bg); border:1px solid var(--card-border); border-radius:8px; border-left:3px solid ${scoreColor};">
        <div style="font-size:1.1rem; font-weight:800; color:var(--text-sub); width:20px; text-align:center;">${i + 1}</div>
        <div style="flex:1; min-width:0;">
          <div style="font-weight:700; color:var(--text-heading); font-size:0.9rem;">${html(r.name || r.ticker)}<span style="font-size:0.72rem; color:var(--text-sub); margin-left:6px;">${r.ticker}</span>${riskHtml}</div>
          <div style="font-size:0.75rem; color:var(--text-sub); margin-top:2px;">
            ${scenarioA != null ? `모멘텀 ${Math.round(scenarioA*100)}` : ""}
            ${scenarioB != null ? ` · 가치 ${Math.round(scenarioB*100)}` : ""}
          </div>
        </div>
        <div style="text-align:right; flex-shrink:0;">
          <div style="font-size:1.3rem; font-weight:800; color:${scoreColor};">${pct}</div>
          <div style="font-size:0.68rem; color:var(--text-sub);">Action</div>
          <div style="width:50px; height:10px; background:var(--card-border); border-radius:5px; margin-top:4px; overflow:hidden;">
            <div style="height:100%; width:${pct}%; background:${scoreColor}; border-radius:5px;"></div>
          </div>
        </div>
      </div>`;
    }).join("");
  }

  // IC 경보 (구조: d.regression.factor_ic.factors = [{key,label,ic_mean,ic_ir,significant,...}])
  const icEl = document.getElementById("home-ic-alerts");
  if (icEl && d.regression?.factor_ic?.factors) {
    const factors = d.regression.factor_ic.factors;
    const alerts = factors.filter(f => {
      const ic = f.ic_mean;
      return ic == null || Math.abs(ic) < 0.02 || !f.significant;
    });
    const goods = factors.filter(f => f.significant && f.ic_mean != null && Math.abs(f.ic_mean) >= 0.02);

    if (alerts.length === 0) {
      icEl.innerHTML = `<div style="color:var(--c-green); font-size:0.85rem; padding:8px;">✓ 모든 주요 팩터 IC 정상 (${goods.length}개 유효)</div>`;
    } else {
      const html2 = alerts.slice(0, 5).map(f => {
        const ic = f.ic_mean;
        const isNull = ic == null;
        const color = isNull ? "var(--text-sub)" : Math.abs(ic) < 0.01 ? "var(--c-red)" : "var(--c-yellow)";
        const bg = isNull ? "var(--c-grey-bg)" : Math.abs(ic) < 0.01 ? "var(--c-red-bg)" : "var(--c-yellow-bg)";
        const border = isNull ? "var(--c-grey-border)" : Math.abs(ic) < 0.01 ? "var(--c-red-border)" : "var(--c-yellow-border)";
        const icon = isNull ? "○" : Math.abs(ic) < 0.01 ? "⬇" : "⚠";
        return `<div style="display:flex; align-items:center; justify-content:space-between; padding:7px 10px; border-radius:6px; background:${bg}; border:1px solid ${border};">
          <span style="font-size:0.78rem; font-weight:600; color:${color};">${icon} ${html(f.label || f.key)}</span>
          <span style="font-size:0.78rem; font-weight:700; color:${color};">${isNull ? "데이터없음" : "IC " + ic.toFixed(3)}</span>
        </div>`;
      }).join("");
      icEl.innerHTML = `<div style="font-size:0.75rem; color:var(--text-sub); margin-bottom:8px;">유효팩터 ${goods.length}/${factors.length}개 <span style="opacity:0.65;">· IC&lt;0.05=예측력 약화</span></div>` + html2
        + (alerts.length > 0 ? `<div style="margin-top:10px; padding:8px 10px; border-radius:6px; background:var(--c-yellow-bg); border:1px solid var(--c-yellow-border); font-size:0.75rem; color:var(--c-yellow);">→ IC 약화 팩터 포함 종목 비중 축소 권장. 팩터 심사표에서 IC 복원 여부 확인.</div>` : "");
    }
  }

  // 뉴스 감성 요약
  const newsSumEl = document.getElementById("home-news-summary");
  if (newsSumEl && window.NEWS_DATA?.summary) {
    const s = window.NEWS_DATA.summary;
    const items = [
      { label: "긍정", val: s.positive_stocks, color: "var(--c-green)", bg: "var(--c-green-bg)", border: "var(--c-green-border)" },
      { label: "부정", val: s.negative_stocks, color: "var(--c-red)", bg: "var(--c-red-bg)", border: "var(--c-red-border)" },
      { label: "중립", val: s.neutral_stocks, color: "var(--text-sub)", bg: "var(--c-grey-bg)", border: "var(--c-grey-border)" },
      { label: "헤드라인", val: s.total_headlines?.toLocaleString(), color: "var(--c-blue)", bg: "var(--c-blue-bg)", border: "var(--c-blue-border)" },
    ];
    newsSumEl.innerHTML = items.map(it => `
      <div style="padding:10px 16px; border-radius:8px; background:${it.bg}; border:1px solid ${it.border}; text-align:center; min-width:80px;">
        <div style="font-size:1.4rem; font-weight:800; color:${it.color};">${it.val}</div>
        <div style="font-size:0.72rem; color:var(--text-sub); margin-top:2px;">${it.label}</div>
      </div>`).join("");
  }

  // 최신 헤드라인 미리보기 (8개)
  const headlinesEl = document.getElementById("home-headlines-preview");
  if (headlinesEl && window.NEWS_DATA?.headlines?.length) {
    const preview = window.NEWS_DATA.headlines.slice(0, 8);
    headlinesEl.innerHTML = preview.map((h, i) => {
      const name = h.name || h.ticker || "";
      const relCount = (h.related || []).length;
      const moreLabel = relCount > 1 ? `<span style="color:var(--text-sub); font-size:0.68rem;"> +${relCount - 1}</span>` : "";
      return `<div style="display:flex; gap:10px; padding:9px 0; border-bottom:1px solid var(--card-border); align-items:flex-start;">
        <div style="flex:1; min-width:0;">
          <div style="font-size:0.83rem; color:var(--text-heading); font-weight:500; line-height:1.4; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${html(h.title)}</div>
          <div style="margin-top:3px; font-size:0.7rem; color:var(--text-sub);">
            <span style="color:var(--c-green); font-weight:700;">${html(name)}</span>${moreLabel}
            <span style="margin-left:6px;">${h.date || ""}</span>
          </div>
        </div>
      </div>`;
    }).join("");
  }

  // 매크로 스코어 미니 패널
  const macroEl = document.getElementById("home-macro-scores");
  if (macroEl && lr) {
    const _toNum = v => (v != null && v !== "") ? Number(v) : null;
    const scoreItems = [
      { label: "DXY z-score", val: _toNum(lr.dxy_zscore_252d), unit: "", flag: lr.dollar_pressure_flag, warn: v => v > 1.5 },
      { label: "VIX z-score", val: _toNum(lr.vix_zscore_252d), unit: "", flag: false, warn: v => v > 1.5 },
      { label: "미 10Y 금리", val: _toNum(d.macro?.DGS10?.slice(-1)[0]?.DGS10), unit: "%", flag: false, warn: v => v > 4.5 },
      { label: "KOSPI 60d", val: _toNum(lr.korea_kospi_ret_60d_pct), unit: "%", flag: false, warn: v => v < 0 },
      { label: "KOSDAQ 60d", val: _toNum(lr.korea_kosdaq_ret_60d_pct), unit: "%", flag: false, warn: v => v < 0 },
    ];
    macroEl.innerHTML = scoreItems.map(item => {
      if (item.val == null || !isFinite(item.val)) return "";
      const isWarn = item.warn(item.val);
      const color = isWarn ? "var(--c-yellow)" : "var(--c-green)";
      const sign = (item.unit === "%" && item.val > 0) ? "+" : "";
      const dispVal = `${sign}${item.val.toFixed(2)}${item.unit}`;
      return `<div style="display:flex; align-items:center; justify-content:space-between; padding:7px 10px; border-radius:6px; background:var(--btn-bg); border:1px solid var(--card-border);">
        <span style="font-size:0.78rem; color:var(--text-sub);">${html(item.label)}</span>
        <span style="font-size:0.82rem; font-weight:700; color:${color};">${dispVal}${item.flag ? " ⚠" : ""}</span>
      </div>`;
    }).join("");
  }
}
window.renderHomeDashboard = renderHomeDashboard;

function kiwoomClass(value) {
  const v = String(value || "unknown").toLowerCase();
  if (["on", "buy", "promote", "ok", "loaded"].some(x => v.includes(x))) return "on";
  if (["caution", "watch", "ready", "wait", "dry"].some(x => v.includes(x))) return "caution";
  if (["off", "reject", "error", "fail", "bad"].some(x => v.includes(x))) return "off";
  return "unknown";
}


function renderTradeImportExportPanel() {
  const data = window.QUANT_DATA?.trade_import_export || {};
  const verdict = data.verdict || {};
  const ecosLatest = data.ecos?.latest || {};
  const allMonths = Array.isArray(data.ecos?.monthly) ? data.ecos.monthly : [];
  const ecosRows = allMonths.slice(-12).reverse();
  const itemRows = Array.isArray(data.customs?.summary) ? data.customs.summary : [];

  const set = (id, val, color) => { const el = document.getElementById(id); if (!el) return; el.textContent = val ?? "--"; if (color) el.style.color = color; };
  const fmtPct = (v) => { const n = Number(v); return Number.isFinite(n) ? `${n >= 0 ? "+" : ""}${n.toFixed(1)}%` : "--"; };
  const pctColor = (v) => Number(v) >= 0 ? "var(--c-green)" : "var(--c-red)";
  const fmtUsd = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return "--";
    if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${n.toLocaleString()}`;
  };
  // verdict.reasons 문자열 내 raw 대형숫자 → $B/$M 치환, "(ECOS 단위 기준)" 제거
  const fmtReason = (r) => r
    .replace(/([\d,]{8,})/g, (m) => {
      const n = Number(m.replace(/,/g, ""));
      if (!Number.isFinite(n)) return m;
      if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
      if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
      return m;
    })
    .replace(/\s*\(ECOS 단위 기준\)/g, "");
  const fmtMonth = (m) => { const s = String(m || ""); return s.length === 6 ? `${s.slice(0,4)}-${s.slice(4,6)}` : s; };
  const sigColor = (sig) => {
    if (!sig) return "var(--text-sub)";
    if (/(개선|상승|증가)/.test(sig)) return "var(--c-green)";
    if (/(하락|둔화|감소)/.test(sig)) return "var(--c-red)";
    return "var(--c-yellow)";
  };

  // ── 히어로 지표
  const stance = String(verdict.stance || "UNKNOWN").toUpperCase();
  set("trade-hero-title", verdict.title || "수출입 데이터 수집 대기");
  set("trade-hero-verdict", data.source_decision?.reason || "ECOS + 관세청 하이브리드 분석");
  set("trade-export-yoy-metric",  fmtPct(ecosLatest.exports_usd_yoy_pct),         pctColor(ecosLatest.exports_usd_yoy_pct));
  set("trade-import-yoy-metric",  fmtPct(ecosLatest.imports_usd_yoy_pct),         pctColor(ecosLatest.imports_usd_yoy_pct));
  set("trade-balance-metric",     fmtUsd(ecosLatest.trade_balance_usd),            Number(ecosLatest.trade_balance_usd) >= 0 ? "var(--c-green)" : "var(--c-red)");
  set("trade-export-mom-metric",  fmtPct(ecosLatest.exports_usd_mom_pct),          pctColor(ecosLatest.exports_usd_mom_pct));
  set("trade-vol-yoy-metric",     fmtPct(ecosLatest.export_volume_index_yoy_pct),  pctColor(ecosLatest.export_volume_index_yoy_pct));
  set("trade-ecos-month-metric",  fmtMonth(ecosLatest.month));

  const pill = document.getElementById("trade-stance-pill");
  if (pill) {
    const lbl = { POSITIVE: "긍정", NEGATIVE: "부정", NEUTRAL: "중립" }[stance] || stance;
    pill.textContent = lbl;
    pill.style.background = stance === "POSITIVE" ? "rgba(34,197,94,.18)" : stance === "NEGATIVE" ? "rgba(239,68,68,.18)" : "rgba(245,158,11,.18)";
    pill.style.color    = stance === "POSITIVE" ? "var(--c-green)"   : stance === "NEGATIVE" ? "var(--c-red)"   : "var(--c-yellow)";
  }

  const ev = document.getElementById("trade-evidence-list");
  if (ev) ev.innerHTML = (verdict.reasons?.length ? verdict.reasons : ["데이터 수집 대기"]).map((r, i) =>
    `<div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:5px;">
       <span style="color:${i===0?'var(--accent)':'var(--text-sub)'};font-weight:900;flex-shrink:0;">${i===0?'→':'•'}</span>
       <span style="font-size:0.87rem;">${html(fmtReason(r))}</span>
     </div>`
  ).join("");

  // ── 차트: 기존 인스턴스 먼저 파괴
  tradeChartInstances.forEach(c => { try { c.destroy(); } catch (_) {} });
  tradeChartInstances = [];

  const trendEl = document.getElementById("trade-trend-charts");
  if (trendEl && window.Chart && allMonths.length) {
    trendEl.innerHTML = "";
    const labels = allMonths.map(r => fmtMonth(r.month));

    const mkCtx = (title, height = 200) => {
      const wrap = document.createElement("div");
      wrap.style.cssText = "background:var(--card-bg);border:1px solid var(--card-border);border-radius:8px;padding:14px;";
      const h4 = document.createElement("h4");
      h4.style.cssText = "font-size:0.85rem;color:var(--text-sub);margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em;";
      h4.textContent = title;
      const cc = document.createElement("div");
      cc.style.cssText = `position:relative;height:${height}px;`;
      const cv = document.createElement("canvas");
      cc.appendChild(cv); wrap.appendChild(h4); wrap.appendChild(cc);
      trendEl.appendChild(wrap);
      return cv.getContext("2d");
    };

    const baseOpts = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#9ca3af", font: { size: 11 }, boxWidth: 12, padding: 10 } } },
      scales: {
        x: { ticks: { color: "#6b7280", maxTicksLimit: 8, font: { size: 10 } }, grid: { color: "rgba(255,255,255,.04)" } },
        y: { ticks: { color: "#6b7280", font: { size: 10 } },                    grid: { color: "rgba(255,255,255,.04)" } },
      },
    };

    // 차트 1 — 수출/수입/무역수지 금액 (라인, 전체 기간)
    const ctx1 = mkCtx("수출 · 수입 · 무역수지 ($억)", 300);
    if (ctx1) tradeChartInstances.push(new Chart(ctx1, {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "수출",     data: allMonths.map(r => r.exports_usd       != null ? +(r.exports_usd/1e8).toFixed(1)      : null), borderColor: "#10b981", backgroundColor: "rgba(16,185,129,.12)", borderWidth: 2, fill: true,  tension: 0.3, pointRadius: 2 },
          { label: "수입",     data: allMonths.map(r => r.imports_usd       != null ? +(r.imports_usd/1e8).toFixed(1)      : null), borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.07)", borderWidth: 2, fill: false, tension: 0.3, pointRadius: 2 },
          { label: "무역수지", data: allMonths.map(r => r.trade_balance_usd != null ? +(r.trade_balance_usd/1e8).toFixed(1): null), borderColor: "#8b5cf6", backgroundColor: "rgba(139,92,246,.08)", borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 2, borderDash: [4,3] },
        ],
      },
      options: { ...baseOpts, scales: { ...baseOpts.scales, y: { ...baseOpts.scales.y, ticks: { ...baseOpts.scales.y.ticks, callback: v => `$${v}억` } } } },
    }));

    // 차트 2 — 수출 YoY / 수입 YoY / 수출물량 YoY (바 + 라인 혼합)
    const ctx2 = mkCtx("YoY 성장률: 수출금액 · 수입금액 · 수출물량 (%)", 300);
    if (ctx2) tradeChartInstances.push(new Chart(ctx2, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "수출금액 YoY", type: "bar",  data: allMonths.map(r => r.exports_usd_yoy_pct         != null ? +Number(r.exports_usd_yoy_pct).toFixed(1)         : null), backgroundColor: allMonths.map(r => Number(r.exports_usd_yoy_pct) >= 0 ? "rgba(16,185,129,.65)" : "rgba(239,68,68,.55)"), borderRadius: 2, order: 2 },
          { label: "수입금액 YoY", type: "bar",  data: allMonths.map(r => r.imports_usd_yoy_pct         != null ? +Number(r.imports_usd_yoy_pct).toFixed(1)         : null), backgroundColor: allMonths.map(r => Number(r.imports_usd_yoy_pct) >= 0 ? "rgba(245,158,11,.55)" : "rgba(239,68,68,.35)"), borderRadius: 2, order: 3 },
          { label: "수출물량 YoY", type: "line", data: allMonths.map(r => r.export_volume_index_yoy_pct != null ? +Number(r.export_volume_index_yoy_pct).toFixed(1) : null), borderColor: "#60a5fa", borderWidth: 2, pointRadius: 3, fill: false, tension: 0.3, order: 1 },
        ],
      },
      options: { ...baseOpts, scales: { ...baseOpts.scales, y: { ...baseOpts.scales.y, ticks: { ...baseOpts.scales.y.ticks, callback: v => `${v}%` } } } },
    }));
  }

  // ── 품목별 수출 테이블 (top_items은 별도 tr로)
  const itemEl = document.getElementById("trade-item-summary-table");
  if (itemEl) {
    if (!itemRows.length) {
      itemEl.innerHTML = `<p style="color:var(--text-sub);padding:16px;">관세청 품목별 데이터 없음</p>`;
    } else {
      let rows = "";
      for (const r of itemRows) {
        const sc = sigColor(r.signal);
        rows += `<tr style="border-top:2px solid var(--card-border);">
          <td style="font-weight:700;">${html(r.name)}<br><span style="color:var(--text-sub);font-size:.73rem;font-weight:400;">HS ${html(r.hs_group)} · ${html(r.theme)}</span></td>
          <td style="font-weight:600;">${fmtUsd(r.export_usd)}</td>
          <td style="color:${pctColor(r.export_usd_yoy_pct)};font-weight:600;">${fmtPct(r.export_usd_yoy_pct)}</td>
          <td style="color:${pctColor(r.export_kg_yoy_pct)};">${fmtPct(r.export_kg_yoy_pct)}</td>
          <td style="color:${pctColor(r.export_unit_usd_per_kg_yoy_pct)};">${fmtPct(r.export_unit_usd_per_kg_yoy_pct)}</td>
          <td><span style="color:${sc};font-size:.82rem;font-weight:600;">${html(r.signal||"–")}</span></td>
        </tr>`;
        if (Array.isArray(r.top_items)) {
          // 같은 이름 중복 감지 → HS 코드 6자리(XXXX.XX) 병기
          const nameCnt = {};
          r.top_items.forEach(t => { const n = t.name || ""; nameCnt[n] = (nameCnt[n] || 0) + 1; });
          for (const t of r.top_items) {
            const raw = t.name || String(t.hs_code || "");
            const hs  = String(t.hs_code || "");
            const hsTag = (nameCnt[t.name || ""] > 1 && hs.length >= 6)
              ? ` <span style="color:var(--text-sub);font-size:.72rem;">(${hs.slice(0,4)}.${hs.slice(4,6)})</span>`
              : "";
            const display = raw.length > 28 ? raw.slice(0, 26) + "…" : raw;
            const exYoy = t.export_usd_yoy_pct != null
              ? `<span style="color:${pctColor(t.export_usd_yoy_pct)};font-size:.78rem;">${fmtPct(t.export_usd_yoy_pct)}</span>`
              : "–";
            const exMom = t.export_usd_mom_pct != null
              ? `<span style="color:${pctColor(t.export_usd_mom_pct)};font-size:.78rem;">${fmtPct(t.export_usd_mom_pct)}</span><span style="color:var(--text-sub);font-size:.68rem;"> MoM</span>`
              : "–";
            const imYoyTag = t.import_usd_yoy_pct != null
              ? ` <span style="color:${pctColor(t.import_usd_yoy_pct)};font-size:.72rem;">${fmtPct(t.import_usd_yoy_pct)}</span>`
              : "";
            const imStr = t.import_usd != null ? `수입 ${fmtUsd(t.import_usd)}${imYoyTag}` : "";
            rows += `<tr style="background:rgba(255,255,255,.02);">
              <td style="padding-left:20px;color:var(--text-sub);font-size:.82rem;border-left:3px solid var(--card-border);" title="${html(raw)}">└ ${html(display)}${hsTag}</td>
              <td style="color:var(--text-sub);font-size:.82rem;">${fmtUsd(t.export_usd)}</td>
              <td style="font-size:.82rem;">${exYoy}</td>
              <td style="font-size:.82rem;">${exMom}</td>
              <td colspan="2" style="color:var(--text-sub);font-size:.78rem;">${imStr}</td>
            </tr>`;
          }
        }
      }
      itemEl.innerHTML = `<div style="overflow-x:auto;"><table class="data-table" style="font-size:.87rem;"><thead><tr><th>품목</th><th>수출금액</th><th>금액 YoY</th><th>물량 YoY</th><th>단가 YoY</th><th>신호</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    }
  }

  // ── ECOS 월별 테이블 (최근 12개월)
  const ecosEl = document.getElementById("trade-ecos-table");
  if (ecosEl) {
    if (!ecosRows.length) {
      ecosEl.innerHTML = `<p style="color:var(--text-sub);padding:16px;">ECOS 월별 데이터 없음</p>`;
    } else {
      const trows = ecosRows.map((r, i) => {
        const latest = i === 0;
        return `<tr style="${latest ? "background:rgba(16,185,129,.05);" : ""}">
          <td style="white-space:nowrap;font-weight:${latest?700:400};">${fmtMonth(r.month)}${latest ? ' <span style="color:var(--c-green);font-size:.7rem;">▲</span>' : ""}</td>
          <td>${fmtUsd(r.exports_usd)}</td>
          <td style="color:${pctColor(r.exports_usd_yoy_pct)};font-weight:600;">${fmtPct(r.exports_usd_yoy_pct)}</td>
          <td>${fmtUsd(r.imports_usd)}</td>
          <td style="color:${pctColor(r.imports_usd_yoy_pct)};font-weight:600;">${fmtPct(r.imports_usd_yoy_pct)}</td>
          <td style="color:${Number(r.trade_balance_usd)>=0?"var(--c-green)":"var(--c-red)"};font-weight:600;">${fmtUsd(r.trade_balance_usd)}</td>
          <td style="color:${pctColor(r.export_volume_index_yoy_pct)};">${fmtPct(r.export_volume_index_yoy_pct)}</td>
          <td style="color:${pctColor(r.exports_usd_mom_pct)};">${fmtPct(r.exports_usd_mom_pct)}</td>
        </tr>`;
      }).join("");
      ecosEl.innerHTML = `<div style="overflow-x:auto;"><table class="data-table" style="font-size:.85rem;"><thead><tr><th>월</th><th>수출</th><th>수출 YoY</th><th>수입</th><th>수입 YoY</th><th>무역수지</th><th>물량 YoY</th><th>수출 MoM</th></tr></thead><tbody>${trows}</tbody></table></div>`;
    }
  }
}
window.renderTradeImportExportPanel = renderTradeImportExportPanel;

function renderKiwoomDecisionPanel() {
  const flow = window.QUANT_DATA?.kiwoom_flow || {};
  const permission = flow.market_permission || {};
  const candidateRows = Array.isArray(flow.candidate_flow_score?.rows) ? flow.candidate_flow_score.rows : [];
  const entryRows = Array.isArray(flow.entry_timing?.rows) ? flow.entry_timing.rows : [];
  const paperRows = Array.isArray(flow.paper_decisions?.rows) ? flow.paper_decisions.rows : [];
  const portfolio = flow.portfolio_state || {};
  const realtime = flow.realtime_conditions || {};
  const intradayRows = Array.isArray(flow.intraday_market_flow?.rows) ? flow.intraday_market_flow.rows : [];
  const candidateRawRows = Array.isArray(flow.candidate_stock_flow?.rows) ? flow.candidate_stock_flow.rows : [];
  const set = (id, text, color) => { const el = document.getElementById(id); if (!el) return; el.textContent = text ?? "--"; if (color) el.style.color = color; };
  const statusText = String(permission.permission || "UNKNOWN").toUpperCase();
  const noKiwoomReason = (permission.reasons || []).some(r => String(r).includes("kiwoom_not_connected") || String(r).includes("사용 가능 값 없음"));
  const flowUnavailable = permission.status === "no_kiwoom_data" || noKiwoomReason || (!intradayRows.length && !candidateRawRows.length && statusText === "UNKNOWN");
  const permClass = kiwoomClass(statusText);
  const buyEntries = entryRows.filter(r => String(r.paper_decision || r.decision || "").toUpperCase() === "BUY").length;
  const watchEntries = entryRows.filter(r => String(r.paper_decision || r.decision || "").toUpperCase() === "WATCH").length;
  const rejectEntries = entryRows.filter(r => String(r.paper_decision || r.decision || "").toUpperCase() === "REJECT").length;
  const promoted = candidateRows.filter(r => String(r.action_adjustment || "").toUpperCase() === "PROMOTE").length;
  const liveOrder = portfolio.live_order_enabled === true;

  set("kiwoom-permission-metric", statusText, permClass === "on" ? "var(--c-green)" : permClass === "off" ? "var(--c-red)" : "var(--c-yellow)");
  set("kiwoom-candidate-metric", candidateRows.length ? `${promoted}/${candidateRows.length}` : "0");
  set("kiwoom-entry-metric", entryRows.length ? `${buyEntries} BUY` : flowUnavailable ? "입력 없음" : "대기");
  set("kiwoom-live-order-metric", liveOrder ? "ON" : "OFF", liveOrder ? "var(--c-red)" : "var(--c-green)");
  set("kiwoom-panel-meta", `Updated: ${html(permission.timestamp || flow.portfolio_state?.updated_at || "장중 실행 대기")}<br>Source: kiwoom_flow`);
  set("kiwoom-hero-title", flowUnavailable ? "Kiwoom 미접속 - 장중 입력 없음" : statusText === "ON" ? "시장 허가 ON - 후보 수급과 진입 조건만 확인" : statusText === "OFF" ? "시장 허가 OFF - 신규 매수 금지" : "Kiwoom 장중 의사결정은 아직 대기 상태");
  set("kiwoom-hero-verdict", flowUnavailable ? "Market Flow/Candidate Flow 최신 JSON이 없어 Permission, Flow Score, Entry Timing을 갱신할 수 없습니다." : statusText === "UNKNOWN" ? "장중 market_flow가 들어오면 Permission, 후보 Flow Score, Entry Timing이 자동으로 채워집니다." : `Permission=${statusText}, 후보 ${candidateRows.length}개, BUY 진입신호 ${buyEntries}개.`);

  const evidence = document.getElementById("kiwoom-evidence-list");
  if (evidence) {
    const reasons = [...(permission.reasons || []), liveOrder ? "실주문 ON — 즉시 확인 필요" : "실주문 비활성화: 페이퍼 기록만 생성", realtime.status ? `조건검색: ${realtime.status}` : "조건검색 상태 대기"].slice(0, 5);
    evidence.innerHTML = (reasons.length ? reasons : ["장중 첫 실행 전입니다."]).map((r, i) => `<div><span style="color:${i === 0 ? 'var(--accent)' : 'var(--text-sub)'}; font-weight:900;">${i === 0 ? '→' : '•'}</span><span>${html(r)}</span></div>`).join("");
  }

  const wf = document.getElementById("kiwoom-workflow-grid");
  if (wf) {
    const steps = [
      ["1 TR Schema", "Inspector", "TR 컬럼 스냅샷 도구 준비"],
      ["2 Market Flow", intradayRows.length ? `${intradayRows.length} rows` : flowUnavailable ? "입력 없음" : "대기", "KOSPI/KOSDAQ 수급 10분"],
      ["3 Candidate Flow", candidateRawRows.length ? `${candidateRawRows.length} rows` : flowUnavailable ? "입력 없음" : "대기", "BUY/WATCH/보유 종목 15분"],
      ["4 Permission", statusText, `score ${permission.score ?? "--"}`],
      ["5 Flow Score", candidateRows.length ? `${candidateRows.length} scored` : "0 scored", `${promoted} PROMOTE`],
      ["6 Entry", entryRows.length ? `${buyEntries}/${watchEntries}/${rejectEntries}` : "대기", "BUY/WATCH/REJECT"],
      ["7 Paper Log", `${paperRows.length} rows`, "실험 의사결정 기록"],
      ["8 Safety", liveOrder ? "LIVE ON" : "LIVE OFF", `holdings ${portfolio.holdings_count ?? "--"}`],
    ];
    wf.innerHTML = steps.map(s => `<div class="kiwoom-step"><div class="label">${html(s[0])}</div><div class="value">${html(s[1])}</div><div class="sub">${html(s[2])}</div></div>`).join("");
  }
  const workflowStatus = document.getElementById("kiwoom-workflow-status");
  if (workflowStatus) { workflowStatus.textContent = entryRows.length ? "LIVE DATA" : flowUnavailable ? "NO DATA" : "READY"; workflowStatus.className = `kiwoom-status ${entryRows.length ? 'on' : 'unknown'}`; }
  const orderStatus = document.getElementById("kiwoom-order-status");
  if (orderStatus) { orderStatus.textContent = liveOrder ? "LIVE ORDER ON" : "LIVE ORDER OFF"; orderStatus.className = `kiwoom-status ${liveOrder ? 'off' : 'on'}`; }
  const entryStatus = document.getElementById("kiwoom-entry-status");
  if (entryStatus) { entryStatus.textContent = buyEntries ? `${buyEntries} BUY` : entryRows.length ? "WATCH" : "WAIT"; entryStatus.className = `kiwoom-status ${buyEntries ? 'buy' : 'watch'}`; }

  const safety = document.getElementById("kiwoom-safety-panel");
  if (safety) {
    const items = [
      ["보유", portfolio.holdings_count ?? "--", "latest_holdings"],
      ["체결", portfolio.trades_count ?? "--", "latest_trades"],
      ["잔고 age", portfolio.holdings_age_minutes != null ? `${portfolio.holdings_age_minutes}m` : "--", "staleness"],
      ["조건식", realtime.status || "--", realtime.message || "HTS 조건식 대기"],
    ];
    safety.innerHTML = items.map(i => `<div class="kiwoom-step"><div class="label">${html(i[0])}</div><div class="value">${html(i[1])}</div><div class="sub">${html(i[2])}</div></div>`).join("");
  }

  const entryBody = document.getElementById("kiwoom-entry-table");
  if (entryBody) {
    const rows = entryRows.slice(0, 12);
    const emptyEntryMessage = flowUnavailable ? "Kiwoom 미접속 또는 최신 Market/Candidate Flow 없음. HTS 로그인과 장중 수집 배치를 확인하세요." : "장중 후보 수급이 들어오면 Entry Timing과 Paper Decision이 여기에 표시됩니다.";
    entryBody.innerHTML = rows.length ? rows.map(r => `<tr><td><b>${html(r.name || r.ticker || "-")}</b><br><span style="color:var(--text-sub); font-size:0.75rem;">${html(r.ticker || "")}</span></td><td>${html(r.market_permission || "-")}</td><td>${html(r.flow_bucket || "-")}<br><span style="color:var(--text-sub);">${html(r.flow_score ?? "")}</span></td><td>${html(r.entry_state || "-")}</td><td><span class="kiwoom-status ${kiwoomClass(r.paper_decision)}">${html(r.paper_decision || "-")}</span><br><span style="color:var(--text-sub); font-size:0.76rem;">${html((r.reasons || []).join(' / '))}</span></td></tr>`).join("") : `<tr><td colspan="5" style="color:var(--text-sub); padding:18px;">${html(emptyEntryMessage)}</td></tr>`;
  }

  const healthBody = document.getElementById("kiwoom-health-table");
  if (healthBody) {
    const health = [
      ["Market Flow", intradayRows.length ? "ok" : "waiting", intradayRows.length, flow.intraday_market_flow?.updated_at || permission.timestamp || "--"],
      ["Candidate Flow", candidateRawRows.length ? "ok" : "waiting", candidateRawRows.length, flow.candidate_stock_flow?.updated_at || "--"],
      ["Permission", permission.status || statusText, permission.permission || "--", permission.timestamp || "--"],
      ["Flow Score", candidateRows.length ? "ok" : "waiting", candidateRows.length, flow.candidate_flow_score?.updated_at || "--"],
      ["Portfolio", portfolio.status || "--", portfolio.holdings_count ?? "--", portfolio.updated_at || "--"],
      ["Conditions", realtime.status || "--", (realtime.conditions || []).length, realtime.updated_at || "--"],
    ];
    healthBody.innerHTML = health.map(h => `<tr><td>${html(h[0])}</td><td><span class="kiwoom-status ${kiwoomClass(h[1])}">${html(h[1])}</span></td><td>${html(h[2])}</td><td>${html(h[3])}</td></tr>`).join("");
  }
}
window.renderKiwoomDecisionPanel = renderKiwoomDecisionPanel;


// ── Decision OS v2: 탭별 결론-근거-원자료 구조 ───────────────────────────────
function renderDecisionOSV2() {
  const d = window.QUANT_DATA || {};
  const nd = window.NEWS_DATA || {};
  const setText = (id, value, color) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value ?? "--";
    if (color) el.style.color = color;
  };
  const setList = (id, rows) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = (rows || []).filter(Boolean).slice(0, 5).map((row, i) =>
      `<div><span style="color:${i === 0 ? 'var(--accent)' : 'var(--text-sub)'}; font-weight:900;">${i === 0 ? '→' : '•'}</span><span>${html(row)}</span></div>`
    ).join("");
  };
  const fmt = (n, digits = 0) => Number.isFinite(Number(n)) ? Number(n).toFixed(digits) : "--";
  const pct = (n) => Number.isFinite(Number(n)) ? Math.round(Number(n) * 100) : null;
  const stockRows = Array.isArray(d.stock_attractiveness?.rows) ? d.stock_attractiveness.rows : [];
  const bRows = stockRows.filter(r => r.project_universe_b === 1 || r.universe_b === 1 || r.market_universe === "B_PROJECT_DEFAULT");
  const universe = bRows.length ? bRows : stockRows;
  const decision = (r) => String(r.model_decision || "-").toUpperCase();
  const buyCount = universe.filter(r => decision(r) === "BUY").length;
  const watchCount = universe.filter(r => decision(r) === "WATCH").length;
  const rejectCount = universe.filter(r => decision(r) === "REJECT").length;
  const topScore = Math.max(0, ...universe.map(r => Number(r.market_attractiveness_score || 0)).filter(Number.isFinite));
  const topStock = [...universe].sort((a,b) => Number(b.market_attractiveness_score || 0) - Number(a.market_attractiveness_score || 0))[0];

  const regimeRows = d.macro_factors?.market_macro_regime_month || [];
  const lr = regimeRows.slice(-1)[0] || {};
  const isRiskOn = lr.market_regime === "risk_on";
  const k60 = Number(lr.korea_kospi_ret_60d_pct);
  const dgs10 = Number(d.macro?.DGS10?.slice(-1)[0]?.DGS10);
  const flowLatest = d.money_flow?.market_funds_trend?.slice(-1)[0] || {};
  const flowDate = flowLatest.date || lr.period || "--";
  const _mn = v => (v != null && v !== "") ? Number(v) : null;
  const dgs2 = _mn(d.macro?.DGS2?.slice(-1)[0]?.DGS2);
  const spread10y2y = (Number.isFinite(dgs10) && dgs2 != null && isFinite(dgs2)) ? dgs10 - dgs2 : null;
  const hy = _mn(d.macro?.BAMLH0A0HYM2?.slice(-1)[0]?.BAMLH0A0HYM2);
  const usdkrw = _mn(d.macro?.USD_KRW?.slice(-1)[0]?.Close);
  const vix = _mn(d.macro?.VIX?.slice(-1)[0]?.Close);
  const stlfsi = _mn(d.macro?.STLFSI4?.slice(-1)[0]?.STLFSI4);
  const riskFlags = [
    lr.risk_off_flag ? "Risk-OFF 레짐" : null,
    lr.dollar_pressure_flag ? "달러 압력" : null,
    Number(lr.vix_zscore_252d || 0) > 1.2 ? "VIX 고압" : null,
    Number.isFinite(k60) && k60 < 0 ? "KOSPI 60d 음수" : null,
    buyCount === 0 ? "BUY 후보 부재" : null,
  ].filter(Boolean);
  const riskLevel = riskFlags.length >= 3 ? "HIGH" : riskFlags.length >= 1 ? "MID" : "LOW";
  const riskColor = riskLevel === "HIGH" ? "var(--c-red)" : riskLevel === "MID" ? "var(--c-yellow)" : "var(--c-green)";
  const permission = riskLevel === "HIGH" ? "제한" : riskLevel === "MID" ? "조건부" : "허용";

  // 종목 / Action Board
  setText("analysis-buy-count", buyCount, buyCount ? "var(--c-green)" : "var(--text-sub)");
  setText("analysis-watch-count", watchCount, "var(--c-yellow)");
  setText("analysis-reject-count", rejectCount, "var(--c-red)");
  setText("analysis-top-score", topScore ? Math.round(topScore * 100) : "--", "var(--accent)");
  setText("analysis-hero-title", buyCount ? `BUY ${buyCount} · WATCH ${watchCount} · 조건부 진입` : `WATCH ${watchCount} · 방어 우선`, buyCount ? "var(--text-heading)" : "var(--c-yellow)");
  setText("analysis-hero-verdict", topStock ? `최상위 후보는 ${topStock.name || topStock.ticker} (${Math.round(Number(topStock.market_attractiveness_score || 0)*100)}점). 시장 위험도 ${riskLevel}이므로 진입 조건 확인 후 행동.` : "종목 데이터가 아직 로딩되지 않았습니다.");
  setList("analysis-evidence-list", [
    buyCount ? `BUY 후보 ${buyCount}개 — 단, 시장 위험도 ${riskLevel}` : "즉시 BUY보다 WATCH/관찰 우선",
    `WATCH ${watchCount}개는 눌림/돌파 조건 충족 시 재평가`,
    `REJECT ${rejectCount}개는 신규 진입 제외`,
    topStock ? `최상위: ${topStock.name || topStock.ticker}` : null,
    "세부 점수보다 진입 조건·손절 기준을 먼저 확인",
  ]);

  // 시장
  setText("macro-regime-metric", isRiskOn ? "Risk-ON" : "Risk-OFF", isRiskOn ? "var(--c-green)" : "var(--c-yellow)");
  setText("macro-kospi-metric", Number.isFinite(k60) ? `${k60 >= 0 ? "+" : ""}${k60.toFixed(1)}%` : "--", Number.isFinite(k60) && k60 >= 0 ? "var(--c-green)" : "var(--c-red)");
  setText("macro-rate-metric", Number.isFinite(dgs10) ? `${dgs10.toFixed(2)}%` : "--", "var(--c-yellow)");
  setText("macro-flow-date", flowDate === "--" ? "--" : String(flowDate).slice(5), "var(--accent)");
  setText("macro-spread-metric", (spread10y2y != null && isFinite(spread10y2y)) ? `${spread10y2y >= 0 ? "+" : ""}${spread10y2y.toFixed(2)}%` : "--", (spread10y2y != null && isFinite(spread10y2y)) ? (spread10y2y >= 0 ? "var(--c-green)" : "var(--c-red)") : null);
  setText("macro-hy-metric", (hy != null && isFinite(hy)) ? `${hy.toFixed(2)}%` : "--", (hy != null && isFinite(hy)) ? (hy <= 3 ? "var(--c-green)" : hy <= 5 ? "var(--c-yellow)" : "var(--c-red)") : null);
  setText("macro-usdkrw-metric", (usdkrw != null && isFinite(usdkrw)) ? Math.round(usdkrw).toLocaleString() : "--", "var(--c-yellow)");
  setText("macro-vix-metric", (vix != null && isFinite(vix)) ? vix.toFixed(1) : "--", (vix != null && isFinite(vix)) ? (vix <= 20 ? "var(--c-green)" : vix <= 30 ? "var(--c-yellow)" : "var(--c-red)") : null);
  setText("macro-stlfsi-metric", (stlfsi != null && isFinite(stlfsi)) ? stlfsi.toFixed(2) : "--", (stlfsi != null && isFinite(stlfsi)) ? (stlfsi <= 0 ? "var(--c-green)" : stlfsi <= 1 ? "var(--c-yellow)" : "var(--c-red)") : null);
  setText("macro-hero-title", permission === "허용" ? "시장은 선별 매수를 허용" : permission === "조건부" ? "시장은 조건부 매수만 허용" : "시장은 신규매수를 제한", riskColor);
  setText("macro-hero-verdict", `현재 레짐 ${isRiskOn ? "Risk-ON" : "Risk-OFF"}, 위험 플래그 ${riskFlags.length}개. 수급/금리/환율 확인 후 종목 진입 강도를 조절합니다.`);
  setList("macro-evidence-list", [
    isRiskOn ? "레짐은 공격 가능 상태" : "레짐은 방어 우선 상태",
    Number.isFinite(k60) ? `KOSPI 60일 수익률 ${k60 >= 0 ? "+" : ""}${k60.toFixed(1)}%` : null,
    Number.isFinite(dgs10) ? `미 10년 금리 ${dgs10.toFixed(2)}%` : null,
    (spread10y2y != null && isFinite(spread10y2y)) ? `장단기 금리차(10Y-2Y) ${spread10y2y >= 0 ? "+" : ""}${spread10y2y.toFixed(2)}%` : null,
    (hy != null && isFinite(hy)) ? `HY 스프레드 ${hy.toFixed(2)}%${hy > 5 ? " — 신용 위험 경고" : ""}` : null,
    (usdkrw != null && isFinite(usdkrw)) ? `USD/KRW ${Math.round(usdkrw).toLocaleString()}원` : null,
    (vix != null && isFinite(vix)) ? `VIX ${vix.toFixed(1)}${vix > 30 ? " — 공포 구간" : vix > 20 ? " — 경계 구간" : " — 안정 구간"}` : null,
    (stlfsi != null && isFinite(stlfsi)) ? `금융 스트레스(STLFSI) ${stlfsi.toFixed(2)}` : null,
    lr.dollar_pressure_flag ? "달러 압력 플래그 ON — 외국인 수급 확인" : "달러 압력 플래그 제한적",
    `수급 최신일 ${flowDate}`,
  ]);

  // 리스크
  setText("risk-level-metric", riskLevel, riskColor);
  setText("risk-buy-permission", permission, riskColor);
  setText("risk-flags-count", riskFlags.length, riskColor);
  setText("risk-date-metric", flowDate === "--" ? "--" : String(flowDate).slice(5), "var(--accent)");
  setText("risk-hero-title", riskLevel === "HIGH" ? "브레이크 우선: 신규매수 제한" : riskLevel === "MID" ? "조건부 진입: 크기 줄이고 확인" : "위험 낮음: 선별 진입 가능", riskColor);
  setText("risk-hero-verdict", `위험 플래그 ${riskFlags.length}개. 위험등급이 MID 이상이면 포지션 크기를 줄이고 Action Board 후보도 WATCH 중심으로 봅니다.`);
  setList("risk-evidence-list", riskFlags.length ? riskFlags.concat(["위험이 낮아질 때까지 추격매수 금지", "포지션 사이징에서 손절 기준 먼저 계산"]) : ["현재 핵심 위험 플래그는 제한적", "그래도 종목별 유동성·손절 기준은 필수", "과열 차트는 아래 버블 지표에서 확인"]);

  // 검증 / Model Trust
  const factors = d.regression?.factor_ic?.factors || [];
  const validFactors = factors.filter(f => f.significant && f.ic_mean != null && Math.abs(Number(f.ic_mean)) >= 0.02).length;
  const factorTotal = factors.length || 0;
  const trustScore = factorTotal ? Math.round((validFactors / factorTotal) * 100) : null;
  const dataQualityRows = d.factor_master?.source_quality || d.data_quality?.sources || [];
  const coverage = universe.length || stockRows.length || 0;
  setText("quant-trust-score", trustScore == null ? "--" : `${trustScore}`, trustScore == null ? null : trustScore >= 60 ? "var(--c-green)" : trustScore >= 35 ? "var(--c-yellow)" : "var(--c-red)");
  setText("quant-valid-factors", factorTotal ? `${validFactors}/${factorTotal}` : "--", "var(--accent)");
  setText("quant-data-score", dataQualityRows.length ? "확인" : "부분", dataQualityRows.length ? "var(--c-green)" : "var(--c-yellow)");
  setText("quant-coverage", coverage ? coverage.toLocaleString() : "--", "var(--text-heading)");
  setText("quant-hero-title", trustScore == null ? "검증 데이터 로딩 중" : trustScore >= 60 ? "모델 신뢰도 양호" : trustScore >= 35 ? "모델 신뢰도 주의" : "모델 신뢰도 낮음", trustScore >= 60 ? "var(--c-green)" : trustScore >= 35 ? "var(--c-yellow)" : "var(--c-red)");
  setList("quant-evidence-list", [
    factorTotal ? `유효 팩터 ${validFactors}/${factorTotal}` : "팩터 IC 데이터 확인 필요",
    trustScore != null ? `모델 신뢰도 ${trustScore}/100` : null,
    coverage ? `현재 커버리지 ${coverage.toLocaleString()}개 종목` : null,
    "IC 약화 팩터가 있으면 후보 비중 축소",
    "데이터 최신성/결측 페널티를 먼저 확인",
  ]);

  // 뉴스
  const summary = nd.summary || {};
  const posNews = Number(summary.positive_stocks || 0);
  const negNews = Number(summary.negative_stocks || 0);
  const headlines = Number(summary.total_headlines || (nd.headlines || []).length || 0);
  const shock = Math.min(posNews + negNews, (nd.sentiment || []).filter(x => x.news_sentiment_bucket && x.news_sentiment_bucket !== "neutral").length || posNews + negNews);
  setText("news-positive-metric", posNews || "0", "var(--c-green)");
  setText("news-negative-metric", negNews || "0", "var(--c-red)");
  setText("news-headlines-metric", headlines ? headlines.toLocaleString() : "0", "var(--accent)");
  setText("news-shock-metric", shock || "0", shock ? "var(--c-yellow)" : "var(--text-sub)");
  setText("news-hero-title", negNews > posNews ? "뉴스 리스크 우위" : posNews > negNews ? "뉴스 분위기 양호" : "뉴스 영향 중립", negNews > posNews ? "var(--c-red)" : posNews > negNews ? "var(--c-green)" : "var(--text-heading)");
  setList("news-evidence-list", [
    `긍정 ${posNews} / 부정 ${negNews} / 헤드라인 ${headlines.toLocaleString()}건`,
    "뉴스는 단독 매수 사유가 아니라 수급·가격 확인용",
    "긍정 뉴스인데 가격/수급 반응이 없으면 노이즈 처리",
    "부정 뉴스 + 수급 이탈이면 리스크 후보로 이동",
  ]);

  // 리포트: 현재 정적/렌더링 데이터가 섞여 있어 DOM 기반 보조 집계
  const alertRows = document.querySelectorAll("#alerts-container-body tr").length;
  const reportCards = document.querySelectorAll("#reports-container-grid .report-card, #reports-container-grid > *").length;
  const analystCards = document.querySelectorAll("#analysts-container .analyst-card, #analysts-container > *").length;
  setText("reports-up-count", "확인", "var(--c-green)");
  setText("reports-down-count", "확인", "var(--c-red)");
  setText("reports-items-count", (alertRows + reportCards + analystCards) || "--", "var(--accent)");
  setText("reports-alignment", buyCount ? "대조" : "보류", buyCount ? "var(--c-yellow)" : "var(--text-sub)");
  setList("reports-evidence-list", [
    "모델 BUY/WATCH 후보와 리포트 방향이 같은지 먼저 확인",
    "목표가 하향/의견 하향은 후보 점수와 별도 리스크로 취급",
    "리포트는 읽을거리보다 Action Board 검증 증거",
    alertRows ? `투자의견 변동 행 ${alertRows}개 렌더링` : "투자의견 변동 데이터 로딩/필터 확인",
  ]);

  // 차트
  const selected = document.querySelectorAll("#stock-checklist input[type='checkbox']:checked").length;
  const activeMode = document.getElementById("btn-chart-mode-price")?.classList.contains("active") ? "가격" : "상대";
  const maActive = document.querySelectorAll("#ma-buttons-container .filter-btn.active").length;
  setText("chart-selected-count", selected || "--", selected ? "var(--accent)" : "var(--text-sub)");
  setText("chart-mode-metric", activeMode, "var(--accent)");
  setText("chart-ma-metric", maActive || "0", maActive ? "var(--c-green)" : "var(--text-sub)");
  setText("chart-entry-metric", riskLevel === "HIGH" ? "보류" : "조건부", riskLevel === "HIGH" ? "var(--c-red)" : "var(--c-yellow)");
}
window.renderDecisionOSV2 = renderDecisionOSV2;

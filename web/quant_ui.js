document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  setTimeout(() => {
    if (!window.QUANT_DATA) return;
    renderMacroChart();
    renderMoneyFlowChart();
    renderBreadthCharts();
    renderStockAttractiveness();
    renderSectorMap();
    renderRegimeCard();
    renderScorecard();
    renderRegressionPanel();
    renderFactorValidation();
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
  window.scrollTo({ top: 0, behavior: "smooth" });

  // 금리/채권 탭: hidden 상태로 그려진 차트들 크기 재계산
  if (targetId === "macro-leading") { setTimeout(renderLeadingIndicatorCharts, 50); }
  if (targetId === "macro-industry") { setTimeout(renderIndustryCharts, 50); }
  if (targetId === "macro-sector-momentum") { setTimeout(renderSectorMomentumCharts, 50); }
  if (targetId === "macro-scorecard") { setTimeout(() => { renderRegimeCard(); renderScorecard(); }, 50); }
  if (targetId === "macro-regression") { setTimeout(renderRegressionPanel, 50); }
  if (targetId === "quant-factor-validation") { setTimeout(renderFactorValidation, 50); }
  if (targetId === "analysis-market-attractiveness") { setTimeout(renderStockAttractiveness, 50); }

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
  createLineChart("macro-rates-charts-dynamic", "미국 10년물 국채 금리", macroData.TNX, "Date", "Close", "#ef4444");
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
        const recent = ft.slice(-20);
        const dateKey = Object.keys(recent[0])[0];
        const keys = Object.keys(recent[0]);
        // 외국인=keys[2], 기관=keys[3] (인코딩 무관하게 인덱스 사용)
        const chart = new Chart(ctx, {
          type: "bar",
          data: {
            labels: recent.map(r => String(r[dateKey] || "").slice(0, 8)),
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
    // 고객예탁금 추이
    const mf = flowData.market_funds_trend;
    if (Array.isArray(mf) && mf.length) {
      const ctx2 = createChartCanvas("macro-index-futures-charts", "고객예탁금 & 신용잔고 추이 (억원)");
      if (ctx2) {
        const recent = mf.slice(-20);
        const keys = Object.keys(recent[0]);
        const chart2 = new Chart(ctx2, {
          type: "line",
          data: {
            labels: recent.map(r => String(r[keys[0]] || "").slice(0, 8)),
            datasets: [
              { label: "고객예탁금", data: recent.map(r => Math.round((parseFloat(r[keys[1]]) || 0) / 10000)), borderColor: "#10b981", backgroundColor: "#10b98120", borderWidth: 2, fill: true, tension: 0.3, pointRadius: 2 },
              { label: "신용잔고", data: recent.map(r => Math.round((parseFloat(r[keys[3]]) || 0) / 10000)), borderColor: "#ef4444", backgroundColor: "#ef444420", borderWidth: 2, fill: false, tension: 0.3, pointRadius: 2 }
            ]
          },
          options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#d1d5db" } } },
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
  createBarChart("macro-index-charts", "KOSPI 투자자별 순매수 추이 (1개월)", flowData.market_trading_value_kospi_20y, "date", investorSeries, 20, "line");
  createBarChart("macro-index-charts", "KOSDAQ 투자자별 순매수 추이 (1개월)", flowData.market_trading_value_kosdaq_20y, "date", investorSeries, 20, "line");
  createBarChart("macro-index-charts", "고객예탁금 및 신용잔고", flowData.market_funds_trend, "날짜_날짜", [
    { label: "고객예탁금", key: "고객예탁금_고객예탁금", color: "#f59e0b" },
    { label: "신용잔고", key: "신용잔고_신용잔고", color: "#ec4899" },
  ], 120, "line");

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
  ranked.forEach((item, idx) => ranks.set(item.row.ticker, idx + 1));
  return { ranks, validCount: ranked.length };
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

function renderScenarioToggles() {
  const wrap = document.getElementById("regression-scenario-toggles");
  const detail = document.getElementById("regression-scenario-detail");
  if (!wrap || !detail) return;
  wrap.innerHTML = Object.entries(STOCK_SCENARIOS).map(([key, s]) => `
    <button class="filter-btn ${window.activeStockScenario === key ? "active" : ""}" onclick="setStockScenario('${key}')" style="height:auto; display:flex; flex-direction:column; align-items:flex-start; gap:4px; padding:10px 12px;">
      <span style="font-weight:800; color:var(--text-heading);">${html(s.label)}</span>
      <span style="font-size:0.75rem; color:var(--text-sub);">${html(s.horizon)}</span>
    </button>
  `).join("");
  const s = STOCK_SCENARIOS[window.activeStockScenario] || STOCK_SCENARIOS.market_attractiveness_score;
  detail.innerHTML = `
    <div style="font-weight:800; color:var(--text-heading); margin-bottom:5px;">${html(s.label)} · ${html(s.horizon)}</div>
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

  const asOf = document.getElementById("regression-as-of");
  if (asOf) {
    const asOfDate = new Date(reg.as_of);
    const monthsStale = (new Date() - asOfDate) / (1000 * 60 * 60 * 24 * 30);
    const staleWarn = monthsStale > 2 ? ` <span style="color:#f59e0b; font-weight:700;">⚠ ${Math.floor(monthsStale)}개월 미갱신</span>` : "";
    asOf.innerHTML = `분석 기준: ${reg.as_of}${staleWarn}`;
  }

  const mt = reg.market_timing || {};
  const fi = reg.factor_ic || {};
  const re = reg.regime || {};

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
          <div style="font-size:0.78rem; color:var(--text-sub); margin-top:2px;">예측 ${mt.pred_pct != null ? (mt.pred_pct >= 0 ? "+" : "") + mt.pred_pct.toFixed(2) + "%" : "-"} / R² ${mt.r2 != null ? (mt.r2 * 100).toFixed(1) + "%" : "-"} · ${mt.periods || 0}개월 기간</div>
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
      return `<div style="display:flex; align-items:center; gap:8px; font-size:0.77rem;">
        <div style="min-width:90px; color:var(--text-sub); text-align:right;">${f.label || f.key}</div>
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
  const { ranks: scenarioRanks, validCount: scenarioValidCount } = buildScenarioRanks(rows, scoreKey);
  renderScenarioBacktestSummary(scoreKey, scenarioValidCount, rows.length);

  let filtered = rows.filter(row => {
    if (term && !(`${row.name || ""} ${row.ticker || ""}`.toLowerCase().includes(term))) return false;
    if (market === "KOSPI200_PROXY" && !row.kospi200_proxy) return false;
    if (market !== "all" && market !== "KOSPI200_PROXY" && row.market !== market) return false;
    if (size !== "all" && row.size_bucket !== size) return false;
    if (sector !== "all" && row.sector !== sector) return false;
    return passesStockQuickFilters(row);
  });

  filtered.sort((a, b) => (stockNum(b[sortKey]) ?? -Infinity) - (stockNum(a[sortKey]) ?? -Infinity));
  const display = filtered.slice(0, 300);
  const scenario = STOCK_SCENARIOS[window.activeStockScenario] || STOCK_SCENARIOS.market_attractiveness_score;

  tbody.innerHTML = display.map(row => {
    const score = scenarioScore(row);
    const rank = scenarioRanks.get(row.ticker);
    const scorePct = score == null ? "-" : `${(score * 100).toFixed(1)}점`;
    const scoreColor = score == null ? "var(--text-sub)" : score >= 0.65 ? "#10b981" : score >= 0.5 ? "#f59e0b" : "#ef4444";
    const growthThis = fmtPctValue(row.this_year_op_growth_pct);
    const growthNext = fmtPctValue(row.next_year_op_growth_pct);
    const badges = [row.market, row.size_bucket, row.kospi200_proxy ? "KOSPI200근사" : null].filter(Boolean).map(v => `<span class="tag">${html(v)}</span>`).join(" ");
    return `
      <tr onclick="openStockModal('${html(row.name || row.ticker)}')" style="cursor:pointer;" onmouseover="this.style.background='var(--tr-hover-bg)'" onmouseout="this.style.background=''">
        <td>
          <div class="company-name" style="font-size:0.95rem; font-weight:800;">${html(row.name || row.ticker)}</div>
          <div class="company-code" style="font-size:0.75rem; color:var(--text-sub);">${html(row.ticker)} · ${html(row.sector || "업종 미분류")}</div>
          <div style="margin-top:5px; display:flex; gap:4px; flex-wrap:wrap;">${badges}</div>
        </td>
        <td>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; font-size:0.8rem; color:var(--text-sub);">
            <div>PER <b style="color:#3b82f6;">${fmtNum(row.per ?? row.consensus_per)}</b></div>
            <div>PBR <b style="color:#8b5cf6;">${fmtNum(row.pbr ?? row.consensus_pbr)}</b></div>
            <div>ROE <b style="color:#10b981;">${row.roe == null ? "-" : `${(row.roe * 100).toFixed(1)}%`}</b></div>
            <div>부채 <b>${row.debt_ratio == null ? "-" : `${(row.debt_ratio * 100).toFixed(0)}%`}</b></div>
            <div>FCF/자산 <b style="color:#10b981;">${row.fcf_to_assets == null ? "-" : `${(row.fcf_to_assets * 100).toFixed(1)}%`}</b></div>
            <div>BS품질 <b>${row.balance_sheet_quality_score == null ? "-" : `${(row.balance_sheet_quality_score * 100).toFixed(0)}점`}</b></div>
            <div>CF품질 <b>${row.cashflow_quality_score == null ? "-" : `${(row.cashflow_quality_score * 100).toFixed(0)}점`}</b></div>
            <div>이익안정 <b>${row.earnings_stability_score == null ? "-" : `${(row.earnings_stability_score * 100).toFixed(0)}점`}</b></div>
            <div>DIV <b>${fmtNum(row.div_yield)}</b></div>
          </div>
        </td>
        <td>${fmtCompact(row.recent_op_profit, "")}</td>
        <td><b style="color:#10b981;">${fmtCompact(row.this_year_op_profit_est, "")}</b>${growthThis}</td>
        <td><b style="color:#3b82f6;">${fmtCompact(row.next_year_op_profit_est, "")}</b>${growthNext}</td>
        <td>
          <div>시총 <b>${fmtCompact(row.market_cap)}</b></div>
          <div style="font-size:0.75rem; color:var(--text-sub);">거래대금 ${fmtCompact(row.trading_value)}</div>
          <div style="font-size:0.75rem; color:var(--text-sub);">${html(row.market || "")} ${row.market_cap_rank ? `#${row.market_cap_rank}` : ""}</div>
        </td>
        <td>
          ${(() => {
            const rs = row.regime_adj_score;
            if (rs == null) return '<div style="color:var(--text-sub); font-size:0.8rem;">-</div>';
            const c = rs >= 0.65 ? "#10b981" : rs >= 0.45 ? "#f59e0b" : "#ef4444";
            return `<div style="font-weight:900; color:${c}; font-size:0.95rem;">${(rs * 100).toFixed(1)}</div><div style="font-size:0.68rem; color:var(--text-sub);">레짐조정</div>`;
          })()}
        </td>
        <td>
          <div style="font-weight:900; color:${scoreColor};">${scorePct}</div>
          <div style="font-size:0.75rem; color:var(--text-sub); margin-top:3px;">${html(scenario.label)}</div>
          <div style="font-size:0.72rem; color:var(--text-sub); margin-top:3px;">전체순위 ${rank ? `#${rank.toLocaleString("ko-KR")}/${scenarioValidCount.toLocaleString("ko-KR")}` : "산정불가"}</div>
          <div style="font-size:0.72rem; color:var(--text-sub); margin-top:3px;">종합 ${row.market_attractiveness_score == null ? "-" : (row.market_attractiveness_score * 100).toFixed(1)}</div>
        </td>
      </tr>
    `;
  }).join("") || '<tr><td colspan="8" style="text-align:center; padding:22px; color:var(--text-sub);">조건에 맞는 종목이 없습니다.</td></tr>';

  const count = document.getElementById("stock-attractiveness-count");
  if (count) count.textContent = `검색 결과 ${filtered.length.toLocaleString("ko-KR")}개 / 화면 표시 ${display.length.toLocaleString("ko-KR")}개 · ${scenario.label} 산정 가능 ${scenarioValidCount.toLocaleString("ko-KR")}개`;
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

  // ── OECD 복합선행지수 (CLI) — 9개국
  createNormalizedLineChart("macro-leading-cli-charts", "한국 CLI (OECD 진폭조정)", macro.KOR_CLI, "KORLOLITONOSTSAM", "#10b981");
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
  const tnx = latestValue(macro.TNX, "Close");
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
window.renderFactorValidation = renderFactorValidation;
window.renderFactorValidationTopn = renderFactorValidationTopn;
window.renderFactorTopnQuintile = renderFactorTopnQuintile;
window.renderFactorValidationCurrent = renderFactorValidationCurrent;

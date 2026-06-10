document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  setTimeout(() => {
    if (!window.QUANT_DATA) return;
    renderMacroChart();
    renderMoneyFlowChart();
    renderBreadthCharts();
    renderDartTable();
    renderEpsTable();
    renderSectorMap();
    renderRegimeCard();
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

  // 금리/채권 탭: hidden 상태로 그려진 차트들 크기 재계산
  if (targetId === "macro-leading") { setTimeout(renderLeadingIndicatorCharts, 50); }
  if (targetId === "macro-industry") { setTimeout(renderIndustryCharts, 50); }
  if (targetId === "quant-sector-momentum") { setTimeout(renderSectorMomentumCharts, 50); }

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
  const fearGreed = window.QUANT_DATA?.sentiment?.fear_greed || null;
  const fearValRaw = fearGreed?.value ?? null;
  const fearVal = fearValRaw === null ? null : Number(fearValRaw);
  const fearDesc = fearGreed?.description ? ` (${fearGreed.description})` : "";
  const dxy = latestValue(macro.DXY, "Close");
  const tnx = latestValue(macro.TNX, "Close");
  const dgs10 = latestValue(macro.DGS10, "DGS10");
  const dgs2 = latestValue(macro.DGS2, "DGS2");
  const hy = latestValue(macro.BAMLH0A0HYM2, "BAMLH0A0HYM2");
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
  const nfci       = latestValue(macro.NFCI, "NFCI");
  const korCli     = latestValue(macro.KOR_CLI, "KORLOLITONOSTSAM");
  const aaiiSpread = latestValue(macro.aaii_bull_bear, "value");

  const yieldSpread = dgs10 !== null && dgs2 !== null ? dgs10 - dgs2 : null;
  const signal = {
    dxy:     dxy === null ? null : dxy < 99 ? 1 : dxy < 102 ? 0 : -1,
    tnx:     tnx === null ? null : tnx < 4.2 ? 1 : tnx < 4.5 ? 0 : -1,
    spread:  yieldSpread === null ? null : yieldSpread > 0.5 ? 1 : yieldSpread > 0 ? 0 : -1,
    hy:      hy === null ? null : hy < 3.5 ? 1 : hy < 4.5 ? 0 : -1,
    fear:    fearVal === null || Number.isNaN(fearVal) ? null : fearVal > 70 ? 1 : fearVal > 30 ? 0 : -1,
    unrate:  unrate === null ? null : unrate < 4 ? 1 : unrate < 5 ? 0 : -1,
    m2:      m2Yoy === null ? null : m2Yoy > 3 ? 1 : m2Yoy > -1 ? 0 : -1,
    cpi:     cpiYoy === null ? null : cpiYoy < 2 ? 1 : cpiYoy < 3.5 ? 0 : -1,
    usdKrw:  usdKrw === null ? null : usdKrw < 1350 ? 1 : usdKrw < 1500 ? 0 : -1,
    exports: exportsYoy === null ? null : exportsYoy > 5 ? 1 : exportsYoy > -5 ? 0 : -1,
    vix:     vix === null ? null : vix < 20 ? 1 : vix < 30 ? 0 : -1,
    nfci:    nfci === null ? null : nfci < -0.1 ? 1 : nfci < 0.5 ? 0 : -1,
    korCli:  korCli === null ? null : korCli > 100.2 ? 1 : korCli > 99.5 ? 0 : -1,
    aaii:    aaiiSpread === null ? null : aaiiSpread < -15 ? 1 : aaiiSpread < 15 ? 0 : -1,
  };

  const pct = (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  const indicators = [
    { name: "달러 인덱스",      value: dxy,         fmt: (v) => v.toFixed(2),                         sig: signal.dxy,     criterion: "↑ <99  →  99~102  ↓ >102" },
    { name: "미국 10년물 금리",  value: tnx,         fmt: (v) => `${v.toFixed(2)}%`,                   sig: signal.tnx,     criterion: "↑ <4.2%  →  4.2~4.5%  ↓ >4.5%" },
    { name: "장단기 금리차",    value: yieldSpread, fmt: (v) => `${v.toFixed(2)}%`,                   sig: signal.spread,  criterion: "↑ >+0.5%  →  0~0.5%  ↓ 역전(<0)" },
    { name: "하이일드 스프레드", value: hy,          fmt: (v) => `${v.toFixed(2)}%`,                   sig: signal.hy,      criterion: "↑ <3.5%  →  3.5~4.5%  ↓ >4.5%" },
    { name: "미국 CPI YoY",    value: cpiYoy,      fmt: pct,                                          sig: signal.cpi,     criterion: "↑ <2%  →  2~3.5%  ↓ >3.5%" },
    { name: "Fear & Greed",    value: fearVal,     fmt: (v) => `${v.toFixed(0)}${fearDesc}`,          sig: signal.fear,    criterion: "↑ >70(Greed)  →  30~70  ↓ <30(Fear)" },
    { name: "미국 실업률",      value: unrate,      fmt: (v) => `${v.toFixed(1)}%`,                   sig: signal.unrate,  criterion: "↑ <4%  →  4~5%  ↓ >5%" },
    { name: "M2 YoY",          value: m2Yoy,       fmt: pct,                                          sig: signal.m2,      criterion: "↑ >+3%  →  -1~+3%  ↓ <-1%" },
    { name: "원달러 환율",      value: usdKrw,      fmt: (v) => `₩${Math.round(v).toLocaleString()}`,  sig: signal.usdKrw,  criterion: "↑ <1,350  →  1,350~1,500  ↓ >1,500" },
    { name: "한국 수출 YoY",    value: exportsYoy,  fmt: pct,                                          sig: signal.exports, criterion: "↑ >+5%  →  ±5%  ↓ <-5%" },
    { name: "VIX 공포지수",      value: vix,          fmt: (v) => v.toFixed(2),                                sig: signal.vix,     criterion: "↑ <20(안정)  →  20~30  ↓ >30(공포)" },
    { name: "NFCI 금융환경",     value: nfci,         fmt: (v) => v.toFixed(3),                                sig: signal.nfci,    criterion: "↑ <-0.1(완화)  →  -0.1~0.5  ↓ >0.5(긴축)" },
    { name: "한국 CLI",          value: korCli,       fmt: (v) => v.toFixed(2),                                sig: signal.korCli,  criterion: "↑ >100.2  →  99.5~100.2  ↓ <99.5" },
    { name: "AAII 강세-약세",    value: aaiiSpread,   fmt: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%p`,   sig: signal.aaii,    criterion: "↑ <-15%(극도 비관=역발상 매수)  →  ↓ >+15%(과열=역발상 매도)" },
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

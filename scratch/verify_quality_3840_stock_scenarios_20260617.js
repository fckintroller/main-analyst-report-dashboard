const puppeteer = require('puppeteer');

(async () => {
  const baseUrl = process.env.DASHBOARD_URL || 'http://127.0.0.1:8765/index.html';
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  try {
    const page = await browser.newPage();
    page.on('pageerror', err => { throw err; });
    await page.goto(baseUrl, { waitUntil: 'networkidle0', timeout: 10000 });
    await page.click('#btn-tab-analysis');
    await page.waitForSelector('#stock-attractiveness-table tbody tr', { timeout: 20000 });

    const dataCheck = await page.evaluate(() => {
      const rows = window.QUANT_DATA?.stock_attractiveness?.rows || [];
      const enriched = rows.filter(r =>
        r.balance_sheet_quality_score != null &&
        r.cashflow_quality_score != null &&
        r.earnings_stability_score != null
      );
      const markerRow = enriched.find(r => r.scenario_b_value_quality != null);
      return {
        rows: rows.length,
        enriched: enriched.length,
        hasDebtToEquity: rows.some(r => r.debt_to_equity != null),
        hasFcfYield: rows.some(r => r.fcf_yield != null),
        hasSource3840: rows.some(r => String(r.quality_source || '').includes('3840')),
        markerName: markerRow?.name || markerRow?.ticker || null,
      };
    });

    if (dataCheck.rows < 2000) throw new Error(`too few stock rows: ${dataCheck.rows}`);
    if (dataCheck.enriched < 300) throw new Error(`too few 38/39/40 enriched rows: ${dataCheck.enriched}`);
    if (!dataCheck.hasDebtToEquity || !dataCheck.hasFcfYield || !dataCheck.hasSource3840) {
      throw new Error(`missing 38/39/40 payload markers: ${JSON.stringify(dataCheck)}`);
    }

    await page.select('#stock-filter-sort', 'scenario_b_value_quality');
    await page.waitForFunction(() => window.activeStockScenario === 'scenario_b_value_quality', { timeout: 10000 });
    await page.waitForFunction(() => document.body.innerText.includes('㊳ BS품질'), { timeout: 5000 });
    const uiCheck = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        descOk: text.includes('Balance Sheet Quality') && text.includes('Cash Flow Quality') && text.includes('Earnings Stability'),
        bsVisible: text.includes('BS품질'),
        cfVisible: text.includes('CF품질'),
        stabilityVisible: text.includes('이익안정'),
      };
    });
    if (!uiCheck.descOk || !uiCheck.bsVisible || !uiCheck.cfVisible || !uiCheck.stabilityVisible) {
      throw new Error(`quality UI markers missing: ${JSON.stringify(uiCheck)}`);
    }

    console.log(JSON.stringify({ ok: true, dataCheck, uiCheck }, null, 2));
  } finally {
    await browser.close();
  }
})();

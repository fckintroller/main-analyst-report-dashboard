const puppeteer = require('puppeteer');

(async () => {
  const baseUrl = process.env.DASHBOARD_URL || 'http://127.0.0.1:8765/index.html';
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  page.on('console', msg => console.log('[browser]', msg.type(), msg.text()));
  await page.goto(baseUrl, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.click('#btn-tab-analysis');
  await page.waitForSelector('#stock-attractiveness-table tbody tr', { timeout: 20000 });

  const result = await page.evaluate(() => {
    const q = window.QUANT_DATA || {};
    const rows = q.stock_attractiveness?.rows || [];
    const enriched = rows.filter(r => r.debt_ratio != null && r.fcf_to_assets != null && r.financial_quality_score != null);
    const sourceOk = rows.some(r => r.quality_source === 'valuation_roe_debt_fcf');
    const descOk = document.body.innerText.includes('부채비율·FCF') || document.body.innerText.includes('부채·FCF');
    return {
      rows: rows.length,
      enriched: enriched.length,
      sourceOk,
      descOk,
      sample: enriched.slice(0, 3).map(r => ({ ticker: r.ticker, debt_ratio: r.debt_ratio, fcf_to_assets: r.fcf_to_assets, financial_quality_score: r.financial_quality_score }))
    };
  });

  await page.select('#stock-filter-sort', 'scenario_b_value_quality');
  await page.waitForFunction(() => window.activeStockScenario === 'scenario_b_value_quality', { timeout: 10000 });
  const visible = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      scenarioVisible: text.includes('B 가치+퀄리티'),
      debtVisible: text.includes('부채'),
      fcfVisible: text.includes('FCF/자산'),
      firstScore: document.querySelector('#stock-attractiveness-table tbody tr td:last-child')?.innerText || ''
    };
  });

  await browser.close();
  console.log(JSON.stringify({ result, visible }, null, 2));

  if (result.rows !== 2770) throw new Error(`expected 2770 rows, got ${result.rows}`);
  if (result.enriched < 300) throw new Error(`too few debt/fcf enriched rows: ${result.enriched}`);
  if (!result.sourceOk) throw new Error('quality_source not exported');
  if (!visible.scenarioVisible || !visible.debtVisible || !visible.fcfVisible) throw new Error('debt/fcf UI markers missing');
})();

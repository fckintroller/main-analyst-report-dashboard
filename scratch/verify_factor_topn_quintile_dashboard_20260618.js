const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(String(err)));
  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error' && !text.includes('favicon') && !text.includes('Failed to load resource')) pageErrors.push(text);
  });
  await page.goto('http://127.0.0.1:8765/index.html', { waitUntil: 'networkidle0', timeout: 60000 });
  await page.click('#btn-tab-quant');
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.sub-tab-btn')].find(b => (b.textContent || '').includes('팩터 심사표'));
    if (btn) btn.click();
  });
  await page.waitForSelector('#factor-topnq-topn-table table', { timeout: 15000 });
  await page.waitForSelector('#factor-topnq-spread-table table', { timeout: 15000 });
  const result = await page.evaluate(() => {
    const fv = window.QUANT_DATA?.factor_validation || {};
    const tq = fv.topn_quintile || {};
    const text = (sel) => document.querySelector(sel)?.textContent || '';
    const rows = (sel) => document.querySelectorAll(`${sel} tbody tr`).length;
    const setVal = (sel, val) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      el.value = val;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    };
    const initialTopRows = rows('#factor-topnq-topn-table table');
    const initialSpreadRows = rows('#factor-topnq-spread-table table');
    const topText = text('#factor-topnq-topn-table');
    const spreadText = text('#factor-topnq-spread-table');
    setVal('#factor-topnq-horizon', '3');
    setVal('#factor-topnq-topn', '20');
    const changedTopRows = rows('#factor-topnq-topn-table table');
    const changedSpreadRows = rows('#factor-topnq-spread-table table');
    return {
      summary: fv.summary?.length || 0,
      current: fv.current_top?.length || 0,
      topnSummary: tq.topn_summary?.length || 0,
      quintileSummary: tq.quintile_summary?.length || 0,
      quintileSpread: tq.quintile_spread?.length || 0,
      tqCurrent: tq.current_top?.length || 0,
      tqCoverage: tq.coverage?.length || 0,
      asOfText: text('#factor-topnq-as-of'),
      initialTopRows,
      initialSpreadRows,
      changedTopRows,
      changedSpreadRows,
      hasValueLabel: topText.includes('밸류에이션') || spreadText.includes('밸류에이션'),
      hasCaveat: text('#fv-practical').includes('거래비용') && text('#fv-practical').includes('중첩'),
    };
  });
  await browser.close();
  const ok = result.topnSummary > 0 && result.quintileSpread > 0 && result.initialTopRows > 0 && result.initialSpreadRows > 0 && result.changedTopRows > 0 && result.changedSpreadRows > 0 && result.hasCaveat;
  if (!ok || pageErrors.length) {
    console.error(JSON.stringify({ ok, result, pageErrors }, null, 2));
    process.exit(1);
  }
  console.log(JSON.stringify({ ok, result, pageErrors }, null, 2));
})();

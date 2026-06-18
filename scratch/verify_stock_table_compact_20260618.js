const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 920, height: 760, deviceScaleFactor: 1 });
  const pageErrors = [];
  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error' && !text.includes('favicon') && !text.includes('Failed to load resource')) pageErrors.push(text);
  });
  page.on('pageerror', err => pageErrors.push(err.message));

  await page.goto('http://127.0.0.1:8768/index.html', { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(() => document.querySelector('#btn-tab-analysis')?.click());
  await page.waitForSelector('#stock-attractiveness-table tbody tr', { timeout: 30000 });

  const result = await page.evaluate(() => {
    const wrap = document.querySelector('.stock-table-wrap');
    const table = document.querySelector('#stock-attractiveness-table');
    const firstRow = document.querySelector('#stock-attractiveness-table tbody tr');
    const headers = [...document.querySelectorAll('#stock-attractiveness-table thead th')].map(th => th.innerText.trim());
    const text = firstRow?.innerText || '';
    const rect = table.getBoundingClientRect();
    const wrapRect = wrap.getBoundingClientRect();
    return {
      headers,
      columnCount: firstRow ? firstRow.children.length : 0,
      tableWidth: Math.ceil(rect.width),
      wrapClientWidth: Math.ceil(wrap.clientWidth),
      wrapScrollWidth: Math.ceil(wrap.scrollWidth),
      bodyClientWidth: document.documentElement.clientWidth,
      bodyScrollWidth: document.documentElement.scrollWidth,
      hasHorizontalScrollbar: wrap.scrollWidth > wrap.clientWidth + 1,
      bodyOverflows: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      hasOpUnit: /최근\s+[\d,]+억/.test(text) && /올해\s+[\d,]+억/.test(text) && /내년\s+[\d,]+억/.test(text),
      hasDividendPct: /DIV\s+[\d.-]+%/.test(text),
      hasDataMissingText: text.includes('데이터없음') || /BS품질\s+\d+점/.test(text),
      hasRegimeInMarketCell: /레짐\s+[\d.-]+/.test(text) || text.includes('레짐 -'),
      hasWhy: text.includes('왜 선정됐나'),
      text: text.slice(0, 1200),
    };
  });
  await browser.close();
  const ok = result.headers.length === 5
    && result.columnCount === 5
    && !result.hasHorizontalScrollbar
    && result.hasOpUnit
    && result.hasDividendPct
    && result.hasDataMissingText
    && result.hasRegimeInMarketCell
    && result.hasWhy
    && pageErrors.length === 0;
  console.log(JSON.stringify({ ok, result, pageErrors }, null, 2));
  if (!ok) process.exit(1);
})().catch(err => { console.error(err); process.exit(1); });

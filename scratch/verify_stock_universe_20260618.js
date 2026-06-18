const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error' && !text.includes('favicon') && !text.includes('Failed to load resource')) pageErrors.push(text);
  });
  page.on('pageerror', err => pageErrors.push(err.message));
  await page.goto('http://127.0.0.1:8767/index.html', { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(() => document.querySelector('#btn-tab-analysis')?.click());
  await page.waitForSelector('#stock-attractiveness-table tbody tr', { timeout: 30000 });

  const initial = await page.evaluate(() => {
    const sa = window.QUANT_DATA.stock_attractiveness;
    const selected = document.querySelector('#stock-filter-market')?.value;
    const countText = document.querySelector('#stock-attractiveness-count')?.innerText || '';
    const body = document.body.innerText;
    return {
      selected,
      countText,
      rowsRendered: document.querySelectorAll('#stock-attractiveness-table tbody tr').length,
      universeDefault: sa.universe?.default,
      counts: sa.universe?.counts,
      hasUniverseSummary: body.includes('유니버스 정의') && body.includes('B 기본') && body.includes('A 별도 플래그') && body.includes('C 스크리닝'),
      hasBDefaultText: body.includes('개발 우선순위는 B 기본 유니버스 유지'),
      hasBadge: body.includes('B 기본'),
    };
  });

  await page.select('#stock-filter-market', 'A_KOSPI200_PROXY');
  await page.waitForFunction(() => document.querySelector('#stock-attractiveness-count')?.innerText.includes('A KOSPI200 proxy'), { timeout: 10000 });
  const a = await page.evaluate(() => ({
    countText: document.querySelector('#stock-attractiveness-count')?.innerText || '',
    rowsRendered: document.querySelectorAll('#stock-attractiveness-table tbody tr').length,
    hasBadge: document.body.innerText.includes('A K200'),
  }));

  await page.select('#stock-filter-market', 'C_SCREENABLE');
  await page.waitForFunction(() => document.querySelector('#stock-attractiveness-count')?.innerText.includes('C 전체상장 스크리닝'), { timeout: 10000 });
  const c = await page.evaluate(() => ({
    countText: document.querySelector('#stock-attractiveness-count')?.innerText || '',
    rowsRendered: document.querySelectorAll('#stock-attractiveness-table tbody tr').length,
    hasBadge: document.body.innerText.includes('C 스크리닝'),
  }));

  await page.select('#stock-filter-market', 'B_PROJECT_DEFAULT');
  await page.type('#stock-attractiveness-search', '삼성전자');
  await page.waitForFunction(() => document.querySelector('#stock-attractiveness-count')?.innerText.includes('검색 결과'), { timeout: 10000 });
  const search = await page.evaluate(() => ({
    countText: document.querySelector('#stock-attractiveness-count')?.innerText || '',
    hasSamsung: document.body.innerText.includes('삼성전자'),
    hasWhy: document.body.innerText.includes('왜 선정됐나'),
  }));

  await browser.close();
  const ok = initial.selected === 'B_PROJECT_DEFAULT'
    && initial.universeDefault === 'B_KOSPI200_KOSDAQ150'
    && initial.counts?.b_project_default === 350
    && initial.counts?.a_kospi200_proxy === 200
    && initial.counts?.kosdaq150_proxy === 150
    && initial.hasUniverseSummary
    && initial.hasBDefaultText
    && initial.hasBadge
    && /검색 결과 350개/.test(initial.countText)
    && /검색 결과 200개/.test(a.countText)
    && a.hasBadge
    && /검색 결과 898개/.test(c.countText)
    && c.hasBadge
    && search.hasSamsung
    && search.hasWhy
    && pageErrors.length === 0;
  console.log(JSON.stringify({ ok, initial, a, c, search, pageErrors }, null, 2));
  if (!ok) process.exit(1);
})().catch(err => { console.error(err); process.exit(1); });

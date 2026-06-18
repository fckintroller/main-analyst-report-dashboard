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
  await page.goto('http://127.0.0.1:8766/index.html', { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluate(() => {
    const btn = document.querySelector('#btn-tab-analysis');
    if (btn) btn.click();
  });
  await page.waitForSelector('#stock-attractiveness-table tbody tr', { timeout: 30000 });
  const result1 = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('#stock-attractiveness-table tbody tr')];
    const text = document.body.innerText;
    return {
      rowCount: rows.length,
      hasWhy: text.includes('왜 선정됐나'),
      hasSectorLeaders: !!document.querySelector('#stock-sector-leaders')?.innerText.trim(),
      hasRankingGuide: text.includes('랭킹 해석 가이드'),
      hasRisk: text.includes('리스크') || text.includes('변동성') || text.includes('주요 리스크 플래그 없음'),
      hasSectorRank: text.includes(' 내 #'),
      hasThreeMonth: text.includes('최근 3개월'),
      summary: document.querySelector('#stock-ranking-summary')?.innerText || '',
      firstRow: rows[0]?.innerText.slice(0, 600) || ''
    };
  });
  await page.select('#stock-filter-sort', 'scenario_b_value_quality');
  await page.waitForFunction(() => document.body.innerText.includes('B 가치+퀄리티'), { timeout: 10000 });
  const result2 = await page.evaluate(() => ({
    rowCount: document.querySelectorAll('#stock-attractiveness-table tbody tr').length,
    hasScenario: document.body.innerText.includes('B 가치+퀄리티'),
    hasFactor: /섹터상대 가치|재무건전성|현금흐름|ROE/.test(document.body.innerText),
  }));
  await page.type('#stock-attractiveness-search', '삼성전자');
  await page.waitForFunction(() => document.querySelector('#stock-attractiveness-count')?.innerText.includes('검색 결과'), { timeout: 10000 });
  const result3 = await page.evaluate(() => ({
    countText: document.querySelector('#stock-attractiveness-count')?.innerText || '',
    hasSamsung: document.body.innerText.includes('삼성전자'),
    hasWhyAfterSearch: document.body.innerText.includes('왜 선정됐나'),
  }));
  await browser.close();
  const ok = result1.rowCount > 0 && result1.hasWhy && result1.hasSectorLeaders && result1.hasRankingGuide && result1.hasRisk && result1.hasSectorRank && result1.hasThreeMonth && result2.rowCount > 0 && result2.hasScenario && result2.hasFactor && result3.hasSamsung && result3.hasWhyAfterSearch && pageErrors.length === 0;
  console.log(JSON.stringify({ ok, result1, result2, result3, pageErrors }, null, 2));
  if (!ok) process.exit(1);
})().catch(err => { console.error(err); process.exit(1); });

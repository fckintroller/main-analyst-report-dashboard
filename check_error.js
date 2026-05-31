const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  
  await page.goto('file:///C:/claude cowork/01_projects/Anal_reports/web/index.html', { waitUntil: 'networkidle0' });
  
  await page.click('#btn-tab-chart');
  await new Promise(r => setTimeout(r, 1000));
  
  await page.evaluate(() => {
    console.log("marketChart is defined after click?", marketChart !== null);
    if(marketChart) console.log("marketChart datasets count:", marketChart.data.datasets.length);
  });
  
  await browser.close();
})();

/**
 * 07_semi_bb_browser.js — Puppeteer로 SEMI B/B 비율 수집
 *
 * Trading Economics의 SEMI B/B 페이지는 JS 렌더링이므로
 * requests만으로는 실제 데이터를 가져올 수 없음.
 * 이 스크립트를 07_semi_bb.py에서 subprocess로 호출합니다.
 *
 * 사용: node 07_semi_bb_browser.js
 * 출력: JSON { success, bb_ratio, date, billings_3ma, bookings_3ma, source }
 */

const puppeteer = require('puppeteer');

const TARGETS = [
  {
    name: 'trading_economics',
    url: 'https://tradingeconomics.com/united-states/semi-north-america-book-to-bill',
    waitFor: 4000,
    extract: async (page) => {
      return page.evaluate(() => {
        // 현재값 후보 셀렉터 (버전마다 달라질 수 있음)
        const sels = [
          '#ctl00_ContentPlaceHolder1_ctl01_UpdatePanel1 .datanow',
          '.ticker-summary .last',
          '[id*="datanow"]',
          '.datanow',
          'td.datanow',
        ];
        for (const sel of sels) {
          const el = document.querySelector(sel);
          if (el) {
            const n = parseFloat(el.textContent.replace(/[^0-9.]/g, ''));
            if (!isNaN(n) && n > 0.3 && n < 3.5) return { bb_ratio: n };
          }
        }
        // 페이지 전체 텍스트에서 BB 후보 값 추출
        const text = document.body.innerText;
        const match = text.match(/(?:book.to.bill|B\/B)[^\d]*?([01]\.\d{2})/i);
        if (match) return { bb_ratio: parseFloat(match[1]) };
        // 0.XX 또는 1.XX 패턴에서 BB 범위 값 찾기
        const nums = text.match(/\b([01]\.\d{2})\b/g) || [];
        const candidates = nums.map(Number).filter(n => n > 0.4 && n < 2.5);
        if (candidates.length) return { bb_ratio: candidates[0] };
        return null;
      });
    },
  },
  {
    name: 'semi_org_search',
    url: 'https://www.semi.org/en/search#q=book-to-bill&t=All&sort=relevancy',
    waitFor: 5000,
    extract: async (page) => {
      return page.evaluate(() => {
        const text = document.body.innerText;
        const match = text.match(/book.to.bill\s*(?:ratio\s*(?:was|of|:)?\s*)?([01]\.\d{2,3})/i);
        if (match) return { bb_ratio: parseFloat(match[1]) };
        return null;
      });
    },
  },
];

function prevMonthDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() === 0 ? 12 : d.getMonth()).padStart(2, '0')}-01`;
}

(async () => {
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });

    for (const target of TARGETS) {
      const page = await browser.newPage();
      await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
      );
      try {
        await page.goto(target.url, { waitUntil: 'networkidle2', timeout: 30000 });
        await new Promise(r => setTimeout(r, target.waitFor));

        const data = await target.extract(page);
        await page.close();

        if (data?.bb_ratio) {
          await browser.close();
          console.log(JSON.stringify({
            success: true,
            bb_ratio: Math.round(data.bb_ratio * 1000) / 1000,
            billings_3ma: data.billings_3ma || null,
            bookings_3ma: data.bookings_3ma || null,
            date: prevMonthDate(),
            source: target.name,
          }));
          process.exit(0);
        }
      } catch (e) {
        await page.close().catch(() => {});
      }
    }

    await browser.close();
    console.log(JSON.stringify({ success: false, error: 'No source returned data' }));
  } catch (e) {
    if (browser) await browser.close().catch(() => {});
    console.log(JSON.stringify({ success: false, error: e.message }));
  }
})();

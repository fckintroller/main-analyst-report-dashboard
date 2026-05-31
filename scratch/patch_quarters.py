import re
import codecs

file_path = 'web/app.js'
with codecs.open(file_path, 'r', 'utf-8') as f:
    content = f.read()

# 1. Update the sectorMap generation block to aggregate by quarters
old_block1 = """  const sectorMap = {};
  reports.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id);
    const sector = aObj ? aObj.merged_sector : '기타';
    if (!sectorMap[sector]) {
      sectorMap[sector] = { count: 0, buy: 0, hold: 0, sell: 0, reports: [] };
    }
    sectorMap[sector].count += 1;
    
    // 팩트(투자의견) 카운팅
    if (rep.rating && (rep.rating.includes('Buy') || rep.rating.includes('매수'))) {
      sectorMap[sector].buy += 1;
    } else if (rep.rating && (rep.rating.includes('Sell') || rep.rating.includes('매도'))) {
      sectorMap[sector].sell += 1;
    } else {
      sectorMap[sector].hold += 1; // 그 외에는 홀딩(Hold)으로 간주
    }
    
    sectorMap[sector].reports.push(rep);
  });

  // 2. 트리맵용 데이터 포맷 구성
  const treemapData = [];
  for (const [sector, data] of Object.entries(sectorMap)) {
    const buyPct = Math.round((data.buy / data.count) * 100);
    const holdPct = Math.round((data.hold / data.count) * 100);
    const sellPct = Math.round((data.sell / data.count) * 100);
    
    treemapData.push({
      sector: sector,
      count: data.count,
      buyPct: buyPct,
      holdPct: holdPct,
      sellPct: sellPct,
      // 색상은 매수 의견 비율(buyPct)을 기준으로 칠함
      sentiment: buyPct,
      topPick: data.reports[0] ? data.reports[0].stock_name : ''
    });
  }"""

new_block1 = """  const sectorMap = {};
  reports.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id);
    const sector = aObj ? aObj.merged_sector : '기타';
    if (!sectorMap[sector]) {
      sectorMap[sector] = { count: 0, buy: 0, hold: 0, sell: 0, quarters: {}, reports: [] };
    }
    sectorMap[sector].count += 1;
    
    // 분기(Quarter) 추출 로직
    if (rep.date) {
      const d = new Date(rep.date);
      const yearStr = String(d.getFullYear()).slice(-2);
      const q = Math.floor(d.getMonth() / 3) + 1;
      const qStr = `${yearStr}'${q}Q`;
      sectorMap[sector].quarters[qStr] = (sectorMap[sector].quarters[qStr] || 0) + 1;
    }

    // 팩트(투자의견) 카운팅
    if (rep.rating && (rep.rating.includes('Buy') || rep.rating.includes('매수'))) {
      sectorMap[sector].buy += 1;
    } else if (rep.rating && (rep.rating.includes('Sell') || rep.rating.includes('매도'))) {
      sectorMap[sector].sell += 1;
    } else {
      sectorMap[sector].hold += 1; // 그 외에는 홀딩(Hold)으로 간주
    }
    
    sectorMap[sector].reports.push(rep);
  });

  // 2. 트리맵용 데이터 포맷 구성
  const treemapData = [];
  for (const [sector, data] of Object.entries(sectorMap)) {
    const buyPct = Math.round((data.buy / data.count) * 100);
    const holdPct = Math.round((data.hold / data.count) * 100);
    const sellPct = Math.round((data.sell / data.count) * 100);
    
    // 분기별 텍스트 배열 생성 (최신 분기순 혹은 오름차순 정렬)
    const sortedQuarters = Object.entries(data.quarters || {})
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([q, cnt]) => `${q} : ${cnt}개`);
      
    treemapData.push({
      sector: sector,
      count: data.count,
      buyPct: buyPct,
      holdPct: holdPct,
      sellPct: sellPct,
      quartersArray: sortedQuarters,
      // 색상은 매수 의견 비율(buyPct)을 기준으로 칠함
      sentiment: buyPct,
      topPick: data.reports[0] ? data.reports[0].stock_name : ''
    });
  }"""

content = content.replace(old_block1, new_block1)

# 2. Update formatter label
old_formatter = """          formatter: (ctx) => {
            if (ctx.type !== 'data') return [];
            return [
              ctx.raw._data.sector, 
              `매수 ${ctx.raw._data.children[0].buyPct}% | 홀딩 ${ctx.raw._data.children[0].holdPct}% | 매도 ${ctx.raw._data.children[0].sellPct}%`
            ];
          }"""

new_formatter = """          formatter: (ctx) => {
            if (ctx.type !== 'data') return [];
            const data = ctx.raw._data.children[0];
            return [
              data.sector, 
              ...data.quartersArray
            ];
          }"""

content = content.replace(old_formatter, new_formatter)

# 3. Update tooltip label
old_tooltip = """              label: (item) => {
                const data = item.raw._data.children[0];
                return [
                  `총 리포트 발행: ${data.count}건`,
                  `매수(Buy): ${data.buyPct}% | 홀딩(Hold): ${data.holdPct}% | 매도(Sell): ${data.sellPct}%`,
                  `관심 종목(Top Pick): ${data.topPick || '없음'}`
                ];
              }"""

new_tooltip = """              label: (item) => {
                const data = item.raw._data.children[0];
                return [
                  `총 리포트 발행: ${data.count}건`,
                  ...data.quartersArray,
                  `매수(Buy): ${data.buyPct}% | 홀딩(Hold): ${data.holdPct}% | 매도(Sell): ${data.sellPct}%`,
                  `관심 종목(Top Pick): ${data.topPick || '없음'}`
                ];
              }"""

content = content.replace(old_tooltip, new_tooltip)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(content)

print("web/app.js patched successfully.")

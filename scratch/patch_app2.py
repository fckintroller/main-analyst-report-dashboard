import re
import codecs

file_path = 'web/app.js'
with codecs.open(file_path, 'r', 'utf-8') as f:
    content = f.read()

# Replace heatmap logic by searching for the start and end tokens
start_token = "  const sectorMap = {};"
end_token = "  // 색상(0~100)을 투명도로 변환"

new_logic = """  const sectorMap = {};
  reports.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id);
    const sector = aObj ? aObj.merged_sector : '기타';
    if (!sectorMap[sector]) {
      sectorMap[sector] = { count: 0, totalScore: 0, reports: [] };
    }
    sectorMap[sector].count += 1;
    
    // 계산 로직: 투자의견(50%) + 모멘텀(50%)
    let ratingScore = 50;
    if (rep.rating && (rep.rating.includes('Buy') || rep.rating.includes('매수'))) ratingScore = 100;
    else if (rep.rating && (rep.rating.includes('Sell') || rep.rating.includes('매도'))) ratingScore = 0;
    
    let momentumScore = 50;
    if (rep.title && (rep.title.includes('상향') || rep.title.includes('서프라이즈') || rep.title.includes('개선') || rep.title.includes('턴어라운드') || rep.title.includes('기대') || rep.title.includes('성장'))) momentumScore = 100;
    else if (rep.title && (rep.title.includes('하향') || rep.title.includes('우려') || rep.title.includes('악재') || rep.title.includes('소멸') || rep.title.includes('선반영'))) momentumScore = 0;
    
    const compositeScore = (ratingScore + momentumScore) / 2;
    sectorMap[sector].totalScore += compositeScore;
    
    sectorMap[sector].reports.push(rep);
  });

  // 2. 트리맵 데이터 변환
  const treemapData = [];
  for (const [sector, data] of Object.entries(sectorMap)) {
    const avgScore = Math.round(data.totalScore / data.count);
    treemapData.push({
      sector: sector,
      count: data.count,
      sentiment: avgScore,
      topPick: data.reports[0] ? data.reports[0].stock_name : ''
    });
  }

  // 색상(0~100)을 투명도로 변환"""

content = re.sub(re.escape(start_token) + r".*?" + re.escape(end_token), new_logic, content, flags=re.DOTALL)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(content)

print("web/app.js patched successfully.")

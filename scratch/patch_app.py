import re
import codecs

file_path = 'web/app.js'
with codecs.open(file_path, 'r', 'utf-8') as f:
    content = f.read()

# 1. Remove AI badge from renderReports
badge_pattern = r'\$\{rep\.sentiment_score !== undefined \? `.*?<\/span>` : \'\'\}'
content = re.sub(badge_pattern, '', content, flags=re.DOTALL)

# 2. Update Heatmap Title and Description
content = content.replace('섹터별 자금 흐름 및 AI 감성 히트맵', '섹터별 자금 흐름 및 투자 과열도 히트맵')
content = content.replace('색상(Color)은 AI가 분석한 해당 섹터 리포트들의 <b>평균 감성 점수(긍정/부정)</b>를 나타냅니다. (<span style="color:#ef4444; font-weight:bold;">빨강: 강세(Bullish)</span> / <span style="color:#3b82f6; font-weight:bold;">파랑: 약세(Bearish)</span>)', '색상(Color)은 해당 섹터 리포트들의 <b>투자의견(Rating) 및 목표가 상향 모멘텀을 종합한 과열도 점수</b>를 나타냅니다. (<span style="color:#ef4444; font-weight:bold;">빨강: 쏠림/과열(Hot)</span> / <span style="color:#3b82f6; font-weight:bold;">파랑: 소외/침체(Cold)</span>)')

# 3. Update initHeatmap Logic
old_heatmap_logic = """  const sectorMap = {};
  reports.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id);
    const sector = aObj ? aObj.merged_sector : '기타';
    if (!sectorMap[sector]) {
      sectorMap[sector] = { count: 0, totalSentiment: 0, reports: [] };
    }
    sectorMap[sector].count += 1;
    if (rep.sentiment_score !== undefined) {
      sectorMap[sector].totalSentiment += rep.sentiment_score;
    } else {
      // 기본값 부여 (임의 배정)
      sectorMap[sector].totalSentiment += 50; 
    }
    sectorMap[sector].reports.push(rep);
  });

  // 2. 트리맵 데이터 변환
  const treemapData = [];
  for (const [sector, data] of Object.entries(sectorMap)) {
    const avgSentiment = Math.round(data.totalSentiment / data.count);
    treemapData.push({
      sector: sector,
      count: data.count,
      sentiment: avgSentiment,
      topPick: data.reports[0] ? data.reports[0].stock_name : ''
    });
  }"""

new_heatmap_logic = """  const sectorMap = {};
  reports.forEach(rep => {
    const aObj = analysts.find(a => a.id === rep.analyst_id);
    const sector = aObj ? aObj.merged_sector : '기타';
    if (!sectorMap[sector]) {
      sectorMap[sector] = { count: 0, totalScore: 0, reports: [] };
    }
    sectorMap[sector].count += 1;
    
    // 계산 로직: 투자의견(50%) + 모멘텀(50%)
    let ratingScore = 50;
    if (rep.rating.includes('Buy') || rep.rating.includes('매수')) ratingScore = 100;
    else if (rep.rating.includes('Sell') || rep.rating.includes('매도')) ratingScore = 0;
    
    let momentumScore = 50;
    if (rep.title.includes('상향') || rep.title.includes('서프라이즈') || rep.title.includes('개선') || rep.title.includes('턴어라운드') || rep.title.includes('기대') || rep.title.includes('성장')) momentumScore = 100;
    else if (rep.title.includes('하향') || rep.title.includes('우려') || rep.title.includes('악재') || rep.title.includes('소멸') || rep.title.includes('선반영')) momentumScore = 0;
    
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
  }"""

content = content.replace(old_heatmap_logic, new_heatmap_logic)
content = content.replace("title=\"AI 감성 분석 점수\"", "") # in case something remained
content = content.replace('섹터별 자금 흐름 및 AI 감성 히트맵', '섹터별 자금 흐름 및 투자 과열도 히트맵') # fallback if index.html was modified

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(content)

print("web/app.js patched successfully.")

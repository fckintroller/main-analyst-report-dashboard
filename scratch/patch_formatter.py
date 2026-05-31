import re
import codecs

file_path = 'web/app.js'
with codecs.open(file_path, 'r', 'utf-8') as f:
    content = f.read()

# 1. Update formatter
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
              `총 발행: ${data.count}건`,
              ...data.quartersArray
            ];
          }"""

content = content.replace(old_formatter, new_formatter)

# 2. Update tooltip
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

print("web/app.js formatter patched successfully.")

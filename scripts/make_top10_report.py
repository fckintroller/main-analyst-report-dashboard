"""KOSPI 시총 상위 10종목 퀀트 팩터 분석 리포트 생성."""
import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'database', 'quant_data.sqlite')
SECTOR_MAP = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'stock_detail', 'sector_map.csv')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
PERIOD = '2026-06-01'


def pct_bar(val, width=10):
    if pd.isna(val):
        return '  N/A      '
    filled = round(val * width)
    return '[' + '█' * filled + '░' * (width - filled) + f'] {val:.2f}'


def fmt_pct(v, decimals=1):
    if pd.isna(v):
        return 'N/A'
    return f'{v * 100:+.{decimals}f}%'


def fmt_f(v, decimals=2):
    if pd.isna(v):
        return 'N/A'
    return f'{v:.{decimals}f}'


def score_star(score):
    thresholds = (0.35, 0.5, 0.65, 0.8)
    if pd.isna(score):
        return '☆☆☆☆'
    stars = sum(score >= t for t in thresholds)
    return '★' * stars + '☆' * (4 - stars)


RERATING_LABEL = {
    're_rating_up': '↑ 재평가 상승',
    'de_rating_down': '↓ 재평가 하락',
    'flat': '→ 횡보',
    'N/A': 'N/A',
}

FLOW_LABEL = {
    'net_buying': '↑ 순매수',
    'net_selling': '↓ 순매도',
    'flat': '→ 중립',
    'N/A': 'N/A',
}


def composite_signal(tkr, val, mom, flow):
    scores = []
    if tkr in val.index and not pd.isna(val.loc[tkr, 'valuation_score']):
        scores.append(('밸류에이션', val.loc[tkr, 'valuation_score']))
    if tkr in mom.index and not pd.isna(mom.loc[tkr, 'momentum_score']):
        scores.append(('모멘텀', mom.loc[tkr, 'momentum_score']))
    if tkr in flow.index and not pd.isna(flow.loc[tkr, 'flow_score']):
        scores.append(('수급', flow.loc[tkr, 'flow_score']))
    if not scores:
        return None, []
    return sum(s for _, s in scores) / len(scores), scores


def build_report():
    conn = sqlite3.connect(DB_PATH)

    mc = pd.read_sql('SELECT * FROM stock_market_snapshot_kospi_market_cap_by_ticker_20260605', conn)
    mc.columns = ['ticker', 'close', 'market_cap', 'volume', 'trading_value', 'shares']
    top10 = mc.nlargest(10, 'market_cap').reset_index(drop=True)
    tickers = top10['ticker'].tolist()

    sector = pd.read_csv(SECTOR_MAP, encoding='utf-8-sig')
    sector.columns = ['ticker', 'name', 'sector', 'price', 'chg', 'pct', 'smktcap', 'market']
    info = sector[sector.ticker.isin(tickers)][['ticker', 'name', 'sector']].set_index('ticker')

    tl = "('" + "','".join(tickers) + "')"
    val  = pd.read_sql(f'SELECT * FROM factor_valuation_per_pbr_month WHERE period="{PERIOD}" AND ticker IN {tl}', conn).set_index('ticker')
    mom  = pd.read_sql(f'SELECT * FROM factor_stock_price_momentum_month WHERE period="{PERIOD}" AND ticker IN {tl}', conn).set_index('ticker')
    flow = pd.read_sql(f'SELECT * FROM factor_investor_flow_momentum_month WHERE period="{PERIOD}" AND ticker IN {tl}', conn).set_index('ticker')

    lines = []
    SEP = '=' * 72
    lines += [SEP,
              '  KOSPI 시총 상위 10종목 -- 퀀트 팩터 분석 리포트',
              f'  기준일: {PERIOD}  /  생성: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
              '  ※ DART 공시 이벤트 신호(④)는 분석에서 제외 (factor_not_ready 격리 중)',
              SEP, '']

    # 종합 요약 테이블
    lines.append('[ 종합 요약 ]')
    lines.append(f'  {"순위":<4} {"티커":<8} {"종목명":<16} {"섹터":<14} {"시총(조)":<9} {"종합":<8} {"밸류":<6} {"모멘텀":<6} {"수급":<6}')
    lines.append('  ' + '-' * 74)
    for rank, row in enumerate(top10.itertuples(), 1):
        tkr = row.ticker
        nm  = info.loc[tkr, 'name']   if tkr in info.index else '?'
        sec = info.loc[tkr, 'sector'] if tkr in info.index else '?'
        mkt = row.market_cap / 1e12
        comp, _ = composite_signal(tkr, val, mom, flow)
        comp_s = f'{comp:.2f}' if comp is not None else 'N/A'
        v_s = fmt_f(val.loc[tkr, 'valuation_score']  if tkr in val.index  else float('nan'))
        m_s = fmt_f(mom.loc[tkr, 'momentum_score']   if tkr in mom.index  else float('nan'))
        f_s = fmt_f(flow.loc[tkr, 'flow_score']      if tkr in flow.index else float('nan'))
        lines.append(f'  {rank:<4} {tkr:<8} {nm:<16} {sec:<14} {mkt:<9.1f} {comp_s:<8} {v_s:<6} {m_s:<6} {f_s}')
    lines += ['', '  * 점수 0~1, 높을수록 긍정적 (밸류=저평가, 모멘텀=상승, 수급=유입)', '', SEP, '']

    # 종목별 상세
    for rank, row in enumerate(top10.itertuples(), 1):
        tkr = row.ticker
        nm  = info.loc[tkr, 'name']   if tkr in info.index else '(이름없음)'
        sec = info.loc[tkr, 'sector'] if tkr in info.index else '?'
        mkt = row.market_cap / 1e12
        comp, detail = composite_signal(tkr, val, mom, flow)

        lines.append(f'[{rank:02d}] {nm} ({tkr}) | {sec} | 시총 {mkt:.1f}조원')
        lines.append('-' * 72)

        # 밸류에이션
        lines.append('  ① 밸류에이션 (PER/PBR 섹터 내 비교)')
        if tkr in val.index:
            v = val.loc[tkr]
            lines.append(f'     PER: {fmt_f(v.PER)}x    PBR: {fmt_f(v.PBR)}x    DIV: {fmt_f(v.DIV)}%')
            lines.append(f'     섹터내 PER 백분위 : {pct_bar(v.per_percentile_sector)}')
            lines.append(f'     섹터내 PBR 백분위 : {pct_bar(v.pbr_percentile_sector)}')
            lines.append(f'     자기역사 PER z-score : {fmt_f(v.per_zscore_own_24m)}σ  (낮을수록 자기 역사상 저평가)')
            lines.append(f'     재평가 방향 : {RERATING_LABEL.get(str(v.rerating_direction), "?")}  (3M PER 변화율: {fmt_pct(v.per_rerating_momentum_3m)})')
            lines.append(f'     밸류에이션 점수 : {fmt_f(v.valuation_score)}  >>  {str(v.valuation_bucket).upper()}  {score_star(v.valuation_score)}')
        else:
            lines.append('     fundamental 데이터 없음 (우선주 등)')
        lines.append('')

        # 가격 모멘텀
        lines.append('  ② 가격·거래량 모멘텀')
        if tkr in mom.index:
            m = mom.loc[tkr]
            lines.append(f'     수익률 :  1M {fmt_pct(m.ret_1m)}   3M {fmt_pct(m.ret_3m)}   6M {fmt_pct(m.ret_6m)}   12M {fmt_pct(m.ret_12m)}')
            lines.append(f'     12-1M 모멘텀 : {fmt_pct(m.mom_12_1)}')
            lines.append(f'     모멘텀 시장 내 백분위 : {pct_bar(m.momentum_percentile_cross)}')
            lines.append(f'     거래량 스파이크 : {"YES ⚡" if m.turnover_spike_flag else "없음"}   거래량Z : {fmt_f(m.turnover_zscore_own)}σ')
            lines.append(f'     모멘텀 점수 : {fmt_f(m.momentum_score)}  >>  {str(m.momentum_bucket).upper()}  {score_star(m.momentum_score)}')
        else:
            lines.append('     데이터 없음')
        lines.append('')

        # 수급
        lines.append('  ③ 수급 (외국인/기관)')
        if tkr in flow.index:
            f = flow.loc[tkr]
            lines.append(f'     외국인 순매수비율 : {fmt_pct(f.foreign_net_ratio)}   (전월 대비 변화: {fmt_pct(f.foreign_net_ratio_change)})')
            lines.append(f'     기관 순매수비율   : {fmt_pct(f.inst_net_ratio)}   (전월 대비 변화: {fmt_pct(f.inst_net_ratio_change)})')
            lines.append(f'     외국인 보유비율   : {fmt_f(f.foreign_ratio_pct)}%  (변화: {fmt_pct(f.foreign_ratio_pct_change)})')
            lines.append(f'     외국인 순매수 z-score : {fmt_f(f.foreign_net_ratio_zscore_own_6m)}σ')
            lines.append(f'     수급 시장 내 백분위 : {pct_bar(f.foreign_net_ratio_percentile_cross)}')
            lines.append(f'     수급 방향 : {FLOW_LABEL.get(str(f.flow_direction), "?")}   ({str(f.flow_bucket).replace("_", " ")})')
            lines.append(f'     수급 점수 : {fmt_f(f.flow_score)}  {score_star(f.flow_score)}')
        else:
            lines.append('     데이터 없음')
        lines.append('')

        # 종합 신호
        if comp is not None:
            if comp >= 0.6:
                sig = 'BUY    ▲'
            elif comp >= 0.45:
                sig = 'WATCH  ->'
            else:
                sig = 'CAUTION▼'
            detail_str = '  |  '.join(f'{k} {v:.2f}' for k, v in detail)
            lines.append(f'  ◆ 종합 신호 : {sig}   (종합점수 {comp:.3f})   [{detail_str}]')
        lines += ['', SEP, '']

    # 가이드
    lines += [
        '[ 팩터 해석 가이드 ]',
        '  밸류에이션 : deep_value > cheap > neutral > rich > expensive',
        '  모멘텀     : strong_up > up > neutral > down > strong_down',
        '  수급       : strong_inflow > inflow > neutral > outflow > strong_outflow',
        '  점수 기준  : 0~1, 0.5=중립 / >0.6 강한 긍정 / <0.4 강한 부정',
        '  종합 기준  : >=0.60 BUY  /  0.45~0.60 WATCH  /  <0.45 CAUTION',
        '',
        '[ 데이터 출처 ]',
        '  시총/스냅샷 : KRX 2026-06-05',
        '  밸류에이션  : pykrx fundamental (PER/PBR 섹터 내 비교, 업종명 기준)',
        '  가격모멘텀  : pykrx OHLCV 수정주가',
        '  수급        : Naver Finance 투자자 동향 (외국인/기관 순매매)',
        '  DART 공시 이벤트 팩터(④)는 데이터 품질 미달로 제외 (factor_not_ready)',
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, 'kospi_top10_factor_analysis.txt')
    with open(out_path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines))
    print(f'저장: {out_path}  ({len(lines)}행)')
    return out_path


if __name__ == '__main__':
    build_report()

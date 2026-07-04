from __future__ import annotations
import argparse,csv,json,os,time,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
PROJECT_ROOT=Path(__file__).resolve().parents[2]
OUT_DIR=PROJECT_ROOT/'data'/'raw'/'trade_import_export'
ECOS_BASE='https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/10000/{stat}/M/{start}/{end}/{item}'
CUSTOMS_BASE='http://apis.data.go.kr/1220000/Itemtrade/getItemtradeList'
HS_GROUPS=[
 {'hs':'8542','name':'반도체/집적회로','theme':'반도체','reason':'한국 수출 사이클 핵심'},
 {'hs':'8703','name':'승용차','theme':'자동차','reason':'완성차 ASP/물량 확인'},
 {'hs':'8507','name':'축전지/이차전지','theme':'2차전지','reason':'배터리 단가·물량 압력'},
 {'hs':'2710','name':'석유제품','theme':'정유','reason':'유가/마진 영향'},
 {'hs':'7208','name':'철강 판재','theme':'철강','reason':'중국 경기/단가 민감'},
 {'hs':'3907','name':'폴리에스터/수지','theme':'화학','reason':'화학 스프레드 proxy'},
 {'hs':'8517','name':'통신기기/부품','theme':'IT 하드웨어','reason':'전방 IT 수요'},
 {'hs':'8901','name':'선박','theme':'조선','reason':'고가 수주 인도 proxy'},
]
def _load_env_file(path:Path)->None:
    if not path.exists(): return
    for raw in path.read_text(encoding='utf-8',errors='ignore').splitlines():
        line=raw.strip()
        if not line or line.startswith('::') or line.startswith('#'): continue
        if line.upper().startswith('SET '): line=line[4:]
        if '=' not in line: continue
        k,v=line.split('=',1); k=k.strip(); v=v.strip().strip('"')
        if k and k not in os.environ: os.environ[k]=v
def load_keys()->tuple[str,str]:
    _load_env_file(PROJECT_ROOT/'.env'); _load_env_file(PROJECT_ROOT/'env.bat')
    return os.environ.get('ECOS_API_KEY','').strip(), (os.environ.get('CUSTOMS_API_KEY') or os.environ.get('DATA_GO_KR_SERVICE_KEY') or '').strip()
def month_range(months:int)->tuple[str,str]:
    n=datetime.now(); end=f'{n.year}{n.month:02d}'; idx=n.year*12+(n.month-1)-max(1,months-1); y,m0=divmod(idx,12); return f'{y}{m0+1:02d}',end
def sf(v:Any)->float|None:
    if v is None: return None
    s=str(v).replace(',','').strip()
    if s in {'','-','nan','None'}: return None
    try: return float(s)
    except Exception: return None
def pct(cur:float|None,prev:float|None)->float|None:
    if cur is None or prev in (None,0): return None
    return round((cur/prev-1)*100,2)
def fj(url:str)->dict[str,Any]:
    with urllib.request.urlopen(url,timeout=25) as resp: return json.loads(resp.read().decode('utf-8'))
def ecos_series(key:str,stat:str,item:str,start:str,end:str)->list[dict[str,Any]]:
    if not key: return []
    url=ECOS_BASE.format(key=urllib.parse.quote(key),stat=stat,start=start,end=end,item=urllib.parse.quote(item))
    try: rows=fj(url).get('StatisticSearch',{}).get('row',[]) or []
    except Exception: return []
    out=[]
    for r in rows:
        val=sf(r.get('DATA_VALUE'))
        if val is not None: out.append({'month':str(r.get('TIME','')),'value':val,'item':item,'item_name':r.get('ITEM_NAME1') or item,'unit':r.get('UNIT_NAME',''),'source':'ECOS'})
    return sorted(out,key=lambda x:x['month'])
def build_ecos(key:str,start:str,end:str)->dict[str,Any]:
    specs={'exports_usd':('901Y118','T002'),'imports_usd':('901Y118','T004'),'export_value_index':('403Y001','*AA'),'export_volume_index':('403Y002','*AA'),'import_value_index':('403Y003','*AA'),'import_volume_index':('403Y004','*AA')}
    series={}; by=defaultdict(dict)
    for name,(stat,item) in specs.items():
        rows=ecos_series(key,stat,item,start,end); series[name]=rows
        for r in rows:
            # ECOS 901Y118 export/import amount unit is thousand USD; normalize to USD for dashboard consistency.
            by[r['month']][name]=r['value']*1000 if name in {'exports_usd','imports_usd'} else r['value']
        time.sleep(.12)
    monthly=[]
    for mon in sorted(by):
        row={'month':mon}; row.update(by[mon])
        if row.get('exports_usd') is not None and row.get('imports_usd') is not None: row['trade_balance_usd']=round(row['exports_usd']-row['imports_usd'],2)
        monthly.append(row)
    lookup={r['month']:r for r in monthly}
    for i,row in enumerate(monthly):
        prev=monthly[i-1] if i else {}; py=lookup.get(str(int(row['month'][:4])-1)+row['month'][4:]) if row.get('month') else {}
        for col in ['exports_usd','imports_usd','trade_balance_usd','export_value_index','export_volume_index','import_value_index','import_volume_index']:
            row[col+'_mom_pct']=pct(row.get(col),prev.get(col)); row[col+'_yoy_pct']=pct(row.get(col),(py or {}).get(col))
    return {'monthly':monthly[-36:],'latest':monthly[-1] if monthly else {},'series_status':{k:len(v) for k,v in series.items()}}
def customs_hs(key:str,hs:str,start:str,end:str)->list[dict[str,Any]]:
    if not key: return []
    all_rows=[]
    for page in range(1,21):
        url=CUSTOMS_BASE+'?'+urllib.parse.urlencode({'serviceKey':key,'strtYymm':start,'endYymm':end,'hsSgn':hs,'numOfRows':'999','pageNo':str(page)})
        with urllib.request.urlopen(url,timeout=30) as resp: raw=resp.read().decode('utf-8')
        if raw.strip().lower().startswith('unauthorized'): raise RuntimeError('customs API unauthorized')
        root=ET.fromstring(raw); code=root.findtext('.//resultCode')
        if code not in (None,'00'): raise RuntimeError(f"customs API resultCode={code} msg={root.findtext('.//resultMsg')}")
        items=root.findall('.//item')
        for item in items:
            d={c.tag:c.text for c in item}; d['hs_group']=hs; all_rows.append(d)
        total=sf(root.findtext('.//totalCount'))
        if not items or (total is not None and len(all_rows)>=int(total)) or len(items)<999: break
        time.sleep(.12)
    return all_rows

def yyyymm_add(mon:str, n:int)->str:
    y=int(mon[:4]); m=int(mon[4:6]); idx=y*12+(m-1)+n; yy,mm0=divmod(idx,12); return f'{yy}{mm0+1:02d}'
def customs_hs_range(key:str,hs:str,start:str,end:str)->list[dict[str,Any]]:
    rows=[]; cur=start
    while cur<=end:
        chunk_end=min(yyyymm_add(cur,11),end)
        rows.extend(customs_hs(key,hs,cur,chunk_end))
        cur=yyyymm_add(chunk_end,1); time.sleep(.15)
    return rows
def agg_customs(rows:list[dict[str,Any]],meta:dict[str,Any])->list[dict[str,Any]]:
    agg={}
    for r in rows:
        mon=str(r.get('year','')).replace('.','')[:6]
        if not mon or len(mon)!=6 or not mon.isdigit(): continue
        a=agg.setdefault(mon,{'month':mon,'hs_group':meta['hs'],'name':meta['name'],'theme':meta['theme'],'reason':meta['reason'],'export_usd':0.0,'export_kg':0.0,'import_usd':0.0,'import_kg':0.0,'balance_usd':0.0,'item_count':0,'top_items':[],'source':'Korea Customs Itemtrade'})
        exp=sf(r.get('expDlr')) or 0; imp=sf(r.get('impDlr')) or 0; ew=sf(r.get('expWgt')) or 0; iw=sf(r.get('impWgt')) or 0; bal=sf(r.get('balPayments'))
        a['export_usd']+=exp; a['import_usd']+=imp; a['export_kg']+=ew; a['import_kg']+=iw; a['balance_usd']+=bal if bal is not None else exp-imp; a['item_count']+=1
        a['top_items'].append({'hs_code':r.get('hsCode'),'name':r.get('statKor'),'export_usd':exp,'import_usd':imp})
    out=[]
    for a in agg.values():
        a['export_unit_usd_per_kg']=round(a['export_usd']/a['export_kg'],4) if a['export_kg'] else None; a['import_unit_usd_per_kg']=round(a['import_usd']/a['import_kg'],4) if a['import_kg'] else None
        a['top_items']=sorted(a['top_items'],key=lambda x:x['export_usd'],reverse=True)
        for k in ['export_usd','import_usd','export_kg','import_kg','balance_usd']: a[k]=round(a[k],2)
        out.append(a)
    out.sort(key=lambda x:x['month']); lookup={r['month']:r for r in out}
    for i,row in enumerate(out):
        prev=out[i-1] if i else {}; py=lookup.get(str(int(row['month'][:4])-1)+row['month'][4:]) if row.get('month') else {}
        for col in ['export_usd','export_kg','export_unit_usd_per_kg','import_usd','import_kg','import_unit_usd_per_kg','balance_usd']:
            row[col+'_mom_pct']=pct(row.get(col),prev.get(col)); row[col+'_yoy_pct']=pct(row.get(col),(py or {}).get(col))
    hs_by_month={r['month']:{t['hs_code']:t for t in r.get('top_items',[])} for r in out}
    for row in out:
        py_month=str(int(row['month'][:4])-1)+row['month'][4:]
        pm_month=yyyymm_add(row['month'],-1)
        py_hs=hs_by_month.get(py_month,{}); pm_hs=hs_by_month.get(pm_month,{})
        for t in row.get('top_items',[]):
            py_t=py_hs.get(t.get('hs_code'),{}); pm_t=pm_hs.get(t.get('hs_code'),{})
            t['export_usd_yoy_pct']=pct(t.get('export_usd'),py_t.get('export_usd'))
            t['import_usd_yoy_pct']=pct(t.get('import_usd'),py_t.get('import_usd'))
            t['export_usd_mom_pct']=pct(t.get('export_usd'),pm_t.get('export_usd'))
            t['import_usd_mom_pct']=pct(t.get('import_usd'),pm_t.get('import_usd'))
        row['top_items']=row['top_items'][:3]
    return out
def build_customs(key:str,start:str,end:str)->dict[str,Any]:
    monthly=[]; errors=[]
    for group in HS_GROUPS:
        try: monthly.extend(agg_customs(customs_hs_range(key,group['hs'],start,end),group)); time.sleep(.2)
        except Exception as exc: errors.append(f"{group['hs']} {group['name']}: {exc}")
    latest=max((r['month'] for r in monthly),default=''); rows=[r for r in monthly if r['month']==latest]; summary=[]
    for r in rows:
        uy,vy,vyv=r.get('export_unit_usd_per_kg_yoy_pct'),r.get('export_kg_yoy_pct'),r.get('export_usd_yoy_pct'); sig='중립'
        if uy is not None and vy is not None:
            if uy>5 and vy>0: sig='가격+물량 동반 개선'
            elif uy>5 and vy<0: sig='단가 방어/물량 둔화'
            elif uy<-5 and vy>0: sig='물량 증가/단가 압박'
            elif uy<-5 and vy<0: sig='가격+물량 동반 악화'
        summary.append({'month':r['month'],'hs_group':r['hs_group'],'name':r['name'],'theme':r['theme'],'export_usd':r['export_usd'],'export_usd_yoy_pct':vyv,'export_kg_yoy_pct':vy,'export_unit_usd_per_kg':r.get('export_unit_usd_per_kg'),'export_unit_usd_per_kg_yoy_pct':uy,'balance_usd':r.get('balance_usd'),'signal':sig,'top_items':r.get('top_items',[])})
    summary.sort(key=lambda x:(x.get('export_usd') or 0),reverse=True)
    return {'monthly':monthly[-len(HS_GROUPS)*36:],'latest_month':latest,'summary':summary,'errors':errors,'hs_groups':HS_GROUPS}
def verdict(ecos:dict[str,Any],customs:dict[str,Any])->dict[str,Any]:
    latest=ecos.get('latest') or {}; rows=customs.get('summary') or []; ex=latest.get('exports_usd_yoy_pct'); im=latest.get('imports_usd_yoy_pct'); bal=latest.get('trade_balance_usd')
    strong=[r for r in rows if r.get('signal')=='가격+물량 동반 개선']; weak=[r for r in rows if r.get('signal')=='가격+물량 동반 악화']; stance,title='UNKNOWN','수출입 데이터 수집 대기'
    if latest:
        if ex is not None and ex>0 and (bal or 0)>0: stance,title='POSITIVE','수출 모멘텀 우위'
        elif ex is not None and ex<0 and len(weak)>=len(strong): stance,title='NEGATIVE','수출 단가/물량 압박'
        else: stance,title='MIXED','수출입 신호 혼재'
    reasons=[]
    if latest:
        reasons.append(f"ECOS 수출 YoY {ex if ex is not None else 'n/a'}%, 수입 YoY {im if im is not None else 'n/a'}%")
        if bal is not None: reasons.append(f'무역수지 {bal:,.0f} (ECOS 단위 기준)')
    if strong: reasons.append('품목 개선: '+', '.join(r['name'] for r in strong[:3]))
    if weak: reasons.append('품목 악화: '+', '.join(r['name'] for r in weak[:3]))
    return {'stance':stance,'title':title,'reasons':reasons[:5],'positive_count':len(strong),'negative_count':len(weak)}
def write_outputs(payload:dict[str,Any])->None:
    OUT_DIR.mkdir(parents=True,exist_ok=True); (OUT_DIR/'latest_trade_import_export_analysis.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    for key,fname in [('customs','customs_item_unit_price_monthly.csv'),('ecos','ecos_trade_macro_monthly.csv')]:
        rows=payload.get(key,{}).get('monthly',[])
        if rows:
            cols=sorted({k for r in rows for k in r.keys() if k!='top_items'})
            with (OUT_DIR/fname).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--months',type=int,default=25); args=ap.parse_args(); ecos_key,customs_key=load_keys(); start,end=month_range(args.months)
    ecos=build_ecos(ecos_key,start,end); customs=build_customs(customs_key,start,end)
    payload={'updated_at':datetime.now().isoformat(timespec='seconds'),'source_decision':{'primary':'hybrid','macro':'ECOS','item_unit_price':'Korea Customs/data.go.kr Itemtrade','reason':'ECOS는 총수출/총수입/무역수지/지수에 강하고, 관세청은 HS 품목별 금액·중량 기반 단가 분석에 필요'},'period':{'start':start,'end':end},'ecos':ecos,'customs':customs,'verdict':verdict(ecos,customs)}
    write_outputs(payload)
    print(json.dumps({'updated_at':payload['updated_at'],'ecos_latest':payload['ecos'].get('latest'),'customs_latest_month':payload['customs'].get('latest_month'),'customs_summary_rows':len(payload['customs'].get('summary',[])),'customs_errors':payload['customs'].get('errors',[]),'verdict':payload['verdict'],'path':str(OUT_DIR/'latest_trade_import_export_analysis.json')},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())

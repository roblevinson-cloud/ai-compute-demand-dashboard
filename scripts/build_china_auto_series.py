"""Build one auditable monthly panel; never manufacture missing observations.

China-reported FOB customs history takes priority; newer country observations
use importer reports. Global value and volume each carry their own provenance.
"""
from __future__ import annotations
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/china-auto/data'
SOURCES = {
 'comtrade_china': {'label':'China customs / UN Comtrade','url':'https://comtradeplus.un.org/TradeFlow','scope':'HS 8703; China-reported exports, FOB'},
 'gacc_portal': {'label':'GACC / China Data Portal','url':'https://chinadata.live/china-trade/hs/8703/','scope':'HS 8703; China-reported export value, FOB'},
 'comtrade_mirror': {'label':'Destination customs / UN Comtrade','url':'https://comtradeplus.un.org/TradeFlow','scope':'HS 8703; destination-reported imports from China; arrival timing, usually CIF'},
 'cpca': {'label':'CPCA / CADA monthly release','url':'https://www.cada.cn/Trends/list_91_1.html','scope':'Passenger vehicles including complete vehicles and CKD kits; industry scope differs from HS 8703'},
}

def months(start, end):
 y,m=map(int,start.split('-'))
 while f'{y:04d}-{m:02d}'<=end:
  yield f'{y:04d}-{m:02d}'
  m+=1
  if m==13:y,m=y+1,1

def shift(p,n):
 y,m=map(int,p.split('-'));i=y*12+m-1+n
 return f'{i//12:04d}-{i%12+1:02d}'

def read(name,default=None):
 p=DATA/name
 return json.loads(p.read_text()) if p.exists() else default

def write_csv(name,rows):
 if not rows:return
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (DATA/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def unique_index(rows,key):
 out={}
 for r in rows:
  k=key(r)
  if k in out:raise ValueError(f'Duplicate observation: {k}')
  out[k]=r
 return out

def annotate_growth(rows):
 ix={(r['iso3'],r['period']):r for r in rows}
 for r in rows:
  for metric in ('units','value_usd'):
   for label,delta in [('mom',-1),('yoy',-12)]:
    prev=ix.get((r['iso3'],shift(r['period'],delta)))
    val=r.get(metric);old=prev.get(metric) if prev else None
    r[f'{metric}_{label}']=val/old-1 if val is not None and old is not None and old>0 else None
    r[f'{metric}_{label}_partial_input']=bool(metric=='units' and prev and (r.get('units_status')=='reported_subtotal_lower_bound' or prev.get('units_status')=='reported_subtotal_lower_bound'))
    source_key='units_source' if metric=='units' else 'value_source'
    r[f'{metric}_{label}_source_break']=bool(r[f'{metric}_{label}'] is not None and (r.get(source_key)!=prev.get(source_key) or (metric=='value_usd' and r.get('value_basis')!=prev.get('value_basis'))))
 return rows

def build(hist,cur,industry):
 hr=unique_index(hist['records'],lambda r:(r['period'],r['iso3']))
 hw=unique_index(hist['world_totals'],lambda r:r['period'])
 mr=unique_index([r for r in cur['mirror']['records'] if r['iso3'] not in ('CHN','W00')],lambda r:(r['period'],r['iso3']))
 gv=unique_index(cur['gacc']['monthly_value'],lambda r:r['period'])
 cv=unique_index(industry.get('records',[]),lambda r:r['period'])
 latest=max(list(hw)+list(gv)+[p for p,i in mr])
 periods=list(months('2020-01',latest))
 # Do not use partial destination sums when a published world total exists.
 world=[]
 for p in periods:
  h=hw.get(p,{});g=gv.get(p,{});c=cv.get(p,{})
  value=h.get('value_usd') if h.get('value_usd') is not None else g.get('value_usd')
  units=h.get('units') if h.get('units') is not None else c.get('units')
  vs='comtrade_china' if h.get('value_usd') is not None else 'gacc_portal' if value is not None else None
  us='comtrade_china' if h.get('units') is not None else 'cpca' if units is not None else None
  unit_status='reported';unit_note=None;quantity_value_coverage=None
  # A historical world quantity can be missing although all destination values
  # nearly reconcile. Expose the reported-unit subtotal as a lower bound, never as an
  # exact total. Do not apply this rule to partial recent mirror reporting.
  if units is None and p in hw:
   dest=[r for (period,iso),r in hr.items() if period==p]
   total_value=sum(r.get('value_usd') or 0 for r in dest)
   measured=[r for r in dest if r.get('units') is not None]
   measured_value=sum(r.get('value_usd') or 0 for r in measured)
   quantity_value_coverage=measured_value/value if value else None
   if value and total_value<=value and quantity_value_coverage>=.999:
    units=sum(r['units'] for r in measured);us='comtrade_china';unit_status='reported_subtotal_lower_bound'
    unit_note=f'Published world quantity missing. Sum of reported named-destination quantities covering {quantity_value_coverage:.6%} of world export value; USD {value-measured_value:g} is unallocated or lacks quantity. Not an exact global total.'
  world.append({'period':p,'iso3':'WLD','country':'World','region':'World','units':units,'value_usd':value,
   'units_source':us,'value_source':vs,'value_basis':'FOB' if value is not None else None,
   'units_source_url':c.get('url') if us=='cpca' else SOURCES[us]['url'] if us else None,
   'value_source_url':SOURCES[vs]['url'] if vs else None,
   'units_scope':SOURCES[us]['scope'] if us else None,
   'status':'partial' if unit_status!='reported' else 'reported' if units is not None and value is not None else 'partial',
   'units_status':unit_status,'units_note':unit_note,'quantity_value_coverage':quantity_value_coverage,
   'unit_value_usd':value/units if units and value is not None and us=='comtrade_china' and unit_status=='reported' else None,
   'unit_value_note':'Not calculated across different customs and industry scopes' if us=='cpca' else 'Customs value per reported item; not a retail price',
   'qty_estimated':h.get('qty_estimated') if us=='comtrade_china' else False})
 countries={}
 for r in list(hr.values())+list(mr.values()):
  countries.setdefault(r['iso3'],{k:r.get(k) for k in ('iso3','country','region')})
 rows=[]
 for iso,country in sorted(countries.items()):
  for p in periods:
   h=hr.get((p,iso));m=mr.get((p,iso))
   src='comtrade_china' if h else 'comtrade_mirror' if m else None
   r=h or m or {};value=r.get('value_usd') if h else (r.get('fob_value_usd') if r.get('fob_value_usd') is not None else r.get('mirror_value_usd'))
   units=r.get('units')
   basis='FOB' if h or r.get('fob_value_usd') is not None else 'CIF/import value' if m else None
   rows.append({**country,'period':p,'units':units,'value_usd':value,'units_source':src if units is not None else None,
    'value_source':src if value is not None else None,'value_basis':basis,
    'units_source_url':SOURCES[src]['url'] if src and units is not None else None,
    'value_source_url':SOURCES[src]['url'] if src and value is not None else None,
    'qty_estimated':r.get('qty_estimated',False),'status':'reported' if h or m else 'not_reported',
    'unit_value_usd':value/units if units and value is not None else None})
 annotate_growth(world);annotate_growth(rows)
 coverage=[]
 for p in periods:
  pr=[r for r in rows if r['period']==p];h=[r for r in pr if r['value_source']=='comtrade_china'];m=[r for r in pr if r['value_source']=='comtrade_mirror']
  w=next(r for r in world if r['period']==p)
  hv=sum(r['value_usd'] for r in h)
  coverage.append({'period':p,'china_destinations':len(h),'mirror_destinations':len(m),
   'unit_destinations':sum(r['units'] is not None for r in pr),'value_destinations':sum(r['value_usd'] is not None for r in pr),
   'missing_destinations':sum(r['status']=='not_reported' for r in pr),
   'world_value_usd':w['value_usd'],'world_units':w['units'],
   'historical_unallocated_value_usd':w['value_usd']-hv if h and w['value_source']=='comtrade_china' else None})
 # Keep the overlap so analysts can measure the source discontinuity rather than guess.
 overlap=[]
 for key,h in hr.items():
  m=mr.get(key)
  if not m:continue
  mv=m.get('fob_value_usd') if m.get('fob_value_usd') is not None else m.get('mirror_value_usd')
  overlap.append({'period':key[0],'iso3':key[1],'country':h['country'],'china_units':h.get('units'),
   'mirror_units':m.get('units'),'china_value_usd':h.get('value_usd'),'mirror_value_usd':mv,
   'mirror_value_basis':'FOB' if m.get('fob_value_usd') is not None else 'CIF/import value',
   'units_difference_pct':m['units']/h['units']-1 if m.get('units') is not None and h.get('units') else None,
   'mirror_qty_estimated':m.get('qty_estimated',False)})
 return {'meta':{'title':'China Auto Export Monitor','built_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
  'start_period':periods[0],'latest_period':latest,'months':len(periods),'history_updated_at':hist['meta'].get('updated_at_utc'),
  'current_updated_at':cur['meta'].get('updated_at_utc'),'china_reported_latest':max(hw),'industry_latest':max(cv) if cv else None,
  'value_months':sum(r['value_usd'] is not None for r in world),'unit_months':sum(r['units'] is not None for r in world),'unit_subtotal_months':[r['period'] for r in world if r['units_status']!='reported'],
  'methodology':'METHOD.md','refresh_errors':hist['meta'].get('refresh_errors',[])+cur['gacc'].get('errors',[])+cur['mirror'].get('errors',[])+industry.get('refresh_errors',[])},
  'sources':SOURCES,'periods':periods,'countries':sorted(countries.values(),key=lambda r:r['country']),
  'world':world,'records':rows,'coverage':coverage,'overlap':overlap,
  'latest_gacc_partners':cur['gacc'].get('latest_partners',[])}

def main():
 payload=build(read('exports.json'),read('current.json'),read('industry_units.json',{'records':[]}))
 if payload['meta']['value_months']!=payload['meta']['months']:raise ValueError('Global monthly value has gaps')
 write_csv('world_monthly.csv',payload['world']);write_csv('destination_monthly.csv',payload['records']);write_csv('coverage.csv',payload['coverage']);write_csv('source_overlap.csv',payload['overlap'])
 columns=['period','iso3','units','value_usd','units_source','value_source','value_basis','qty_estimated','status','unit_value_usd']
 compact={**payload,'record_columns':columns,'records':[[r.get(k) for k in columns] for r in payload['records']]}
 compact.pop('overlap',None)
 (DATA/'series.json').write_text(json.dumps(compact,ensure_ascii=False,separators=(',',':')))
 print(json.dumps(payload['meta'],indent=2))

if __name__=='__main__':main()

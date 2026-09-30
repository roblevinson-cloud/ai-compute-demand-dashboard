"""Refresh CPCA passenger export units from public CADA monthly releases.

Exact month + passenger-export + CKD phrase required. Never parse a nearby
all-vehicle total, YTD number or NEV-only figure. Preserve all saved records
when a source is unavailable or its layout changes.
"""
import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/china-auto/data/industry_units.json'
BASE='https://www.cada.cn'

def parse_units(text,period):
    month=int(period[5:])
    plain=html.unescape(re.sub('<[^>]+>',' ',text))
    plain=re.sub(r'\s+',' ',plain)
    match=re.search(rf'(?<!\d){month}月乘用车出口\s*[（(]含整车与CKD[）)]\s*([\d.]+)万辆',plain)
    if not match:raise ValueError(f'{period}: precise monthly passenger-export phrase not found')
    units=round(float(match[1])*10000)
    if not 10000<units<5000000:raise ValueError(f'{period}: implausible units {units}')
    return {'period':period,'units':units,'reported_number':match[1],'reported_unit':'10,000 vehicles'}

def get(session,url):
    r=session.get(url,timeout=40);r.raise_for_status();r.encoding='utf-8';return r.text

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--full',action='store_true');args=ap.parse_args()
    saved=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {'records':[]}
    old={r['period']:r for r in saved['records']};links={};errors=[];session=requests.Session()
    for i in range(1,16 if args.full else 4):
        url=f'{BASE}/Trends/list_91_{i}.html'
        try:
            for href,title in re.findall(r'<a[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',get(session,url),re.S):
                title=html.unescape(re.sub('<[^>]+>','',title)).strip()
                m=re.fullmatch(r'(20\d{2})年(\d+)月份?全国乘用车市场分析',title)
                if m:
                    period=f'{m[1]}-{int(m[2]):02d}'
                    if period>='2025-01':links[period]=urljoin(BASE,href)
        except Exception as e:errors.append({'url':url,'error':str(e)})
    for p in sorted(old)[-3:] if not args.full else old:
        links.setdefault(p,old[p]['url'])
    checked=0
    for p,url in sorted(links.items()):
        try:old[p]={**parse_units(get(session,url),p),'url':url};checked+=1
        except Exception as e:errors.append({'period':p,'url':url,'error':str(e)})
    saved.update({'source':'CPCA monthly market releases published by CADA',
        'scope':'Passenger vehicles including complete vehicles and CKD kits; not the HS 8703 customs population. Original monthly releases; later revisions can change published YoY rates.',
        'last_attempt_utc':datetime.now(timezone.utc).isoformat(),'refresh_errors':errors,
        'records':[old[p] for p in sorted(old)]})
    if checked:saved['retrieved_at']=datetime.now(timezone.utc).date().isoformat()
    OUTPUT.write_text(json.dumps(saved,ensure_ascii=False,indent=2));print(f'CPCA: {len(old)} stored months; {checked} refreshed; {len(errors)} errors')

if __name__=='__main__':main()

"""Reproduce the dated Nov 18 revision audit against its parent and current panel.
Run manually after refreshing/building the source panel. Requires repository history.
"""
import csv
import io
import json
import subprocess
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs/china-auto'
DATA=SITE/'data'
REF='022e998e7b8a312eeaf094235bf13c184bb1cb72'

def snapshot(ref,name):
    raw=subprocess.check_output(['git','show',f'{ref}:docs/china-auto/data/{name}'],cwd=ROOT)
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))

def local(name):
    return list(csv.DictReader((DATA/name).read_text(encoding='utf-8-sig').splitlines()))

def changes(a,b):
    old={(r['iso3'],r['period']):r for r in a}
    out=[]
    for r in b:
        p=old.get((r['iso3'],r['period']),{})
        if not any(p.get(k,'')!=r.get(k,'') for k in ('units','value_usd','status')):continue
        if not p and r['status']=='not_reported':continue
        out.append({'country':r['country'],'iso3':r['iso3'],'period':r['period'],
                    **{f'{side}_{k}':row.get(k,'') for side,row in [('before',p),('after',r)] for k in ['units','value_usd','status']},
                    'units_yoy':r.get('units_yoy',''),'qty_estimated':r['qty_estimated'],'value_basis':r['value_basis']})
    return out

def n(v):return 'Not reported' if v in ('',None) else f'{float(v):,.3f}'.rstrip('0').rstrip('.')
def pct(v):return '—' if v in ('',None) else f'{float(v)*100:+.1f}%'
def table(head,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join(f'<th>{escape(h)}</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(str(v))}</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table></div>'
def main():
    a=snapshot(REF+'^','destination_monthly.csv');b=snapshot(REF,'destination_monthly.csv');c=local('destination_monthly.csv')
    delta=changes(a,b);later=changes(b,c)
    world=local('world_monthly.csv');w={r['period']:r for r in world}
    before=snapshot(REF+'^','world_monthly.csv');at=snapshot(REF,'world_monthly.csv')
    assert before==at, 'Recheck national revisions at the cited commit'
    cov_a={r['period']:r for r in snapshot(REF+'^','coverage.csv')};cov_b={r['period']:r for r in snapshot(REF,'coverage.csv')};cov_c={r['period']:r for r in local('coverage.csv')}
    def total(year,field,through='09'):
        return sum(float(r[field] or 0) for r in world if r['period'].startswith(year) and r['period'][5:]<=through)
    ytd=total('2026','units');ytd25=total('2025','units');ten=total('2026','units','10');fy25=total('2025','units','12')
    q3=sum(float(w['2026-'+m]['units']) for m in ['07','08','09']);sep=float(w['2026-09']['units']);october=float(w['2026-10']['units'])
    run=ten+2*october
    meta=json.loads((DATA/'series.json').read_text())['meta']
    summary={'as_of':'2026-11-20','source_commit':REF,'comparison_parent':subprocess.check_output(['git','rev-parse',REF+'^'],cwd=ROOT,text=True).strip(),
        'latest_repository_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'national_at_source_commit_unchanged':True,'nov18_destination_revisions':delta,'subsequent_destination_revisions':later,
        'latest_units_period':meta['industry_latest'],'latest_value_period':max(r['period'] for r in world if r['value_usd']),
        'jan_sep_units':ytd,'jan_sep_units_yoy':ytd/ytd25-1,'jan_oct_units':ten,'jan_oct_units_yoy_from_stored_months':ten/total('2025','units','10')-1,
        'september_units_annualized':sep*12,'q3_units_annualized':q3*4,'october_units_annualized':october*12,
        'fy2026_if_nov_dec_equal_october':run,'fy2025_stored_units':fy25,
        'refresh_errors':meta['refresh_errors']}
    (DATA/'revision_review_2026-11-20.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (DATA/'revision_audit_2026-11-18.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(delta[0]));writer.writeheader();writer.writerows(delta)
    revtable=table(['Destination / month','Units before','Units after','USD before','USD after','Unit YoY','Quantity flag'],[
        [r['country']+' / '+r['period'],n(r['before_units']),n(r['after_units']),n(r['before_value_usd']),n(r['after_value_usd']),pct(r['units_yoy']),'Estimated' if r['qty_estimated']=='True' else 'Reported'] for r in delta])
    latertable=table(['Destination / month','Units before','Units now','USD now','Unit YoY','Quantity flag'],[
        [r['country']+' / '+r['period'],n(r['before_units']),n(r['after_units']),n(r['after_value_usd']),pct(r['units_yoy']),'Estimated' if r['qty_estimated']=='True' else 'Reported'] for r in later])
    metrics=table(['Measure','Latest result','Interpretation'],[
        ['Jan–Sep passenger exports',f'{ytd/1e6:.3f}m / {pct(ytd/ytd25-1)} YoY','CPCA; complete vehicles + CKD'],
        ['September passenger exports',f'{sep:,.0f} / {pct(float(w["2026-09"]["units_yoy"]))} YoY',f'{sep*12/1e6:.3f}m annualized; unchanged Nov 18'],
        ['Jan–Sep HS 8703 value',f'${total("2026","value_usd")/1e9:.3f}bn / {pct(total("2026","value_usd")/total("2025","value_usd")-1)} YoY','Latest saved customs values; different scope from CPCA units'],
        ['Q3 passenger exports',f'{q3/1e6:.3f}m',f'{q3*4/1e6:.3f}m annualized'],
        ['October passenger exports',f'{october:,.0f} / {pct(float(w["2026-10"]["units_yoy"]))} YoY from stored months',f'{pct(october/sep-1)} MoM; {october*12/1e6:.3f}m annualized'],
        ['Jan–Oct passenger exports',f'{ten/1e6:.3f}m / {pct(ten/total("2025","units","10")-1)} YoY','Sum of original monthly observations'],
        ['2026 mechanical projection',f'{run/1e6:.3f}m / {pct(run/fy25-1)} vs stored 2025','Jan–Oct actual + two months at October volume; not guidance']])
    coverage=table(['Month','Before Nov 18','At Nov 18','Latest refresh'],[[p,cov_a[p]['mirror_destinations'],cov_b[p]['mirror_destinations'],cov_c[p]['mirror_destinations']] for p in ['2026-08','2026-09']])
    scenarios=[]
    for name,g,h in [('Downside',-.05,0),('Illustrative base',.10,.08),('Upside',.20,.15)]:
        scenarios.append([name,pct(g),f'{run*(1+g)/1e6:.2f}m',pct(h),f'{run*(1+g)*(1+h)**3/1e6:.2f}m'])
    scenario=table(['Sensitivity','2027 growth','2027 units','2028–30 annual growth','2030 units'],scenarios)
    national_old=sum(float(r['value_usd']) for r in at if r['period'].startswith('2026'))
    value_delta=total('2026','value_usd')-national_old
    body=f'''<header><div class="eyebrow">CHINA AUTO · RESEARCH UPDATE</div><h1>Reporting catches up; export momentum holds</h1><p>As of November 20, 2026 · November 18 revision audit and latest source refresh</p></header><main>
<section class="panel"><h2>Investment conclusion</h2><p>The cited November 18 refresh improves destination coverage; it does not revise national volume or value and does not change the 2026 national run-rate. October CPCA volume, newly fetched for this update, is 928,000 vehicles. Momentum remains strong year over year, with a much slower sequential pace. The data support continued overseas competitive pressure, but do not establish a 2027–2030 growth rate or Chinese-brand market share.</p><p><a href="./">Open interactive monitor</a> · <a href="data/revision_audit_2026-11-18.csv">Download exact revision CSV</a> · <a href="data/revision_review_2026-11-20.json">Download review inputs and calculations</a></p></section>
<section class="panel"><h2>What actually changed on November 18</h2><p>Compared with the cited commit’s immediate parent, seven destination observations changed. Four September rows moved from missing to reported: Czechia, Estonia, Japan and El Salvador. Croatia gained August reporting. Japan’s July and August values received tiny corrections with unchanged quantities. Germany’s September row remains missing: it appears as diff context, not as a changed observation.</p>{revtable}<p>September’s observed destination-unit subtotal rose from 69,911.505 to 81,753.181 (+11,841.676; +16.9%). This is a reporting-sample expansion, not a 16.9% increase in China’s exports. These rows mix estimated quantities and FOB/CIF import values; neither their sum nor their unit values should replace a national total or retail ASP.</p>{coverage}<p>Only 14 of 202 destinations reported September at that commit, versus 10 before it. August increased from 45 to 46. Missing markets must stay missing. The small September sample cannot establish regional share or which incumbent lost sales.</p></section>
<section class="panel"><h2>Subsequent changes retained in this full update</h2>{latertable}<p>The fresh source requests preserve these later arrivals. National Jan–Sep customs value is now ${total('2026','value_usd')/1e9:.6f}bn, a change of ${value_delta:,.0f} versus November 18 ({pct(value_delta/national_old)} at one-decimal precision). Volume through September is unchanged. The November 18 national files were exactly unchanged versus their parent; later small value corrections are a separate event.</p></section>
<section class="panel"><h2>2026 trend and run-rate</h2>{metrics}<p>October’s original CPCA release reports +68.5% YoY. Our saved original monthly observations yield +63.4% October YoY (928k / 568k − 1). The discrepancy suggests different data vintages or definitions; the exact cause has not been reconciled. We do not infer revised historical months from a reported growth rate. We retain original monthly levels and distinguish release growth from recomputed growth. The release also reports 810k own-brand and 118k joint-venture/luxury exports in October, illustrating why China-origin exports are broader than Chinese-brand sales.</p><p>Quarterly volume rose from 1.826m in Q1 to 2.430m in Q2 and 2.723m in Q3. September increased 3.3% MoM; October increased 1.2% from the saved September level. This is sequential moderation at a high level, not evidence of export contraction. A November–December pace of 0.8–1.0m per month gives roughly 9.51–9.91m for 2026. These calculations include CKD kits and are not finished-vehicle shipping capacity requirements.</p><p>October customs value and destination observations remain blank until reported. National value per vehicle is not calculated by dividing HS 8703 value by CPCA units because the populations differ.</p></section>
<section class="panel"><h2>What changes for 2027–2030</h2><p>The November 18 revisions alone warrant no change to a national export forecast. They strengthen the evidence for specific reported destinations, but do not prove broad European penetration or invalidate a plateau risk. October’s volume confirms a high exit pace; it provides no basis to extend 2026’s roughly 75% year-to-date growth for another four years.</p><p>For competitive analysis, use Chinese OEM destination retail sales = China-origin deliveries sold locally + locally manufactured vehicles sold locally, with inventory and re-exports reconciled. CKD kits counted in exports can become locally assembled vehicles: adding the two series without reconciling kits double counts demand. Production abroad and exports are alternative supply routes, so export flattening can coexist with further Chinese OEM share gains.</p>{table(['Region','How to assess incumbent displacement','What this refresh establishes'],[['Europe','Match country, segment, price, powertrain and registrations; include local output and inventory','Czechia and Estonia additions; Germany still missing. No Europe-wide share estimate.'],['Latin America','Track Brazil/Mexico and other countries separately; include local assembly and kit treatment','El Salvador addition is small and quantity-estimated; no regional extrapolation.'],['North America','Separate US, Canada and Mexico; test market access and local production separately','No new evidence in this diff sufficient to change a regional share forecast.']])}<p>The practical Stellantis question is how many additional Chinese OEM retail sales overlap its B/C cars and crossovers, at what transaction prices, in each European market. Export growth alone cannot be assigned one-for-one to Stellantis lost production. Total-market growth, other incumbent losses, inventories and Stellantis’s own launches must be included.</p><p>The following is a transparent sensitivity, not external research or a fitted forecast. It starts from the {run/1e6:.3f}m mechanical 2026 projection above. 2030 = 2026 × (1 + 2027 growth) × (1 + 2028–2030 annual growth)^3. It measures exports including CKD, not total Chinese OEM overseas sales.</p>{scenario}<p>Watch for falling same-source national exports over several months, sustained destination registrations below arrivals, discounting and inventory build, barriers to market access, and local production replacing shipments. None of the November 18 reporting additions by themselves resolve those risks.</p></section>
<section class="panel"><h2>Sources, freshness and limits</h2><ul><li><a href="https://github.com/roblevinson-cloud/ai-compute-demand-dashboard/commit/{REF}">November 18 source commit and exact parent comparison</a>; later changes use the repository snapshots plus the fresh November 20 requests.</li><li><a href="https://www.cada.cn/Trends/info_91_10597.html">CADA / CPCA October original monthly release</a>, retrieved November 20. Monthly units include complete vehicles and CKD.</li><li><a href="https://chinadata.live/china-trade/hs/8703/">GACC via China Data Portal HS 8703 chart</a> and <a href="https://comtradeplus.un.org/TradeFlow">UN Comtrade</a>; monthly source URLs and quantity flags remain in the downloads.</li></ul><p>Latest industry month: {meta['industry_latest']}; customs value: {summary['latest_value_period']}; complete China-reported destination history: {meta['china_reported_latest']}. Retrieval dates are not observation dates. Source refresh errors in this build: {len(meta['refresh_errors'])}. Full audit metadata is in the review JSON. <a href="METHOD.md">Methodology</a>.</p></section></main>'''
    (SITE/'review-2026-11-20.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>China auto exports: November 20 review</title><link rel="stylesheet" href="monitor.css"><style>body{font-size:16px}.panel p,.panel li{max-width:100ch}table{font-size:14px}.eyebrow{font-size:14px}.table-wrap{max-height:none}</style></head><body>'+body+'</body></html>')
    print(f'Review built: {len(delta)} Nov 18 revisions; {len(later)} later revisions; {ten:,.0f} Jan–Oct units')

if __name__=='__main__':main()

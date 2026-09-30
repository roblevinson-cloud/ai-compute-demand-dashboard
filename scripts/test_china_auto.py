import copy
import json
import unittest
from pathlib import Path
from build_china_auto_series import build, months, unique_index
from china_vehicle_current import preserve_snapshots
from china_vehicle_industry import parse_units

DATA=Path(__file__).resolve().parents[1]/'docs/china-auto/data'

class ChinaAutoTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.h=json.loads((DATA/'exports.json').read_text());cls.c=json.loads((DATA/'current.json').read_text());cls.i=json.loads((DATA/'industry_units.json').read_text());cls.d=build(cls.h,cls.c,cls.i)
 def test_contiguous_world_history(self):
  self.assertEqual(self.d['periods'],list(months('2020-01',self.d['meta']['latest_period'])))
  self.assertTrue(all(r['value_usd'] is not None for r in self.d['world']))
  # Complete at this release; future missing units must remain explicit rather than fabricated.
  rows=[r for r in self.d['world'] if r['period']<='2026-08']
  self.assertEqual(len(rows),80);self.assertTrue(all(r['units'] is not None for r in rows))
 def test_global_uses_published_totals(self):
  w={r['period']:r for r in self.d['world']}
  for r in self.h['world_totals']:
   self.assertEqual(w[r['period']]['value_usd'],r['value_usd'])
 def test_source_join_and_scope(self):
  w={r['period']:r for r in self.d['world']}
  self.assertEqual(w['2025-01']['units_source'],'cpca');self.assertTrue(w['2025-01']['units_mom_source_break'])
  self.assertIsNone(w['2025-01']['unit_value_usd'])
 def test_country_grid_and_no_self_trade(self):
  self.assertNotIn('CHN',{r['iso3'] for r in self.d['records']})
  self.assertEqual(len(self.d['records']),len(self.d['countries'])*len(self.d['periods']))
  unique_index(self.d['records'],lambda r:(r['iso3'],r['period']))
 def test_missing_country_is_not_zero(self):
  r=next(r for r in self.d['records'] if r['iso3']=='RUS' and r['period']=='2026-08')
  self.assertIsNone(r['units']);self.assertIsNone(r['value_usd']);self.assertEqual(r['status'],'not_reported')
 def test_mirror_foB_value_used_when_labelled_foB(self):
  r=next(r for r in self.c['mirror']['records'] if r['period']=='2025-01' and r['fob_value_usd'] is not None and r['iso3']!='CHN')
  out=next(v for v in self.d['records'] if v['iso3']==r['iso3'] and v['period']==r['period'])
  self.assertEqual(out['value_usd'],r['fob_value_usd']);self.assertEqual(out['value_basis'],'FOB')
 def test_failed_refresh_preserves_data(self):
  g,m=preserve_snapshots(self.c,{'monthly_value':[],'latest_partners':[]},{'records':[],'errors':['failure']})
  self.assertEqual(len(g['monthly_value']),len(self.c['gacc']['monthly_value']))
  self.assertEqual(len(m['records']),sum(r['iso3']!='CHN' for r in self.c['mirror']['records']))
 def test_precise_monthly_passenger_parser(self):
  self.assertEqual(parse_units('7月汽车出口（含整车与CKD）69.4万辆。7月乘用车出口（含整车与CKD）47.5万辆。','2025-07')['units'],475000)
  self.assertEqual(parse_units('2025年1-2月汽车整车出口97万辆。2月乘用车出口（含整车与CKD）34.9万辆。','2025-02')['units'],349000)
  with self.assertRaises(ValueError):parse_units('7月新能源车出口20万辆。','2025-07')
 def test_historical_missing_world_quantity_is_flagged_subtotal(self):
  r=next(r for r in self.d['world'] if r['period']=='2020-09')
  self.assertEqual(r['units_status'],'reported_subtotal_lower_bound');self.assertAlmostEqual(r['units'],178729.013)
  self.assertGreater(r['quantity_value_coverage'],.9999);self.assertIsNone(r['unit_value_usd'])
 def test_no_duplicate_acceptance(self):
  with self.assertRaises(ValueError):unique_index([{'p':'2020-01'},{'p':'2020-01'}],lambda r:r['p'])

if __name__=='__main__':unittest.main()

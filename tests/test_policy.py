import io
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from openpyxl import load_workbook
from monitor.core import connect,import_videos,report,review,week_bounds
from monitor.commercial import signals
from monitor.export import workbook,markdown


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=connect(Path(self.temp.name)/'test.db')
        self.start,self.end=week_bounds()

    def tearDown(self):self.db.close();self.temp.cleanup()

    def video(self,**kw):
        v=dict(platform='YouTube',url='https://youtu.be/policy00001',title='Yozma IN-10 review',creator='fixture',
            published_at=(self.start+timedelta(hours=1)).isoformat(),observed_at=(self.end-timedelta(hours=1)).isoformat(),
            source='isolated policy test',market='US',language='en',format='long',views=1000)
        v.update(kw);return v

    def test_discount_and_affiliate_are_primary_automatic_commercial_evidence(self):
        for description in ['Use code RIDE10 for 10% off','Buy: https://yozmasport.com/products/in-10?ref=creator123',
                            'https://yozmasport.com/discount/RIDE10']:
            with self.subTest(description=description):
                import_videos(self.db,[self.video(description=description)])
                r=report(self.db)
                self.assertEqual(r['summary']['published'],1)
                self.assertEqual(r['videos'][0]['cooperation'],'明确合作')
                self.assertTrue(r['videos'][0]['commercial_signals'])

    def test_no_discount_or_affiliate_requires_review_even_with_sponsorship_text(self):
        import_videos(self.db,[self.video(description='Sponsored by Yozma')])
        r=report(self.db);self.assertEqual(r['summary']['published'],0)
        self.assertEqual(r['summary']['pending'],1)
        review(self.db,{'id':'yt:policy00001','cooperation':'明确合作','evidence':'manually verified sponsorship'})
        self.assertEqual(report(self.db)['summary']['published'],1)
        import_videos(self.db,[self.video(description='No new code')])
        self.assertEqual(report(self.db)['summary']['published'],1)

    def test_999_excluded_1000_included_unknown_not_zero_and_records_preserved(self):
        for i,views in enumerate([999,1000,None]):
            import_videos(self.db,[self.video(url=f'https://youtu.be/policy{i:05d}',views=views,description='Use code RIDE10')])
        r=report(self.db)
        self.assertEqual(len(r['videos']),3)
        self.assertEqual(r['summary']['published'],1)
        self.assertEqual(r['summary']['known_views'],1000)
        self.assertEqual(r['summary']['excluded_low_views'],1)
        self.assertEqual(r['summary']['excluded_unknown_views'],1)
        self.assertEqual(sum(c['confirmed'] for c in r['creators']),1)

    def test_crossing_threshold_not_backfilled_into_old_week(self):
        import_videos(self.db,[self.video(views=999,description='Use code RIDE10')])
        import_videos(self.db,[self.video(views=5000,description='Use code RIDE10',observed_at=(self.end+timedelta(hours=1)).isoformat())])
        r=report(self.db)
        self.assertEqual(r['summary']['published'],0)
        self.assertEqual(r['videos'][0]['views'],999)

    def test_previous_week_threshold_uses_previous_cutoff(self):
        pub=self.start-timedelta(days=3)
        import_videos(self.db,[self.video(published_at=pub.isoformat(),observed_at=(self.start-timedelta(hours=1)).isoformat(),views=999,description='Use code RIDE10')])
        import_videos(self.db,[self.video(published_at=pub.isoformat(),views=1500,description='Use code RIDE10')])
        r=report(self.db)
        self.assertEqual(r['summary']['previous_videos'],0)
        self.assertTrue(r['videos'][0]['statistics_eligible'])

    def test_generic_purchase_utm_and_negated_discount_do_not_confirm(self):
        for text in ['Buy https://yozmasport.com/products/in-10',
                     'https://yozmasport.com/?utm_source=youtube',
                     'There is no discount code RIDE10',
                     'Discount code available below']:
            with self.subTest(text=text):self.assertEqual(signals(text),[])

    def test_high_views_without_priority_evidence_waits_for_review_before_weekly_viral(self):
        import_videos(self.db,[self.video(views=100000,description='A normal review')])
        r=report(self.db)
        self.assertEqual(r['summary']['published'],0)
        self.assertEqual(r['viral_candidates'],[])
        self.assertEqual(len(report(self.db,scope='suspected')['viral_candidates']),1)
        review(self.db,{'id':'yt:policy00001','cooperation':'明确合作','evidence':'manually verified record'})
        self.assertEqual(len(report(self.db)['viral_candidates']),1)

    def test_priority_order_and_compact_report_contract(self):
        text='Sponsored by Yozma. https://yozmasport.com/?ref=creator Use code RIDE10'
        self.assertEqual([s['kind'] for s in signals(text)],['折扣码','联盟链接'])
        import_videos(self.db,[self.video(description=text,views=80000)])
        r=report(self.db);doc=markdown(r);wb=load_workbook(io.BytesIO(workbook(r)))
        self.assertEqual([x.value for x in wb['爆款视频'][1]],['视频','标题','数据','关键词','内容方向'])
        for heading in ['## 关键信号','## 核心数据','## 趋势','## 爆款视频']:self.assertIn(heading,doc)
        for removed in ['各模块分析与总结','Qronge行动建议','封面、开场','推测（待核验）']:self.assertNotIn(removed,doc)
        self.assertIn('| 视频 | 标题 | 数据 | 关键词 | 内容方向 |\n|---',doc)
        self.assertLess(len(doc.splitlines()),65)

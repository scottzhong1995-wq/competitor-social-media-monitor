import io
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from monitor.core import connect,import_videos,week_bounds
from monitor.youtube import api,collect


class CollectorTests(unittest.TestCase):
    def test_monitored_account_retains_ordinary_videos_only_as_baseline(self):
        from monitor.profiles import upsert_account
        from monitor.core import report
        with tempfile.TemporaryDirectory() as folder:
            db=connect(Path(folder)/'test.db');start,_=week_bounds();aid='UC'+'x'*22
            with db:upsert_account(db,{'platform':'YouTube','account_id':aid,'creator':'fixture','monitor':True})
            def fake(resource,**params):
                if resource=='search':return {'items':[{'id':{'videoId':'checkvid001'}}] if params.get('channelId') else []}
                if resource=='channels':return {'items':[{'id':aid,'statistics':{}}]}
                return {'items':[{'id':'checkvid001','snippet':{'title':'A normal riding video','channelTitle':'fixture','channelId':aid,'publishedAt':(start+timedelta(hours=1)).isoformat()},'statistics':{'viewCount':'100'}}]}
            with patch('monitor.youtube.api',side_effect=fake):collect(db)
            self.assertEqual(db.execute('SELECT baseline_only FROM videos').fetchone()[0],1)
            self.assertEqual(report(db)['videos'],[])
            db.close()

    def test_retry_transient_and_preserve_key_redaction(self):
        with patch.dict('os.environ',{'YOUTUBE_API_KEY':'test-secret'}),patch('monitor.youtube.time.sleep') as sleep:
            with patch('monitor.youtube.urlopen',side_effect=[HTTPError('hidden',429,'rate',{},io.BytesIO(b'{}')),OSError('test-secret'),OSError('test-secret')]):
                with self.assertRaises(RuntimeError) as error:api('search',q='Yozma')
        self.assertEqual(sleep.call_count,2);self.assertNotIn('test-secret',str(error.exception))

    def test_deleted_video_keeps_snapshots_and_failed_refresh_keeps_values(self):
        with tempfile.TemporaryDirectory() as folder:
            db=connect(Path(folder)/'test.db');start,_=week_bounds()
            import_videos(db,[dict(platform='YouTube',url='https://youtu.be/checkvid001',title='Yozma IN-10 review',creator='test',
                published_at=(start+timedelta(hours=1)).isoformat(),observed_at=(start+timedelta(days=1)).isoformat(),source='fixture',views=500)])
            with patch('monitor.youtube.api',return_value={'items':[]}):collect(db)
            self.assertEqual(db.execute('SELECT availability FROM videos').fetchone()[0],'unavailable')
            with patch('monitor.youtube.api',side_effect=RuntimeError('quotaExceeded')):
                with self.assertRaises(RuntimeError):collect(db)
            self.assertEqual(db.execute('SELECT views FROM snapshots').fetchone()[0],500)
            self.assertEqual(db.execute('SELECT count(*) FROM snapshots').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM runs WHERE status='failed'").fetchone()[0],1)
            db.close()

    def test_pagination_and_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            db=connect(Path(folder)/'test.db');start,_=week_bounds()
            calls=[]
            def fake(resource,**params):
                calls.append((resource,params))
                if resource=='search':return {'items':[{'id':{'videoId':'checkvid001'}}],**({} if params.get('pageToken') else {'nextPageToken':'page2'})}
                if resource=='channels':return {'items':[{'id':'id','statistics':{}}]}
                return {'items':[{'id':'checkvid001','snippet':{'title':'Yozma IN-10 review','channelTitle':'fixture','channelId':'id','publishedAt':(start+timedelta(hours=1)).isoformat()},'statistics':{'viewCount':'100'}}]}
            with patch('monitor.youtube.api',side_effect=fake):collect(db,True)
            self.assertEqual(db.execute('SELECT count(*) FROM videos').fetchone()[0],1)
            self.assertTrue(any(params.get('pageToken')=='page2' for resource,params in calls if resource=='search'))
            self.assertEqual(db.execute('SELECT max(pages) FROM queries').fetchone()[0],2)
            db.close()

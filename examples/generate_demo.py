"""Generate explicitly synthetic examples in isolation; never touches real data."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from monitor.core import connect,import_videos,report,week_bounds,import_trends
from monitor.export import workbook,markdown


def generate(out=None):
    out=Path(out or Path(__file__).parent/'demo-output');out.mkdir(parents=True,exist_ok=True)
    start,end=week_bounds();items=[]
    def video(key,published,observed,views,**kw):
        item=dict(platform='YouTube',url='https://youtu.be/'+key,title='[DEMO] Yozma IN-10 Pro review',creator='DEMO测试账号',creator_id='demo-creator',
          published_at=published.isoformat(),observed_at=observed.isoformat(),views=views,likes=100,comments=10,format='long',market='US',language='en',
          source='DEMO：合成示例，不是真实监控',cooperation='明确合作',evidence='DEMO赞助披露',market_evidence='DEMO美国账号声明')
        item.update(kw);items.append(item)
    video('demoNEW0001',start+timedelta(hours=1),end-timedelta(hours=1),80000)
    video('demoNEW0002',start+timedelta(hours=2),end-timedelta(hours=1),None,title='[DEMO] Tuttio Soleil01 GB Pro off-road first ride',cooperation='疑似合作',evidence='DEMO折扣码',market='unknown',format='short')
    target=start-timedelta(days=10)
    for i in range(10):
        pub=target-timedelta(days=(i+1)*2)
        video(f'demoB{i:06d}',pub,pub+timedelta(days=7),100,creator='DEMO同龄样本账号',creator_id='demo-baseline',baseline_only=True)
    video('demoREL0001',target,target+timedelta(days=7),400,creator='DEMO同龄样本账号',creator_id='demo-baseline')
    with tempfile.TemporaryDirectory() as folder:
        db=connect(Path(folder)/'demo.db');import_videos(db,items)
        stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['series_id','query','week','value','source','geo','search_type'])
        for i in range(12):writer.writerow(['DEMO-shared-normalization','Yozma',(start.date()-timedelta(weeks=11-i)).isoformat(),20+i*3,'DEMO合成趋势','US','web'])
        import_trends(db,stream.getvalue())
        r=report(db);r['data_label']='DEMO：全部为合成示例，不代表真实品牌合作、红人表现或搜索热度'
        (out/'demo-weekly.xlsx').write_bytes(workbook(r))
        (out/'demo-weekly.md').write_text(markdown(r),encoding='utf-8')
        (out/'demo-videos.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        db.close()
    return out


if __name__=='__main__':print(generate())

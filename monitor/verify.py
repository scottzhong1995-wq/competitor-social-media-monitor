"""Read official pages and produce an evidence ledger, without inventing names."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .settings import load, ROOT
from .core import stamp


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.title='';self.in_title=False;self.accounts=set()

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='meta' and attrs.get('property')=='og:title': self.title=attrs.get('content','')
        href=attrs.get('href','')
        if href.startswith(('https://www.youtube.com/','https://youtube.com/','https://www.instagram.com/','https://instagram.com/','https://www.tiktok.com/','https://tiktok.com/')):
            self.accounts.add(href)

    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False

    def handle_data(self,data):
        if self.in_title:self.title+=data


def verify(path=None):
    results=[]
    for brand in load()['brands']:
        for url in [brand['website'],*[m['url'] for m in brand['models']]]:
            item=dict(brand=brand['name'],url=url,checked_at=stamp())
            try:
                with urlopen(Request(url,headers={'User-Agent':'QrongeMonitor/2'}),timeout=20) as response:
                    page=Page();page.feed(response.read(2_000_000).decode('utf-8',errors='replace'))
                    item.update(status='已读取，待人工核对页面是否为目标产品',page_title=page.title,official_linked_accounts=sorted(page.accounts))
            except (HTTPError,URLError,OSError):
                item['status']='不可用：官网请求未连通/被限制；未核验名称、拼写或账号'
            results.append(item)
    out=Path(path or ROOT/'data/official-verification.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    return out

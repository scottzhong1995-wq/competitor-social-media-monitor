import json,os,socket,subprocess,tempfile,time
from datetime import date,timedelta
from pathlib import Path
from urllib.request import urlopen,Request
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parent.parent;out=root/'docs/layout-audit';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 base=f'http://127.0.0.1:{port}'
 env={**os.environ,'MONITOR_DB':folder+'/audit.db','MONITOR_CONFIG':folder+'/settings.json'};env.pop('YOUTUBE_API_KEY',None)
 server=subprocess.Popen(['python3','-m','monitor','serve','--port',str(port)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(100):
   try:urlopen(base+'/health',timeout=1).close();break
   except OSError:time.sleep(.05)
  with urlopen(base+'/api/config') as r:token=json.load(r)['csrf']
  payload=(root/'examples/demo-output/demo-videos.json').read_bytes()
  urlopen(Request(base+'/api/import',data=payload,headers={'X-Monitor-Token':token},method='POST')).close()
  with urlopen(base+'/api/report') as r:week=json.load(r)['week']
  csv='series_id,query,week,value,source,geo,search_type\n'
  for i in range(12):
   # One missing week tests that the chart leaves a gap rather than inventing zero.
   if i==4:continue
   csv+=f'DEMO-layout,Yozma,{date.fromisoformat(week)-timedelta(weeks=11-i)},{20+i*3},https://example.invalid/demo-trends,US,web\n'
  urlopen(Request(base+'/api/trends',data=csv.encode(),headers={'X-Monitor-Token':token},method='POST')).close()
  results=[]
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
   page=browser.new_page()
   for width,height in [(1366,768),(390,844)]:
    page.set_viewport_size({'width':width,'height':height});page.goto(base);expect(page.locator('#count-videos')).to_have_text('1')
    for tab in ['overview','videos','viral-tab','trends','creators','sources']:
     page.click('[data-tab='+tab+']')
     value=page.locator('#'+tab).evaluate('''node=>({height:Math.round(node.getBoundingClientRect().height),top:Math.round(node.getBoundingClientRect().top),bodyOverflow:document.documentElement.scrollWidth>innerWidth,tables:[...node.querySelectorAll('table')].map(t=>({width:Math.round(t.getBoundingClientRect().width),container:Math.round(t.parentElement.getBoundingClientRect().width),rowHeight:t.rows[1]?Math.round(t.rows[1].getBoundingClientRect().height):0,smallFont:t.querySelector('small')?getComputedStyle(t.querySelector('small')).fontSize:null})),insightHeight:Math.round([...node.querySelectorAll('[data-insight]')].reduce((s,x)=>s+x.getBoundingClientRect().height,0))})''')
     assert not value['bodyOverflow'],(width,tab,value)
     if tab=='videos':
      assert all(float(t['smallFont'].removesuffix('px'))>=12 for t in value['tables'] if t['smallFont'])
      page.locator('[data-detail="yt:demoNEW0001"]').click()
      expect(page.locator('#video-detail-dialog')).to_be_visible()
      expect(page.locator('#video-detail-content')).to_contain_text('首次发现')
      expect(page.locator('#video-detail-content')).to_contain_text('7天表现')
      expect(page.locator('#video-detail-content')).to_contain_text('证据来源')
      page.click('#close-detail')
     if tab=='trends':
      expect(page.locator('.trend-chart')).to_have_count(1)
      expect(page.locator('.week-bar')).to_have_count(12)
      expect(page.locator('.missing-point')).to_have_count(1)
      expect(page.locator('#trend-charts')).to_contain_text('Yozma')
      page.screenshot(path=str(out/f'after-{width}-trends.png'),full_page=True)
     if width==390:
      assert not page.locator('#global-filter').evaluate('n=>n.open')
     results.append({'viewport':f'{width}x{height}','tab':tab,**value})
     if (width==1366 and tab in ['overview','videos']) or (width==390 and tab=='overview'):
      page.locator('.notice').evaluate("n=>n.textContent='DEMO · 隔离合成数据，仅用于排版检查'")
      page.screenshot(path=str(out/f'after-{width}-{tab}.png'),full_page=True)
   # Desktop recovery, filter reset, date normalization and analysis expansion.
   page.set_viewport_size({'width':1366,'height':768});page.click('[data-tab=videos]')
   page.select_option('#brand','Tuttio');expect(page.locator('main')).to_have_attribute('aria-busy','false')
   page.click('#reset-filters');expect(page.locator('#brand')).to_have_value('')
   expect(page.locator('main')).to_have_attribute('aria-busy','false')
   page.fill('#week','2026-10-21');page.locator('#week').dispatch_event('change')
   expect(page.locator('#week')).to_have_value('2026-10-19')
   expect(page.locator('main')).to_have_attribute('aria-busy','false')
   assert page.locator('[aria-current=page]').count()==1
   page.locator('#videos .analysis-details > summary').first.click()
   expect(page.locator('#videos .analysis-details').first).to_have_attribute('open','')
   page.route('**/api/report?*',lambda route:route.abort())
   page.click('#refresh');expect(page.locator('#toast')).to_contain_text('更新未完成')
   expect(page.locator('#export')).to_have_attribute('aria-disabled','true')
   page.unroute('**/api/report?*');page.click('#refresh')
   expect(page.locator('#export')).to_have_attribute('aria-disabled','false')
   browser.close()
  (out/'after.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  print(json.dumps(results,ensure_ascii=False,indent=2))
 finally:server.terminate();server.wait()

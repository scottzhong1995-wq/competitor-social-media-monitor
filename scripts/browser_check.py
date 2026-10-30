"""Optional browser smoke test: needs Playwright + Chromium, no real credentials."""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parent.parent

def main():
 with tempfile.TemporaryDirectory() as folder:
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  env={**os.environ,'MONITOR_DB':folder+'/demo.db','MONITOR_CONFIG':folder+'/settings.json'}
  env.pop('YOUTUBE_API_KEY',None)
  server=subprocess.Popen([sys.executable,'-m','monitor','serve','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for _ in range(100):
    try:urlopen(f'http://127.0.0.1:{port}/health',timeout=1).close();break
    except OSError:time.sleep(.05)
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1500,'height':1050});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{port}');expect(page.locator('#count-videos')).to_have_text('0')
    page.click('[data-tab=sources]');page.set_input_files('#import-videos',str(ROOT/'examples/demo-output/demo-videos.json'))
    expect(page.locator('#toast')).to_contain_text('已导入')
    page.click('[data-tab=overview]');expect(page.locator('#count-videos')).to_have_text('1')
    expect(page.locator('[data-insight=overview]')).to_contain_text('本周动态分析与总结')
    expect(page.locator('[data-insight=effects]')).to_contain_text('单条最高播放')
    page.locator('.notice').evaluate("el => el.textContent='DEMO · 此截图使用隔离的合成示例，不代表真实竞品合作或播放表现。'")
    page.screenshot(path=str(ROOT/'docs/dashboard-v2.png'),full_page=True)
    page.click('[data-tab=viral-tab]');expect(page.locator('.viral-card')).to_have_count(2)
    expect(page.locator('#viral')).to_contain_text('相对爆款候选')
    expect(page.locator('#viral')).to_contain_text('未取得对应材料')
    page.screenshot(path=str(ROOT/'docs/viral-analysis-v2.png'),full_page=True)
    page.click('[data-tab=videos]');page.locator('[data-review="yt:demoNEW0001"]').click()
    page.select_option('[name=cooperation]','普通提及');page.get_by_role('button',name='保存审核').click()
    expect(page.locator('#toast')).to_contain_text('审核已保存')
    for tab in ['videos','viral-tab','trends','creators','sources']:
     page.click('[data-tab='+tab+']')
     key='viral' if tab=='viral-tab' else tab
     expect(page.locator('[data-insight='+key+']')).to_be_visible()
    page.click('[data-tab=creators]');page.click('#add-account')
    page.fill('#json-editor',json.dumps({'platform':'TikTok','account_id':'DEMO-manual','creator':'DEMO新账号','notes':'公开观察','followed':True}))
    page.click('#json-save');expect(page.locator('#creator-table')).to_contain_text('DEMO新账号')
    page.select_option('#brand','Tuttio');page.select_option('#scope','suspected');page.check('#include-other')
    expect(page.locator('#count-videos')).to_have_text('1')
    with page.expect_download() as d:page.click('#export')
    assert d.value.suggested_filename.endswith('.xlsx')
    with page.expect_download() as d:page.click('#weekly')
    assert d.value.suggested_filename.endswith('.md')
    page.click('[data-tab=sources]');page.locator('.config-details > summary').click();settings=json.loads(page.locator('#config-editor').input_value());settings['baseline']['multiple']=4
    page.fill('#config-editor',json.dumps(settings));page.click('#save-config');expect(page.locator('#toast')).to_contain_text('配置已保存')
    page.set_viewport_size({'width':390,'height':844});page.click('[data-tab=overview]')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors,errors
    browser.close();print('Browser PASS: six tabs, import, audit, account creation, shared filters, XLSX/Markdown downloads, config persistence, mobile layout; module summaries + detailed viral evidence, no JS errors.')
  finally:server.terminate();server.wait(timeout=5)

if __name__=='__main__':main()

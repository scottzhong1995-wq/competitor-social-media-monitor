'use strict';
const $ = s => document.querySelector(s);
let data, csrf;
const fmt = v => v === null || v === undefined ? '—' : new Intl.NumberFormat('zh-CN').format(v);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {long:'长视频',short:'短视频',unknown:'格式待核实'};
const empty = (title, text='请先导入有来源的数据，或配置 YouTube 免费 API 后执行采集。') => `<div class="empty"><b>${esc(title)}</b>${esc(text)}</div>`;
const link = (url, text) => /^https:\/\//i.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : esc(text);
function table(headers, rows) { return `<table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`; }
function toast(text, error=false) { $('#toast').textContent=text; $('#toast').className=error?'error':''; $('#toast').hidden=false; setTimeout(()=>{$('#toast').hidden=true;},8000); }
async function request(path, options) { const r=await fetch(path,options);const body=await r.json();if(!r.ok)throw Error(body.error||'请求失败');return body; }
async function post(path, body) { return request(path,{method:'POST',headers:{'X-Monitor-Token':csrf,'Content-Type':'application/json'},body:typeof body==='string'?body:JSON.stringify(body)}); }
function titleCell(v) { return `${link(v.url,v.title)}<small>${esc(v.platform)} · ${esc(v.creator)} · ${esc(v.models.join(' / ')||'车型待识别')}</small>`; }
function renderVideos() {
  const q=$('#search').value.toLowerCase();
  const rows=data.videos.filter(v=>(!$('#new-only').checked||v.new_in_week)&&(!$('#platform').value||v.platform===$('#platform').value)&&(!$('#brand').value||v.brands.includes($('#brand').value))&&(!$('#status').value||v.cooperation===$('#status').value)&&JSON.stringify([v.title,v.creator,v.models]).toLowerCase().includes(q));
  $('#video-table').innerHTML=rows.length?table(['视频 / 车型','合作状态 / 市场','格式 / 内容','播放 / 快照','观测区间增量','操作'],rows.map(v=>[
    titleCell(v),`<span class="tag ${v.cooperation==='线索待核实'?'warn':''}">${esc(v.cooperation)}</span><small>${esc(v.market)} / ${esc(v.language)}</small>`,
    `${esc(labels[v.format])}<small>${esc(v.direction.join(' / '))}</small>`,`${fmt(v.views)}<small>${esc(v.observed_at||'尚无快照')}</small>`,
    `${fmt(v.observed_growth)}${v.metric_correction?'（指标回调）':''}<small>${esc(v.growth_from||'无基线')}<br>${esc(v.growth_to||'')}</small>`,
    `<button data-review="${esc(v.id)}">审核</button>`])):empty('本筛选下没有已收录视频');
  document.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>openReview(b.dataset.review));
}
function openReview(id) {
  const v=data.videos.find(v=>v.id===id), form=$('#review-form');
  $('#review-title').textContent=v.title;
  ['id','cooperation','evidence','format','market','language','review_note'].forEach(k=>{const input=form.elements.namedItem(k);input.value=v[k]||'';if(input.tagName==='SELECT'&&!input.value)input.value='unknown';});
  $('#review-dialog').showModal();
}
function render() {
  const s=data.summary;$('#period').textContent=`${data.week} — ${data.end} · 洛杉矶时间 · ${data.complete?'已结束统计周':'进行中，数据不完整'}`;
  $('#week').value=data.week;$('#export').href='/api/export?week='+data.week;
  $('#count-videos').textContent=fmt(s.confirmed_videos);$('#count-creators').textContent=fmt(s.confirmed_creators);$('#count-views').textContent=fmt(s.known_views);$('#count-pending').textContent=fmt(s.pending);
  $('#views-coverage').textContent=`播放数据覆盖 ${s.measured_videos}/${s.confirmed_videos} 条 · 非去重触达`;
  const confirmed=data.videos.filter(v=>v.new_in_week&&v.target_market&&v.cooperation==='明确合作');
  $('#brands').innerHTML=['Yozma','Tuttio'].map(brand=>{const rows=confirmed.filter(v=>v.brands.includes(brand));return `<div class="brand-row"><div><strong>${brand}</strong><small>${esc([...new Set(rows.flatMap(v=>v.models))].join(' / ')||'本周暂无已确认车型')}</small></div><div class="brand-value">${rows.length}<small>合作视频</small></div></div>`;}).join('');
  const directions={},words={};confirmed.forEach(v=>{v.direction.forEach(d=>directions[d]=(directions[d]||0)+1);v.keywords.forEach(w=>words[w]=(words[w]||0)+1);});
  $('#directions').innerHTML=Object.entries(directions).map(([k,v])=>`<div class="direction-row"><span>${esc(k)}</span><b>${v}</b></div>`).join('')||empty('尚无可分析的确认合作','导入视频后审核合作、市场与语言，即可汇总。');
  $('#keywords').innerHTML=Object.entries(words).sort((a,b)=>b[1]-a[1]).slice(0,15).map(([k,v])=>`<span class="tag">${esc(k)} · ${v}</span>`).join('');
  const viral=data.videos.filter(v=>v.new_in_week&&v.viral_candidate&&v.cooperation!=='排除').sort((a,b)=>b.views-a.views);
  $('#viral').innerHTML=viral.length?table(['视频','合作状态 / 市场','累计播放','候选依据'],viral.map(v=>[titleCell(v),`${esc(v.cooperation)}<small>${esc(v.market)} / ${esc(v.language)}</small>`,fmt(v.views),esc(v.viral_reason)])):empty('尚无达到阈值的已收录视频','覆盖不足时无法判断竞品是否存在爆款。');
  $('#breakdown').innerHTML=data.breakdown.length?table(['平台','格式','合作视频','已知累计播放','指标覆盖'],data.breakdown.map(r=>[esc(r.platform),esc(labels[r.format]),fmt(r.videos),fmt(r.views),`${r.measured}/${r.videos}`])):empty('尚无已确认的美国英语合作');
  $('#creator-table').innerHTML=data.creators.length?table(['红人账号','粉丝 / 快照','红人类型','公开联系方式','收录 / 确认'],data.creators.map(c=>[`${link(c.creator_url,c.creator)}<small>${esc(c.platform)}</small>`,`${fmt(c.followers)}<small>${esc(c.observed_at||'')}</small>`,esc(c.creator_type||'待分类'),`${esc(c.contact||'未收录')}<small>${link(c.contact_source,c.contact_source?'查看公开来源':'')}</small>`,`${c.videos} / ${c.confirmed}`])):empty('红人名单尚未建立');
  $('#trend-table').innerHTML=data.trends.length?table(['搜索词','系列','周起始','热度0–100','环比','来源'],data.trends.map(t=>[esc(t.query),esc(t.series_id),esc(t.week),`${fmt(t.value)}<div class="trend-bar" data-value="${t.value}"></div>`,t.change_percent===null?'—':`${t.change_percent}%`,link(t.source,t.source)])):empty('尚未导入搜索趋势','可从 Google Trends 下载美国品牌词与车型词的周度热度，并整理为模板 CSV。');
  document.querySelectorAll('.trend-bar').forEach(b=>{b.style.width=`${Number(b.dataset.value)}%`;});
  $('#coverage').innerHTML=Object.entries(data.coverage).filter(([k])=>k!=='video_records').map(([k,v])=>`<div class="coverage-row"><strong>${esc(k)}</strong><span>${esc(v)}</span></div>`).join('');
  $('#runs').innerHTML=data.runs.length?table(['时间','状态','结果'],data.runs.map(r=>[esc(r.started_at),esc(r.status),esc(r.detail)])):empty('尚无自动采集运行记录','常驻调度尚未启动；看板不会自行触发付费数据采集。');
  renderVideos();
}
async function load() {try{data=await request('/api/report'+($('#week').value?'?week='+$('#week').value:''));render();}catch(e){toast(e.message,true);}}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>{document.querySelectorAll('.nav,.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.tab).classList.add('active');$('#page-title').textContent=b.textContent.replace(/^\d+\s*/, '');});
$('#refresh').onclick=load;['search','platform','brand','status','new-only'].forEach(id=>$('#'+id).addEventListener('input',()=>data&&renderVideos()));
$('#cancel-review').onclick=()=>$('#review-dialog').close();
$('#review-form').onsubmit=async e=>{e.preventDefault();try{await post('/api/review',Object.fromEntries(new FormData(e.target)));$('#review-dialog').close();toast('审核已保存');await load();}catch(error){toast(error.message,true);}};
for(const [id,path] of [['import-videos','/api/import'],['import-trends','/api/trends']])$('#'+id).onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>5000000)throw Error('文件不能超过5MB');const r=await post(path,await file.text());toast(`已导入 ${r.imported} 条记录`);await load();}catch(error){toast(error.message,true);}finally{e.target.value='';}};
(async()=>{try{const c=await request('/api/config');csrf=c.csrf;$('#watchlist').innerHTML=c.config.brands.map(b=>`<div class="watch"><strong>${link(b.website,b.name)}</strong>${b.models.map(m=>link(m.url,m.name)).join(' / ')}</div>`).join('');await load();}catch(e){toast(e.message,true);}})();

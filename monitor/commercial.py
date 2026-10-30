"""Commercial-association evidence, in the user's discount/affiliate priority."""
import re
from urllib.parse import parse_qs, unquote, urlparse
from .settings import load


def signals(text):
    results=[];seen=set()
    def add(kind,value,context):
        key=(kind,value.casefold())
        if key not in seen:
            results.append(dict(kind=kind,value=value,context=context.strip()));seen.add(key)
    for match in re.finditer(r'(?:\b(?:discount|coupon|promo)\s+code\s*(?:[:=\-]|is\b)?\s*["\']?|\buse\s+(?:my\s+|our\s+|the\s+)?code\s*[:=\-]?\s*["\']?)([a-z0-9][a-z0-9_-]{2,24})\b',text,re.I):
        prefix=text[max(0,match.start()-25):match.start()]
        if re.search(r'(?:\bno|\bwithout|\bnot using|\bdon.t use|\bdo not use)\s+(?:(?:any|a|my)\s+)?$',prefix,re.I):continue
        code=match[1]
        if code.lower() in {'available','below','here','none','not','needed','required','description','link','code','for','and','the'}:continue
        add('折扣码',code,text[max(0,match.start()-30):match.end()+60])
    domains={urlparse(b.get('website','')).hostname for b in load()['brands']}
    for match in re.finditer(r'https?://[^\s<>"\']+',text,re.I):
        url=match[0].rstrip('.,;!)]}')
        try:p=urlparse(url);params={k.lower():v for k,v in parse_qs(p.query).items()}
        except ValueError:continue
        host=(p.hostname or '').removeprefix('www.')
        brand_link=any(d and (host==d.removeprefix('www.') or host.endswith('.'+d.removeprefix('www.'))) for d in domains)
        path=re.search(r'/discount/([^/?#]+)',p.path,re.I)
        if brand_link and path:add('折扣码',unquote(path[1]),url)
        if brand_link and params.get('discount'):add('折扣码',params['discount'][0],url)
        strong={'aff','aff_id','affid','affiliate','affiliate_id','referral','sca_ref'}
        ref={'ref','ref_id','referrer'}
        context=text[max(0,match.start()-50):match.end()+20]
        affiliate=any(params.get(k) for k in strong) or (brand_link and any(params.get(k) for k in ref)) or ('affiliate' in context.lower() and bool(params))
        if (host=='amazon.com' or host.endswith('.amazon.com')) and params.get('tag'):affiliate=True
        if affiliate:add('联盟链接',url,context)
    return sorted(results,key=lambda r:0 if r['kind']=='折扣码' else 1)


def exclusion(views, minimum):
    if views is None:return '播放量未知，待补数据'
    if views<minimum:return f'播放量低于 {minimum:,}，不纳入统计'
    return ''

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import ROOT, CONFIG, connect, import_trends, import_videos, report, review
from .export import workbook, markdown
from .settings import load as settings, save as save_settings
from .profiles import upsert_account


def serve(host='127.0.0.1', port=8000):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type='application/json; charset=utf-8', headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                return self.reply(403, {'error': '仅允许本机访问'})
            parsed = urlparse(self.path)
            if parsed.path in ('/', '/app.js', '/style.css'):
                filename = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[parsed.path]
                kind = {'index.html':'text/html; charset=utf-8', 'app.js':'text/javascript; charset=utf-8', 'style.css':'text/css; charset=utf-8'}[filename]
                return self.reply(200, (ROOT/'monitor/static'/filename).read_bytes(), kind)
            if parsed.path == '/api/config':
                return self.reply(200, dict(config=settings(), csrf=token))
            if parsed.path == '/health':
                with connect() as db:
                    db.execute('SELECT 1').fetchone()
                return self.reply(200, {'status': 'ok'})
            if parsed.path not in ('/api/report', '/api/export', '/api/weekly'):
                return self.reply(404, {'error': '不存在'})
            try:
                with connect() as db:
                    args={k:v[0] for k,v in parse_qs(parsed.query).items()}
                    data = report(db, args.pop('week',None), **args)
                if parsed.path == '/api/weekly':
                    return self.reply(200, markdown(data), 'text/markdown; charset=utf-8', {'Content-Disposition':f'attachment; filename=weekly-{data["week"]}.md'})
                if parsed.path == '/api/export':
                    return self.reply(200, workbook(data), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                      {'Content-Disposition': f'attachment; filename="weekly-{data["week"]}.xlsx"'})
                self.reply(200, data)
            except ValueError as e:
                self.reply(400, {'error': str(e)})

        def do_POST(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                return self.reply(403, {'error': '仅允许本机访问'})
            if not secrets.compare_digest(self.headers.get('X-Monitor-Token', ''), token):
                return self.reply(403, {'error': '请从本地看板提交操作'})
            if self.path not in ('/api/import', '/api/trends', '/api/review','/api/config','/api/account','/api/related'):
                return self.reply(404, {'error': '不存在'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 5_000_000:
                    raise ValueError('文件需为 1 字节至 5MB')
                body = self.rfile.read(size).decode('utf-8-sig')
                with connect() as db:
                    if self.path == '/api/import':
                        result = {'imported': import_videos(db, json.loads(body))}
                    elif self.path == '/api/trends':
                        result = {'imported': import_trends(db, body)}
                    elif self.path == '/api/config':
                        result={'config':save_settings(json.loads(body))}
                    elif self.path == '/api/account':
                        with db:
                            result=upsert_account(db,json.loads(body))
                    elif self.path == '/api/related':
                        items=json.loads(body)
                        with db:
                            for r in items:
                                if r['kind'] not in {'top','rising'} or not r.get('source'):
                                    raise ValueError('相关查询需 kind=top/rising 和来源')
                                from .core import stamp
                                db.execute('INSERT INTO related_queries VALUES (?,?,?,?,?,?,?)',(r['series_id'],r['query'],r['kind'],r['term'],str(r.get('value','')),r['source'],stamp()))
                        result={'imported':len(items)}
                    else:
                        review(db, json.loads(body))
                        result = {'reviewed': True}
                self.reply(200, result)
            except (ValueError, KeyError, TypeError, UnicodeError) as e:
                self.reply(400, {'error': str(e)})

    # Local-only service. Put authenticated HTTPS in front before remote deployment.
    print(f'本地看板已启动，监听 {host}:{port}（尚未部署为公网服务）', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()

"""Local dashboard for reconciled TalentPulse analytics. Run: python dashboard/server.py."""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analytics.warehouse_analytics import collect,save
from warehouse.reload_validation import preflight
from warehouse.snowflake_loader import create_connection
from rag.analytics_assistant import GeminiAssistant,ask

REPORT=ROOT/'analytics/output/warehouse_analytics.json'
INPUT=ROOT/'ingestion/output/transformed_jobs.csv'
LOCK=threading.Lock()
STATE={'running':False,'error':None}
ASSISTANT_LOCK=threading.Lock()
ASSISTANT=None


def load_report():
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    _,manifest=preflight(INPUT)
    if report.get('input_sha256')!=manifest['output_sha256']:
        raise ValueError('Report belongs to a different snapshot. Refresh analytics first.')
    validation=report.get('validation',{})
    if not validation.get('exact_snapshot_reconciliation') or not validation.get('sql_aggregate_reconciliation'):
        raise ValueError('Report has not passed reconciliation.')
    return report


def refresh():
    try:
        conn=create_connection()
        try: report=collect(conn,INPUT)
        finally: conn.close()
        save(report,REPORT.parent)
    except Exception:
        # Provider/connector exceptions may contain connection details; never return them to browsers.
        STATE['error']='Refresh failed. The previous report is retained. Check Snowflake access and run analytics/analyze_jobs.py for diagnostics.'
    finally:
        STATE['running']=False
        LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def trusted(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

    def send(self,code,data,kind='application/json; charset=utf-8'):
        body=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,dict) else data
        self.send_response(code)
        if urlsplit(self.path).path=='/api/download' and code==200:
            self.send_header('Content-Disposition','attachment; filename="talentpulse-validated-analytics.json"')
        for k,v in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"}.items():
            self.send_header(k,v)
        self.end_headers();self.wfile.write(body)

    def do_GET(self):
        if not self.trusted(): return self.send(403,{'error':'Local access only'})
        route=urlsplit(self.path).path
        if route=='/api/status':return self.send(200,dict(STATE))
        if route in {'/api/report','/api/download'}:
            try: report=load_report()
            except (OSError,ValueError,KeyError):return self.send(409,{'error':'No current validated report is available. Refresh analytics to create one.'})
            return self.send(200,report)
        assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if route not in assets:return self.send(404,{'error':'Not found'})
        name,kind=assets[route];return self.send(200,(Path(__file__).parent/name).read_bytes(),kind)

    def do_POST(self):
        global ASSISTANT
        expected={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        if not self.trusted() or self.headers.get('Origin') not in expected:
            return self.send(403,{'error':'Same-origin request required'})
        if self.path=='/api/ask':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError()
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict) or set(body)!={'question'}:raise ValueError()
                question=body['question']
                if not isinstance(question,str) or not 1<=len(question.strip())<=1000:raise ValueError()
            except (ValueError,UnicodeError):return self.send(400,{'error':'Send one question of 1–1000 characters as JSON.'})
            try:report=load_report()
            except (ValueError,OSError,KeyError):return self.send(409,{'error':'Refresh the validated analytics before asking questions.'})
            if not ASSISTANT_LOCK.acquire(blocking=False):return self.send(429,{'error':'Another question is being answered. Please try again shortly.'})
            try:
                if ASSISTANT is None:ASSISTANT=GeminiAssistant()
                result=ask(question,report,ASSISTANT)
            except Exception:
                return self.send(503,{'error':'The assistant could not produce a validated answer. Try a simpler question or check Gemini configuration/quota. No unverified answer was substituted.'})
            finally:ASSISTANT_LOCK.release()
            return self.send(200,result)
        if self.path!='/api/refresh':return self.send(404,{'error':'Not found'})
        if not LOCK.acquire(blocking=False):return self.send(409,{'error':'A refresh is already running'})
        STATE.update(running=True,error=None)
        threading.Thread(target=refresh,daemon=True).start()
        return self.send(202,dict(STATE))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    print(f'TalentPulse dashboard: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

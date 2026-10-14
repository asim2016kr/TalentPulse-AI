"""No-email HTTP verification against a running production build."""
import json
import re
import requests
from bs4 import BeautifulSoup
from .db import ROOT

def verify(base='http://127.0.0.1:3000'):
    checks=[]
    nonces=[]
    for path in ['/login','/login','/jobs','/signup','/missing-phase6-page']:
        response=requests.get(base+path,timeout=30)
        assert response.status_code==(404 if 'missing-' in path else 200)
        policy=response.headers['Content-Security-Policy']
        nonce=re.search(r"'nonce-([^']+)'",policy).group(1)
        nonces.append(nonce)
        assert 'unsafe-eval' not in policy
        assert "script-src-attr 'none'" in policy
        scripts=BeautifulSoup(response.text,'html.parser').find_all('script')
        assert scripts and all(s.get('nonce')==nonce for s in scripts)
        assert 'no-store' in response.headers['Cache-Control']
        checks.append(path+' nonce matches all rendered scripts')
    assert len(nonces)==len(set(nonces));checks.append('unique per-request nonces')
    for path,status in [('/api/health','ok'),('/api/v1/health','ready')]:
        r=requests.get(base+path,timeout=30);assert r.status_code==200
        data=r.json();assert data.get('status',data.get('data',{}).get('status'))==status
        checks.append(path+' available')
    result={'passed':True,'checks':checks,'emails_sent':0}
    (ROOT/'product/output/security_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'http_checks':len(checks),'emails_sent':0}))

if __name__=='__main__':verify()

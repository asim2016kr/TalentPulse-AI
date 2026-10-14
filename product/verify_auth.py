"""Public auth boundary checks only: never sends signup or recovery emails."""
import json
from uuid import uuid4
import requests
from .db import ROOT


def verify(base='http://127.0.0.1:3000'):
    checks=[]
    def req(method,path,expected,**kwargs):
        response=requests.request(method,base+path,timeout=30,allow_redirects=False,**kwargs)
        assert response.status_code==expected,(path,response.status_code)
        checks.append({'path':path,'status':response.status_code})
        return response
    for path in ['/api/v1/auth/me','/api/v1/me/saved-jobs','/api/v1/me/applications']:
        req('GET',path,401)
    job=requests.get(base+'/api/v1/jobs',timeout=30).json()['data'][0]['id']
    req('PUT','/api/v1/me/saved-jobs/'+job,401,json={},headers={'Origin':base})
    req('PUT','/api/v1/me/saved-jobs/'+job,403,json={},headers={'Origin':'https://evil.example'})
    # Forged session presence must not silently become an anonymous apply request.
    cookie='sb-ufetbdkqvvagojogpdfd-auth-token=forged'
    req('GET','/api/v1/auth/me',401,headers={'Cookie':cookie})
    req('POST','/api/v1/jobs/'+job+'/apply-click',401,json={'request_id':str(uuid4())},headers={'Origin':base,'Cookie':cookie})
    req('POST','/api/v1/auth/login',401,json={'email':'qa-'+uuid4().hex+'@test.invalid','password':'invalid-test-password'},headers={'Origin':base})
    # Validation rejects this before contacting the email provider.
    req('POST','/api/v1/auth/signup',422,json={'email':'invalid','password':'short'},headers={'Origin':base})
    req('POST','/api/v1/auth/reset-password',401,json={'password':'test-passphrase-not-used'},headers={'Origin':base})
    response=req('GET','/auth/callback?next=https://evil.example',303)
    assert response.headers['Location'].startswith(base+'/login')
    for path in ['/login','/signup','/forgot-password','/reset-password']:
        response=req('GET',path,200)
        assert response.headers.get('X-Frame-Options')=='DENY'
        assert 'no-store' in response.headers.get('Cache-Control','')
    result={'passed':True,'http_checks':len(checks),'checked':checks,'emails_sent':0}
    (ROOT/'product/output/auth_http_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checked'}))


if __name__=='__main__':verify()

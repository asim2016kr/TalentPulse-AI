"""Verify the guest external-apply contract through the running local application."""
import json
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit
import requests
from .db import ROOT, connect


def verify(base='http://127.0.0.1:3000'):
    checks = []
    with connect() as conn:
        before = conn.execute('SELECT (SELECT count(*) FROM app.application_clicks), (SELECT count(*) FROM app.applications)').fetchone()
        hidden = conn.execute('SELECT id FROM app.jobs WHERE is_development LIMIT 1').fetchone()
    jobs = requests.get(base+'/api/v1/jobs', timeout=25).json()['data']
    assert jobs, 'A currently eligible job is required for the live apply check'
    job = jobs[0]
    path = base+'/api/v1/jobs/'+job['id']+'/apply-click'

    def post(expected, body=None, headers=None, url=path):
        response = requests.post(url, json=body if body is not None else {'request_id':str(uuid4())},
                                 headers=headers if headers is not None else {'Origin':base}, timeout=25)
        assert response.status_code == expected, (expected, response.status_code)
        assert 'no-store' in response.headers.get('Cache-Control', '')
        payload = response.json()
        if expected != 200:
            assert 'data' not in payload and 'redirect_url' not in response.text
        checks.append({'status':response.status_code})
        return payload

    request_id = str(uuid4())
    first = post(200, {'request_id':request_id})['data']
    source = urlsplit(job['source']['url'])
    normalized = urlunsplit((source.scheme, source.netloc.lower(), source.path, source.query, source.fragment))
    assert first == {'redirect_url':normalized, 'destination_kind':'source_listing',
                     'tracked':False, 'application_status':None}
    assert post(200, {'request_id':request_id})['data'] == first
    post(403, headers={'Origin':'https://untrusted.example'})
    post(403, headers={})
    post(401, headers={'Origin':base, 'Authorization':'Bearer invalid'})
    post(400, {'request_id':request_id, 'redirect_url':'https://untrusted.example'})
    post(400, {'request_id':'invalid'})
    post(404, url=base+'/api/v1/jobs/'+str(uuid4())+'/apply-click')
    if hidden:
        post(404, url=base+'/api/v1/jobs/'+str(hidden[0])+'/apply-click')
    response = requests.get(path, timeout=25)
    assert response.status_code == 405
    checks.append({'status':405})
    with connect() as conn:
        after = conn.execute('SELECT (SELECT count(*) FROM app.application_clicks), (SELECT count(*) FROM app.applications)').fetchone()
    assert before == after, 'Guest requests must not create personal records'
    result = {'passed':True, 'http_checks':len(checks), 'guest_writes':0, 'checked':checks}
    output = ROOT/'product/output/apply_validation.json'
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checked'}))


if __name__ == '__main__':
    verify()

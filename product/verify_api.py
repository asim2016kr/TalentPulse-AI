"""Read-only checks from actual HTTP API through PostgreSQL and back."""
import argparse
import json
from collections import Counter
from pathlib import Path
import requests
from .db import ROOT,connect


def verify(base):
    tests=[]
    def get(path,params=None,expected=200):
        response=requests.get(base+path,params=params,timeout=25)
        assert response.status_code==expected,(path,response.status_code)
        assert 'no-store' in response.headers.get('Cache-Control','')
        tests.append({'path':path,'status':response.status_code})
        return response.json()
    get('/api/v1/health')
    full=get('/api/v1/jobs',{'page_size':50})
    jobs=full['data']; total=full['pagination']['total']
    assert len(jobs)==total  # MVP test snapshot fits on one page.
    with connect() as connection:
        expected=connection.execute("""SELECT count(*) FROM app.jobs WHERE status='active' AND NOT is_development
            AND fresh_until>now() AND (expires_at IS NULL OR expires_at>now())""").fetchone()[0]
        hidden=connection.execute('SELECT id FROM app.jobs WHERE is_development LIMIT 1').fetchone()
    assert total==expected
    assert len({j['id'] for j in jobs})==len(jobs)
    assert all(j['status']=='active' and not j['is_development'] for j in jobs)
    roles=Counter(j['role'] for j in jobs)
    for role,count in roles.items():
        data=get('/api/v1/jobs',{'role':role,'page_size':50})
        assert len(data['data'])==count and data['pagination']['total']==count
        assert all(j['role']==role for j in data['data'])
    filters=get('/api/v1/jobs/filters')['data']
    assert set(filters['roles'])==set(roles)
    pages=[]
    for number in range(1,full['pagination']['total']//7+2):
        pages.extend(get('/api/v1/jobs',{'page':number,'page_size':7})['data'])
    assert [j['id'] for j in pages]==[j['id'] for j in jobs]
    if jobs:
        job=jobs[0]
        detail=get('/api/v1/jobs/'+job['id'])['data']
        assert detail['can_apply'] and detail['description_text'].strip()
        assert detail['application_url_kind']=='source_listing'
        assert not set(detail)&{'classification','reviewer','source_job_id','application_url'}
        company=get('/api/v1/jobs',{'company_id':job['company']['id'],'page_size':50})['data']
        assert all(j['company']['id']==job['company']['id'] for j in company)
        search=get('/api/v1/jobs',{'q':job['title'],'sort':'relevance','page_size':50})
        assert job['id'] in {j['id'] for j in search['data']}
        get('/api/v1/jobs',{'q':"%' OR 1=1 --",'location':'%_'})
    if hidden:
        get('/api/v1/jobs/'+str(hidden[0]),expected=404)
    get('/api/v1/jobs/00000000-0000-0000-0000-000000000000',expected=404)
    for params in [{'page_size':51},{'page':0},{'preview':'true'},{'sort':'sql'},{'company_id':'bad'}]:
        get('/api/v1/jobs',params,400)
    get('/api/v1/jobs',{'role':'invalid role'},422)
    get('/api/v1/jobs/not-a-uuid',expected=400)
    return {'passed':True,'http_checks':len(tests),'public_jobs':total,'checked':tests}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:3000')
    parser.add_argument('--output',type=Path,default=ROOT/'product/output/api_validation.json')
    args=parser.parse_args()
    result=verify(args.base)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checked'},indent=2))


if __name__=='__main__':main()

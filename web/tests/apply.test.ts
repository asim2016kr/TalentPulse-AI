import test from 'node:test';
import assert from 'node:assert/strict';
import {applicationDestination, type ApplicationRecord} from '../lib/application-policy';
import {applicationOrigins, createApplyHandler, createApplyLimiter} from '../lib/apply-handler';

const id = '00000000-0000-0000-0000-000000000001';
const origin = 'http://localhost:3000';
const row: ApplicationRecord = {source:'remoteok', application_url:'https://remoteok.com/remote-jobs/software-engineer-123', application_url_kind:'source_listing', eligible:true};
function request(body: unknown = {request_id:id}, headers: Record<string,string> = {}) {
  return new Request(`${origin}/api/v1/jobs/${id}/apply-click`, {method:'POST', headers:{origin,'Content-Type':'application/json',...headers}, body:JSON.stringify(body)});
}
const origins = () => new Set([origin]);

test('only reviewed Remote OK HTTPS listing destinations are accepted', () => {
  assert.equal(applicationDestination(row), row.application_url);
  for (const url of ['http://remoteok.com/remote-jobs/x','https://remoteok.com.evil.test/remote-jobs/x',
    'https://evil.test/remote-jobs/x','https://remoteok.com@evil.test/remote-jobs/x','https://a:b@remoteok.com/remote-jobs/x',
    'https://127.0.0.1/remote-jobs/x','//remoteok.com/remote-jobs/x','javascript:alert(1)',
    'https://remoteok.com:444/remote-jobs/x','https://remoteok.com/remote-jobs/x?next=https://evil.test',
    'https://remoteok.com/remote-jobs/x#fragment','https://remoteok.com/remote-jobs/x%0a',
    'https://remoteok.com/remote-jobs/../../login','https://remoteok.com/remote-jobs/x\\y',' https://remoteok.com/remote-jobs/x']) {
    assert.equal(applicationDestination({...row,application_url:url}),null,url);
  }
  assert.equal(applicationDestination({...row,eligible:false}),null);
  assert.equal(applicationDestination({...row,source:'unreviewed'}),null);
  assert.equal(applicationDestination({...row,application_url_kind:'employer'}),null);
});

test('guest click resolves stored destination and never claims application submission', async () => {
  let calls = 0;
  const handler = createApplyHandler(async jobId => {assert.equal(jobId,id);calls++;return row;},()=>true,origins);
  for (let n=0;n<2;n++) {
    const response = await handler(request(),id);
    assert.equal(response.status,200);
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.deepEqual(await response.json(),{data:{redirect_url:row.application_url,destination_kind:'source_listing',tracked:false,application_status:null}});
  }
  assert.equal(calls,2); // Eligibility is checked again even for a repeated guest request.
});

test('ineligible, missing, unsafe and database failure paths never return redirect URLs', async () => {
  for (const [record,status] of [[null,404],[{...row,eligible:false},410],[{...row,application_url:'https://evil.test'},410]] as const) {
    const response=await createApplyHandler(async()=>record,()=>true,origins)(request(),id);
    assert.equal(response.status,status);
    assert.ok(!(await response.text()).includes('redirect_url'));
  }
  const response=await createApplyHandler(async()=>{throw new Error('postgres://secret:password@host');},()=>true,origins)(request(),id);
  assert.equal(response.status,503);assert.ok(!(await response.text()).includes('password'));
});

test('cross-origin, tokens, malformed bodies and caller-controlled redirects fail before database', async () => {
  let calls=0;
  const handler=createApplyHandler(async()=>{calls++;return row;},()=>true,origins);
  const cases:[Request,number][]=[
    [request({}, {origin:'https://evil.test'}),403], [request({}, {origin:''}),403],
    [request({}, {'sec-fetch-site':'cross-site'}),403],
    [request({}, {authorization:'Bearer fake'}),401],
    [request({}, {cookie:'sb-project-auth-token.0=fake'}),401],
    [request({request_id:id,redirect_url:'https://evil.test'}),400],
    [request({request_id:'bad'}),400], [request(null),400], [request([]),400],
    [request({request_id:'x'.repeat(1500)}),400],
    [request({}, {'Content-Type':'text/plain'}),415],
    [new Request(`${origin}/api/v1/jobs/${id}/apply-click`),405],
    [new Request(`${origin}/api/v1/jobs/${id}/apply-click?redirect_url=evil`,{method:'POST',headers:{origin}}),400],
  ];
  for(const [req,status] of cases) assert.equal((await handler(req,id)).status,status);
  assert.equal((await handler(request(),'invalid')).status,400);
  assert.equal(calls,0);
});

test('rate limiting blocks database work and recovers after the window', async () => {
  let now=0;const limiter=createApplyLimiter(2,1000,()=>now);
  const handler=createApplyHandler(async()=>row,limiter,origins);
  assert.equal((await handler(request(),id)).status,200);
  assert.equal((await handler(request(),id)).status,200);
  const blocked=await handler(request(),id);
  assert.equal(blocked.status,429);assert.equal(blocked.headers.get('retry-after'),'60');
  now=1000;assert.equal((await handler(request(),id)).status,200);
});

test('production accepts only configured origin; local aliases are development-only',()=>{
  assert.deepEqual([...applicationOrigins({APP_BASE_URL:'https://talent.example',APP_ENV:'production'})],['https://talent.example']);
  assert.equal(applicationOrigins({APP_BASE_URL:origin,APP_ENV:'development'}).has('http://127.0.0.1:3000'),true);
  assert.equal(applicationOrigins({}).size,0);
});

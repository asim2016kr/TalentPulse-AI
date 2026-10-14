import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSearch,queryPlan,developmentPreview,InputError} from '../lib/search';
import {failure} from '../lib/response';
test('defaults and strict query bounds',()=>{
  assert.equal(parseSearch(new URLSearchParams()).page_size,20);
  for(const query of ['page=0','page_size=51','page=999&page_size=50','q=x&q=y','preview=true','role=Doctor','sort=relevance','company_id=abc']) {
    assert.throws(()=>parseSearch(new URLSearchParams(query)),InputError);
  }
});
test('search inputs cannot become SQL syntax',()=>{
  const text="%' OR 1=1 --";
  const plan=queryPlan(parseSearch(new URLSearchParams({q:text,location:'%_'})));
  assert.ok(!plan.where.includes(text));
  assert.ok(plan.values.includes(text));
  assert.ok(plan.values.includes('%\\%\\_%'));
  assert.ok(plan.where.includes('fresh_until>now()'));
  assert.ok(plan.where.includes('NOT j.is_development'));
});
test('preview is server configuration and cannot run in production',()=>{
  assert.equal(developmentPreview({APP_ENV:'development',ALLOW_DEVELOPMENT_JOBS:'true',NODE_ENV:'development'}),true);
  assert.throws(()=>developmentPreview({APP_ENV:'development',ALLOW_DEVELOPMENT_JOBS:'true',NODE_ENV:'production'}));
  assert.throws(()=>developmentPreview({APP_ENV:'production',ALLOW_DEVELOPMENT_JOBS:'true'}));
});
test('role, source tag and company filters bind exact values',()=>{
  const plan=queryPlan(parseSearch(new URLSearchParams({role:'Data Engineer',source_tag:'python',company_id:'00000000-0000-0000-0000-000000000001'})));
  assert.deepEqual(plan.values,['Data Engineer','00000000-0000-0000-0000-000000000001','python']);
  assert.ok(plan.where.includes('unnest(j.source_tags)'));
});
test('unexpected errors cannot expose driver credentials',async()=>{
  const response=failure(new Error('postgresql://secret:password@host/db'));
  assert.equal(response.status,503);
  assert.ok(!(await response.text()).includes('password'));
});

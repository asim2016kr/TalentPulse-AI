import test from 'node:test';
import assert from 'node:assert/strict';
import {contentSecurityPolicy} from '../lib/security-policy';
import {failure} from '../lib/response';
import {AccountError} from '../lib/account-policy';

test('production CSP blocks arbitrary scripts, embedding and external form submissions',()=>{
  const policy=contentSecurityPolicy('YWJjZA==');
  const scripts=policy.split('; ').find(p=>p.startsWith('script-src '))!;
  assert.ok(scripts.includes("'nonce-YWJjZA=='"));
  assert.ok(scripts.includes("'strict-dynamic'"));
  assert.ok(!scripts.includes('unsafe-inline'));
  assert.ok(!policy.includes('unsafe-eval'));
  for(const rule of ["form-action 'self'","frame-ancestors 'none'","object-src 'none'","connect-src 'self'","script-src-attr 'none'"]) assert.ok(policy.includes(rule));
  assert.throws(()=>contentSecurityPolicy("';script-src *"));
});
test('development eval permission never leaks into production CSP',()=>{
  assert.ok(contentSecurityPolicy('YWJj',true).includes('unsafe-eval'));
  assert.ok(!contentSecurityPolicy('YWJj',false).includes('unsafe-eval'));
});
test('persistent account throttles include a conservative retry interval',async()=>{
  const response=failure(new AccountError(429,'RATE_LIMITED','Please wait.'));
  assert.equal(response.status,429);assert.equal(response.headers.get('retry-after'),'900');
  assert.ok((await response.json()).error.request_id);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {safeNext,authInput,AccountError,callbackOrigin} from '../lib/account-policy';
test('callbacks preserve the browser local origin and use configured HTTPS in production',()=>{
  assert.equal(callbackOrigin('127.0.0.1:3000',{APP_ENV:'development'}),'http://127.0.0.1:3000');
  assert.equal(callbackOrigin('localhost:3000',{APP_ENV:'development'}),'http://localhost:3000');
  assert.throws(()=>callbackOrigin('evil.test',{APP_ENV:'development'}),AccountError);
  assert.equal(callbackOrigin('untrusted-forwarded-host',{APP_ENV:'production',APP_BASE_URL:'https://talent.example'}),'https://talent.example');
  assert.throws(()=>callbackOrigin('localhost',{APP_ENV:'production',APP_BASE_URL:'http://localhost'}),AccountError);
});
import {accountBody} from '../lib/account-http';
test('post-login redirects stay on approved local screens',()=>{
  for(const value of ['https://evil.test','//evil.test','/\\evil.test','/dashboard?next=evil','/api/v1/auth/logout','/jobs/not-a-uuid','%2f%2fevil.test',null]) assert.equal(safeNext(value),'/dashboard');
  assert.equal(safeNext('/dashboard/saved'),'/dashboard/saved');
  assert.equal(safeNext('/jobs/00000000-0000-0000-0000-000000000001'),'/jobs/00000000-0000-0000-0000-000000000001');
});
test('authentication validation preserves passwords and bounds names and email',()=>{
  const input=authInput({email:' Test@Example.com ',password:'  secret passphrase  ',display_name:' Test '},'signup');
  assert.equal(input.password,'  secret passphrase  ');assert.equal(input.email,'test@example.com');assert.equal(input.displayName,'Test');
  for(const body of [{email:'bad',password:'longvalidpassword',display_name:'test'},{email:'a@b.com',password:'short',display_name:'test'},{email:'a@b.com',password:'x'.repeat(129),display_name:'test'},{email:'a@b.com',password:'longvalidpassword',display_name:''}]) assert.throws(()=>authInput(body,'signup'),AccountError);
});
test('account actions require trusted origins and bounded JSON objects',async()=>{
  process.env.APP_ENV='development';
  const make=(body:string,origin='http://127.0.0.1:3000')=>new Request('http://127.0.0.1:3000/api/v1/auth/login',{method:'POST',headers:{origin,'content-type':'application/json'},body});
  assert.deepEqual(await accountBody(make('{}')),{});
  for(const request of [make('{}','https://evil.test'),make('null'),make('[]'),make('{'),make(JSON.stringify({x:'a'.repeat(5000)}))]) await assert.rejects(()=>accountBody(request),AccountError);
});

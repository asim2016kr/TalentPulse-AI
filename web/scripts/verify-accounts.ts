/** Opt-in integration test; synthetic app users only, no Auth accounts or emails. */
import {config} from 'dotenv';
import {resolve} from 'node:path';
import {readFileSync,writeFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
import {Pool} from 'pg';
import {saveJob,trackClick,updateApplication,personalList} from '../lib/personal';
import {memberDatabase} from '../lib/member-db';
config({path:resolve('../.env'),quiet:true});
const uri=new URL(process.env.DATABASE_URL!);
for(const key of ['sslmode','sslrootcert','sslcert','sslkey','uselibpqcompat'])uri.searchParams.delete(key);
const owner=new Pool({connectionString:uri.toString(),ssl:{ca:readFileSync(resolve('..',process.env.DATABASE_CA_CERT!),'utf8'),rejectUnauthorized:true},max:1});
const a=randomUUID(),b=randomUUID(),checks:string[]=[];
async function main(){
  try{
    await owner.query(`INSERT INTO app.users(id,email,display_name,email_verified_at) VALUES($1,$2,'Integration A',now()),($3,$4,'Integration B',now())`,[a,`${a}@test.invalid`,b,`${b}@test.invalid`]);
    const jobs=(await owner.query(`SELECT id FROM app.jobs WHERE status='active' AND NOT is_development AND fresh_until>now() AND (expires_at IS NULL OR expires_at>now()) LIMIT 2`)).rows;
    assert.equal(jobs.length,2);const j=jobs[0].id,k=jobs[1].id;
    await saveJob(a,j,true);await saveJob(a,j,true);
    assert.equal((await personalList(a,'saved')).pagination.total,1);assert.equal((await personalList(b,'saved')).pagination.total,0);checks.push('save idempotency and cross-user isolation');
    await assert.rejects(()=>memberDatabase(a,db=>db.query('INSERT INTO app.saved_jobs(user_id,job_id) VALUES($1,$2)',[b,k])));checks.push('RLS rejects forged owner');
    await assert.rejects(()=>memberDatabase(a,db=>db.query("UPDATE app.users SET disabled_at=NULL WHERE id=$1",[a])));checks.push('runtime cannot change disable flag');
    await assert.rejects(()=>memberDatabase(a,db=>db.query('SELECT classification FROM app.jobs')));checks.push('private ingestion evidence denied');
    assert.equal((await memberDatabase(null,db=>db.query('SELECT * FROM app.saved_jobs'))).rowCount,0);checks.push('pool identity is transaction-local');
    const key=randomUUID();const first=await trackClick(a,j,key);assert.equal(first.application_status,'clicked');
    await Promise.all([trackClick(a,j,key),trackClick(a,j,key)]);
    assert.equal(Number((await owner.query('SELECT count(*) FROM app.application_clicks WHERE user_id=$1',[a])).rows[0].count),1);checks.push('concurrent click retries create one event');
    await assert.rejects(()=>trackClick(a,k,key),{status:409});checks.push('cross-job key reuse rejected');
    const applied=await updateApplication(a,j,'applied');assert.ok(applied.self_reported_applied_at);
    const repeated=await updateApplication(a,j,'applied');assert.equal(repeated.updated_at.toISOString(),applied.updated_at.toISOString());
    assert.equal((await trackClick(a,j,randomUUID())).application_status,'applied');
    const interview=await updateApplication(a,j,'interviewing');assert.equal(interview.self_reported_applied_at.toISOString(),applied.self_reported_applied_at.toISOString());checks.push('applied status and timestamp survive repeat clicks and no-op edits');
    assert.equal((await personalList(b,'applications')).pagination.total,0);checks.push('application tracker isolation');
    await saveJob(a,j,false);assert.equal((await personalList(a,'saved')).pagination.total,0);checks.push('bookmark removal');
    await owner.query('UPDATE app.users SET disabled_at=now() WHERE id=$1',[a]);
    assert.equal((await personalList(a,'applications')).pagination.total,0);
    await assert.rejects(()=>saveJob(a,j,true));checks.push('disabled account RLS blocks reads and writes');
    const result={passed:true,checks,emails_sent:0,auth_accounts_created:0};
    writeFileSync(resolve('../product/output/accounts_validation.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify({passed:true,checks:checks.length,emails_sent:0}));
  }finally{
    // Only the two random IDs created by this test; FK cascades remove their test actions.
    await owner.query('DELETE FROM app.users WHERE id=ANY($1::uuid[])',[ [a,b] ]);
    await owner.end();
  }
}
main().then(()=>process.exit(0)).catch(()=>{console.error('Account integration test failed; synthetic fixtures were cleaned up.');process.exit(1);});

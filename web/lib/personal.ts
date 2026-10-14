import 'server-only';
import {type PoolClient} from 'pg';
import {memberDatabase} from './member-db';
import {AccountError,applicationStatuses} from './account-policy';
import {ACTIVE} from './search';
import {applicationDestination} from './application-policy';

async function eligibleJob(db:PoolClient,id:string) {
  const row=(await db.query(`SELECT j.source,j.application_url,j.application_url_kind,(${ACTIVE}) AS eligible
    FROM app.jobs j WHERE j.id=$1 AND NOT j.is_development AND j.status IN ('active','expired')`,[id])).rows[0];
  if(!row || !applicationDestination(row)) throw new AccountError(410,'UNAVAILABLE','This listing is no longer available.');
  return row;
}
export async function saveJob(userId:string,jobId:string,save:boolean) {
  return memberDatabase(userId,async db=>{
    if(save){await eligibleJob(db,jobId);await db.query('INSERT INTO app.saved_jobs(user_id,job_id) VALUES($1,$2) ON CONFLICT DO NOTHING',[userId,jobId]);}
    else await db.query('DELETE FROM app.saved_jobs WHERE user_id=$1 AND job_id=$2',[userId,jobId]);
    return {job_id:jobId,saved:save};
  });
}
export async function trackClick(userId:string,jobId:string,requestId:string) {
  return memberDatabase(userId,async db=>{
    const row=await eligibleJob(db,jobId);
    // Serializes a user's retries so a key cannot concurrently create two events.
    await db.query('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',[userId]);
    const prior=(await db.query('SELECT job_id FROM app.application_clicks WHERE user_id=$1 AND request_id=$2',[userId,requestId])).rows[0];
    if(prior && prior.job_id!==jobId) throw new AccountError(409,'IDEMPOTENCY_CONFLICT','This request was already used for another listing.');
    if(!prior){
      await db.query('INSERT INTO app.application_clicks(user_id,job_id,request_id) VALUES($1,$2,$3)',[userId,jobId,requestId]);
      await db.query(`INSERT INTO app.applications(user_id,job_id,first_clicked_at,last_clicked_at) VALUES($1,$2,now(),now())
        ON CONFLICT(user_id,job_id) DO UPDATE SET first_clicked_at=coalesce(app.applications.first_clicked_at,now()),last_clicked_at=now()`,[userId,jobId]);
    }
    const application=(await db.query('SELECT status FROM app.applications WHERE user_id=$1 AND job_id=$2',[userId,jobId])).rows[0];
    return {redirect_url:applicationDestination(row),destination_kind:'source_listing',tracked:true,application_status:application.status};
  });
}
export async function updateApplication(userId:string,jobId:string,status:string) {
  if(!applicationStatuses.includes(status as typeof applicationStatuses[number])) throw new AccountError(422,'INVALID_STATUS','Choose a valid application status.');
  return memberDatabase(userId,async db=>{
    await db.query('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',[userId]);
    const prior=(await db.query('SELECT * FROM app.applications WHERE user_id=$1 AND job_id=$2 FOR UPDATE',[userId,jobId])).rows[0];
    if(prior?.status===status) return prior;
    if(!prior) await eligibleJob(db,jobId);
    return (await db.query(`INSERT INTO app.applications(user_id,job_id,status,self_reported_applied_at)
      VALUES($1,$2,$3,CASE WHEN $3='applied' THEN now() END)
      ON CONFLICT(user_id,job_id) DO UPDATE SET status=excluded.status,status_updated_at=now(),
      self_reported_applied_at=CASE WHEN excluded.status='applied' THEN coalesce(app.applications.self_reported_applied_at,now()) ELSE app.applications.self_reported_applied_at END RETURNING *`,[userId,jobId,status])).rows[0];
  });
}
export async function personalList(userId:string,kind:'saved'|'applications',page=1,status='') {
  return memberDatabase(userId,async db=>{
    const table=kind==='saved'?'saved_jobs':'applications';
    const filter=kind==='applications' && status?' AND p.status=$2':'';
    const values:unknown[]=[userId];if(filter) values.push(status);
    const count=Number((await db.query(`SELECT count(*) FROM app.${table} p WHERE p.user_id=$1${filter}`,values)).rows[0].count);
    const rows=await db.query(`SELECT p.*,j.title,c.name AS company,j.location_text,j.status AS listing_status,
      coalesce((${ACTIVE}),false) AS can_apply
      FROM app.${table} p LEFT JOIN app.jobs j ON j.id=p.job_id LEFT JOIN app.companies c ON c.id=j.company_id
      WHERE p.user_id=$1${filter} ORDER BY p.${kind==='saved'?'created_at':'updated_at'} DESC,p.job_id
      LIMIT 20 OFFSET $${values.length+1}`,[...values,(page-1)*20]);
    return {data:rows.rows,pagination:{page,page_size:20,total:count,total_pages:Math.ceil(count/20)}};
  });
}

import 'server-only';
import {Pool,type PoolClient} from 'pg';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {AccountError} from './account-policy';
let pool:Pool;
export async function memberDatabase<T>(userId:string|null, work:(db:PoolClient)=>Promise<T>):Promise<T> {
  if(!pool) {
    if(!process.env.MEMBER_DATABASE_URL || !process.env.DATABASE_CA_CERT) throw new Error('Account database unavailable');
    const uri=new URL(process.env.MEMBER_DATABASE_URL);
    for(const key of ['sslmode','sslrootcert','sslcert','sslkey','uselibpqcompat']) uri.searchParams.delete(key);
    pool=new Pool({connectionString:uri.toString(),ssl:{ca:readFileSync(resolve(process.cwd(),'..',process.env.DATABASE_CA_CERT),'utf8'),rejectUnauthorized:true},
      max:4,connectionTimeoutMillis:10000,statement_timeout:10000,idleTimeoutMillis:10000,application_name:'talentpulse-accounts'});
    pool.on('error',()=>console.warn('Account database connection closed.'));
  }
  const db=await pool.connect();let broken=false;
  try {
    await db.query('BEGIN');
    const {rows}=await db.query(`SELECT rolsuper,rolbypassrls,pg_has_role(current_user,'talentpulse_member','MEMBER') AS member,
      pg_has_role(current_user,'talentpulse_ingest','MEMBER') AS ingest FROM pg_roles WHERE rolname=current_user`);
    if(!rows[0]?.member || rows[0].rolsuper || rows[0].rolbypassrls || rows[0].ingest) throw new Error('Unsafe account role');
    await db.query('SET LOCAL ROLE talentpulse_member');
    await db.query("SELECT set_config('app.user_id',$1,true)",[userId||'']);
    const result=await work(db);await db.query('COMMIT');return result;
  } catch(error) {try{await db.query('ROLLBACK');}catch{broken=true;}throw error;}
  finally{db.release(broken);}
}
export async function consumeLimit(key:string,scope:'auth_global'|'auth_account'|'action') {
  const digest=createHash('sha256').update(key).digest('hex');
  const allowed=await memberDatabase(null,async db=>(await db.query('SELECT app.consume_limit($1,$2) AS allowed',[digest,scope])).rows[0].allowed);
  if(!allowed) throw new AccountError(429,'RATE_LIMITED','Too many attempts. Please wait before trying again.');
}

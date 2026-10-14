/** Read-only production configuration and restricted-role connectivity gate. */
import {config} from 'dotenv';
import {resolve} from 'node:path';
import {database} from '../lib/database';
import {memberDatabase} from '../lib/member-db';
import {authConfig,cookieSettings} from '../lib/auth-config';
config({path:resolve('../.env'),quiet:true});
async function main(){
  const problems:string[]=[];
  if(process.env.APP_ENV!=='production') problems.push('Set APP_ENV=production');
  try {
    const url=new URL(process.env.APP_BASE_URL||'');
    if(url.protocol!=='https:'||url.username||url.password||url.pathname!=='/'||url.search||url.hash) throw new Error();
  } catch {problems.push('Set APP_BASE_URL to the public HTTPS origin');}
  if(process.env.ALLOW_DEVELOPMENT_JOBS!=='false') problems.push('Set ALLOW_DEVELOPMENT_JOBS=false');
  if(!process.env.DATABASE_CA_CERT) problems.push('Configure the trusted database CA');
  try{authConfig();}catch{problems.push('Configure Supabase authentication');}
  if(!cookieSettings().secure) problems.push('Secure session cookies required');
  // The web service must not receive owner/worker or AI/warehouse credentials.
  for(const key of ['DATABASE_URL','INGEST_DATABASE_URL','GEMINI_API_KEY','OPENAI_API_KEY','SNOWFLAKE_PASSWORD'])
    if(process.env[key]) problems.push(`Remove ${key} from the web deployment environment`);
  if(problems.length){console.error(JSON.stringify({passed:false,checks:problems}));process.exit(1);}
  try {
    await database(db=>db.query('SELECT id FROM app.jobs LIMIT 1'));
    await memberDatabase(null,db=>db.query('SELECT id FROM app.users LIMIT 1'));
    console.log(JSON.stringify({passed:true,message:'Configuration and restricted roles verified; complete manual launch gates in the runbook.'}));
    process.exit(0);
  }catch{console.error('Restricted database connectivity or role check failed.');process.exit(1);}
}
void main();

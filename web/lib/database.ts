import 'server-only';
import { Pool, type PoolClient } from 'pg';
import { config } from 'dotenv';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { developmentPreview } from './search';

// Python and the local API share root server config; deployment uses real env vars.
if (process.env.NODE_ENV !== 'production') config({path:resolve(process.cwd(),'../.env'),quiet:true});
let pool: Pool | undefined;
export async function database<T>(work: (client:PoolClient,preview:boolean)=>Promise<T>):Promise<T> {
  const preview = developmentPreview(process.env);
  const url = process.env.APP_DATABASE_URL;
  if (!url || /YOUR_|<|>/.test(url)) throw new Error('Restricted database connection unavailable');
  const caPath=process.env.DATABASE_CA_CERT;
  const uri=new URL(url);
  // URL SSL parameters override pg's SSL object. Remove them only when supplying
  // an explicitly trusted CA and strict hostname/certificate verification.
  if (caPath) for (const key of ['sslmode','sslrootcert','sslcert','sslkey','uselibpqcompat']) uri.searchParams.delete(key);
  if (!pool) {
    pool = new Pool({connectionString:uri.toString(),
    ...(caPath?{ssl:{ca:readFileSync(resolve(process.cwd(),'..',caPath),'utf8'),rejectUnauthorized:true}}:{}),
    max:2,connectionTimeoutMillis:10000,idleTimeoutMillis:10000,
      statement_timeout:10000,application_name:'talentpulse-read-api'});
    pool.on('error',()=>console.warn('Idle database connection closed; subsequent requests will reconnect.'));
  }
  const client = await pool.connect();
  let releaseError: Error | undefined;
  try {
    await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
    const check = await client.query(`SELECT r.rolsuper,r.rolbypassrls,
      pg_has_role(current_user,'talentpulse_read','MEMBER') AS reader,
      pg_has_role(current_user,'talentpulse_ingest','MEMBER') AS writer
      FROM pg_roles r WHERE r.rolname=current_user`);
    const flags = check.rows[0];
    if (!flags || flags.rolsuper || flags.rolbypassrls || !flags.reader || flags.writer) throw new Error('Unsafe runtime role');
    await client.query(preview ? 'SET LOCAL ROLE talentpulse_preview' : 'SET LOCAL ROLE talentpulse_read');
    const result = await work(client,preview);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    try { await client.query('ROLLBACK'); } catch {releaseError=new Error('Discard failed connection');}
    throw error;
  } finally {client.release(releaseError);}
}

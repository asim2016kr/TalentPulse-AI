import 'server-only';
import {createServerClient} from '@supabase/ssr';
import {cookies,headers} from 'next/headers';
import {authConfig,cookieSettings} from './auth-config';
import {AccountError} from './account-policy';
import {memberDatabase} from './member-db';

export async function authClient() {
  const jar=await cookies();const {url,key}=authConfig();
  return createServerClient(url,key,{cookieOptions:cookieSettings(),global:{fetch:(input,init)=>fetch(input,{...init,signal:AbortSignal.timeout(10000)})},cookies:{
    getAll:()=>jar.getAll(),setAll:values=>{try{values.forEach(({name,value,options})=>jar.set(name,value,{...options,...cookieSettings()}));}catch{/* Server components refresh through proxy. */}}
  }});
}
export async function currentUser(required=false) {
  if((await headers()).has('authorization')) throw new AccountError(401,'INVALID_SESSION','Sign in through TalentPulse to continue.');
  const jar=await cookies();
  if(!jar.getAll().some(c=>/^sb-.*-auth-token(?:\.\d+)?$/.test(c.name))) {
    if((await headers()).get('x-tp-had-session')==='1') throw new AccountError(401,'INVALID_SESSION','Your session has expired. Please sign in again.');
    if(required) throw new AccountError(401,'SIGN_IN_REQUIRED','Sign in to continue.');return null;
  }
  const supabase=await authClient();const {data,error}=await supabase.auth.getUser();
  if(error || !data.user) {
    if(error && (!error.status || error.status>=500)) throw new AccountError(503,'AUTH_UNAVAILABLE','Sign-in service is temporarily unavailable.');
    throw new AccountError(401,'INVALID_SESSION','Your session has expired. Please sign in again.');
  }
  const user=data.user;
  if(!user.email || !user.email_confirmed_at) throw new AccountError(403,'VERIFY_EMAIL','Verify your email before continuing.');
  const profile=await memberDatabase(user.id,async db=>{
    await db.query(`INSERT INTO app.users(id,email,display_name,email_verified_at,last_sign_in_at) VALUES($1,$2,$3,$4,$5)
      ON CONFLICT(id) DO UPDATE SET email=excluded.email,email_verified_at=excluded.email_verified_at,last_sign_in_at=excluded.last_sign_in_at`,
      [user.id,user.email,String(user.user_metadata?.display_name||'').slice(0,100),user.email_confirmed_at,user.last_sign_in_at||null]);
    return (await db.query('SELECT id,email,display_name,disabled_at FROM app.users WHERE id=$1',[user.id])).rows[0];
  });
  if(!profile || profile.disabled_at) throw new AccountError(403,'ACCOUNT_DISABLED','This account is unavailable.');
  return {id:profile.id as string,email:profile.email as string,display_name:profile.display_name as string,email_verified:true};
}

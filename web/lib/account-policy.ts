export class AccountError extends Error {
  constructor(public status:number, public code:string, message:string) {super(message);}
}
export function safeNext(value:unknown):string {
  if(typeof value!=='string') return '/dashboard';
  return /^\/jobs\/[0-9a-f-]{36}$/i.test(value) || ['/dashboard','/dashboard/saved','/dashboard/applications','/reset-password'].includes(value) ? value : '/dashboard';
}
export const applicationStatuses=['applied','interviewing','offer','rejected','withdrawn'] as const;
export function callbackOrigin(host:string|null,env:{APP_ENV?:string;APP_BASE_URL?:string}) {
  if(env.APP_ENV==='development') {
    if(host==='127.0.0.1:3000'||host==='localhost:3000') return 'http://'+host;
    throw new AccountError(400,'INVALID_CALLBACK','Invalid callback origin.');
  }
  if(!env.APP_BASE_URL || new URL(env.APP_BASE_URL).protocol!=='https:') throw new AccountError(503,'AUTH_UNAVAILABLE','Authentication is not configured.');
  return new URL(env.APP_BASE_URL).origin;
}
export function authInput(body:Record<string,unknown>, action:string) {
  const email=typeof body.email==='string'?body.email.trim().toLowerCase():'';
  const password=typeof body.password==='string'?body.password:'';
  const displayName=typeof body.display_name==='string'?body.display_name.trim():'';
  if(['login','signup','forgot-password'].includes(action) && (email.length>254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))) throw new AccountError(422,'INVALID_INPUT','Enter a valid email address.');
  if(['signup','reset-password'].includes(action) && (password.length<12 || password.length>128)) throw new AccountError(422,'INVALID_INPUT','Use a password between 12 and 128 characters.');
  if(action==='login' && (!password || password.length>128)) throw new AccountError(422,'INVALID_INPUT','Enter your email and password.');
  if(action==='signup' && (!displayName || displayName.length>100 || /[\x00-\x1f]/.test(displayName))) throw new AccountError(422,'INVALID_INPUT','Enter a name between 1 and 100 characters.');
  return {email,password,displayName,next:safeNext(body.next)};
}

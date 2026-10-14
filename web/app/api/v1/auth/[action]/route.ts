import {authClient,currentUser} from '../../../../../lib/auth';
import {authInput,AccountError} from '../../../../../lib/account-policy';
import {accountBody} from '../../../../../lib/account-http';
import {consumeLimit} from '../../../../../lib/member-db';
import {json,failure} from '../../../../../lib/response';
export const dynamic='force-dynamic';
type Context={params:Promise<{action:string}>};
export async function GET(_request:Request,{params}:Context) {
  try{if((await params).action!=='me') throw new AccountError(404,'NOT_FOUND','Route not found.');return json({data:await currentUser(true)});}catch(e){return failure(e);}
}
export async function POST(request:Request,{params}:Context) {
  try {
    const {action}=await params;
    if(!['signup','login','logout','forgot-password','reset-password'].includes(action)) throw new AccountError(404,'NOT_FOUND','Route not found.');
    const body=await accountBody(request);
    const allowed=['email','password','display_name','next'];
    if(Object.keys(body).some(k=>!allowed.includes(k))) throw new AccountError(400,'INVALID_INPUT','Unexpected request field.');
    const input=authInput(body,action);
    await consumeLimit('all','auth_global');
    if(input.email) await consumeLimit(input.email,'auth_account');
    const supabase=await authClient();
    const callback=new URL('/auth/callback',request.headers.get('origin')!);
    callback.searchParams.set('next',action==='forgot-password'?'/reset-password':input.next);
    if(action==='signup') {
      const {error}=await supabase.auth.signUp({email:input.email,password:input.password,options:{data:{display_name:input.displayName},emailRedirectTo:callback.href}});
      if(error && !['user_already_exists','email_exists'].includes(error.code||'')) throw new AccountError(error.status===429?429:503,'SIGNUP_UNAVAILABLE','We couldn’t process signup right now. Please try again later.');
      return json({data:{message:'If this address can be registered, you’ll receive a confirmation email. Check your inbox, then sign in.'}},202);
    }
    if(action==='login') {
      const {error}=await supabase.auth.signInWithPassword({email:input.email,password:input.password});
      if(error) throw new AccountError(401,'LOGIN_FAILED','Unable to sign in. Check your details and confirm your email.');
      return json({data:{user:await currentUser(true),next:input.next}});
    }
    if(action==='forgot-password') {
      const {error}=await supabase.auth.resetPasswordForEmail(input.email,{redirectTo:callback.href});
      if(error?.status===429) throw new AccountError(429,'RATE_LIMITED','Too many email requests. Please wait before trying again.');
      if(error && (!error.status || error.status>=500)) throw new AccountError(503,'EMAIL_UNAVAILABLE','Email delivery is temporarily unavailable. Please try again later.');
      return json({data:{message:'If an account exists for this address, you’ll receive a password reset email.'}},202);
    }
    if(action==='reset-password') {
      const user=await currentUser(true);await consumeLimit(user!.id,'action');
      const {error}=await supabase.auth.updateUser({password:input.password});
      if(error) throw new AccountError(422,'PASSWORD_REJECTED','The password could not be updated. Use a different password or request a new reset link.');
    }
    const {error}=await supabase.auth.signOut({scope:'global'});
    if(error && error.status!==401 && error.status!==403) throw new AccountError(503,'LOGOUT_FAILED','Couldn’t end your session. Please try again.');
    return json({data:{message:action==='reset-password'?'Password updated. Sign in with your new password.':'Signed out.'}});
  }catch(e){return failure(e);}
}

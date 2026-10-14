'use client';
import {useState,type FormEvent} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
export type AuthMode='login'|'signup'|'forgot-password'|'reset-password';
const titles={login:'Welcome back.',signup:'Your next chapter starts here.','forgot-password':'Let’s get you back in.','reset-password':'A fresh start.'};
const descriptions={login:'Sign in to revisit your saved roles and keep track of your next move.',signup:'Keep the opportunities that matter. Follow your applications, all in one place.','forgot-password':'Enter your account email and we’ll send you a password reset link.','reset-password':'Choose a strong, unique password for your TalentPulse account.'};
export function AuthForm({mode,next,notice}:{mode:AuthMode;next:string;notice?:string}) {
  const router=useRouter();const [busy,setBusy]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState(''),[show,setShow]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(busy)return;setBusy(true);setError('');
    const form=new FormData(event.currentTarget);
    const body:Record<string,string>={next};for(const [k,v] of form.entries())body[k]=String(v);
    try {
      const response=await fetch(`/api/v1/auth/${mode}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(25000)});
      const data=await response.json();
      if(!response.ok){setError(data.error?.message||'Something went wrong. Please try again.');return;}
      if(mode==='login'){router.replace(next);router.refresh();}else setSuccess(data.data.message);
    }catch{setError('We couldn’t connect. Please check your connection and try again.');}finally{setBusy(false);}
  }
  return <div className="auth-card">
    <p className="eyebrow">{mode==='login'?'YOUR TALENTPULSE ACCOUNT':'A LITTLE MOMENTUM'}</p>
    <h1>{titles[mode]}</h1><p className="muted auth-intro">{descriptions[mode]}</p>
    {notice==='link-expired'&&<p className="form-message" role="alert">This link has expired or was opened in a different browser. Request a new reset link, or sign in after confirming your email.</p>}
    {success ? <div className="success-panel" role="status"><span aria-hidden="true">✓</span><h2>{mode==='reset-password'?'Password updated':'Check your inbox'}</h2><p>{success}</p><Link className="button" href={'/login?next='+encodeURIComponent(next)}>Go to sign in</Link><p className="fine-print">For email links, continue in this browser. Check your spam folder if needed.</p></div> :
    <form onSubmit={submit} className="account-form">
      {mode==='signup'&&<label>Your name<input required name="display_name" autoComplete="name" maxLength={100} placeholder="How should we address you?"/></label>}
      {mode!=='reset-password'&&<label>Email address<input required type="email" name="email" autoComplete="email" maxLength={254} placeholder="you@example.com"/></label>}
      {mode!=='forgot-password'&&<label>Password<div className="password-field"><input required type={show?'text':'password'} name="password" aria-label="Password" autoComplete={mode==='login'?'current-password':'new-password'} minLength={mode==='login'?1:12} maxLength={128} aria-describedby={mode==='login'?undefined:'password-help'}/><button type="button" onClick={()=>setShow(!show)} aria-label={show?'Hide password':'Show password'}>{show?'Hide':'Show'}</button></div>{mode!=='login'&&<small id="password-help">At least 12 characters. Use a unique password.</small>}</label>}
      {mode==='login'&&<Link href="/forgot-password" className="forgot-link">Forgot password?</Link>}
      {error&&<p className="form-message" role="alert">{error}</p>}
      <button className="button" disabled={busy} aria-busy={busy}>{busy?'Please wait…':mode==='login'?'Sign in →':mode==='signup'?'Create account →':mode==='forgot-password'?'Send reset link →':'Update password →'}</button>
    </form>}
    {!success&&<p className="auth-alternative">{mode==='login'?<>New to TalentPulse? <Link href={'/signup?next='+encodeURIComponent(next)}>Create an account</Link></>:<>Already have an account? <Link href={'/login?next='+encodeURIComponent(next)}>Sign in</Link></>}</p>}
    <Link href="/jobs" className="browse-guest">Keep exploring jobs without an account ↗</Link>
  </div>;
}

'use client';
import {useEffect,useState} from 'react';
import {usePathname} from 'next/navigation';
import Link from 'next/link';
export function AccountNav(){
  const [signedIn,setSignedIn]=useState(false);const path=usePathname();
  useEffect(()=>{const controller=new AbortController();fetch('/api/v1/auth/me',{signal:controller.signal,cache:'no-store'}).then(r=>setSignedIn(r.ok)).catch(()=>{});return()=>controller.abort();},[path]);
  return <div className="account-nav">{signedIn?<Link className="button small" href="/dashboard">My workspace ↗</Link>:<><Link className="sign-in-link" href="/login">Sign in</Link><Link className="button small" href="/signup">Join TalentPulse ↗</Link></>}</div>;
}

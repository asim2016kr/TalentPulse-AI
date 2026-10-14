'use client';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
export default function WorkspaceError({reset}:{reset:()=>void}) {
  const router=useRouter();
  return <main id="main" className="section empty" role="alert"><p className="eyebrow">YOUR WORKSPACE</p><h1>We couldn’t load your workspace.</h1><p>Your account service may be temporarily unavailable. Try again, or sign in to restore your session.</p><button className="button" onClick={()=>{router.refresh();reset();}}>Try again</button><Link className="clear" href="/login?next=/dashboard">Return to sign in</Link></main>;
}

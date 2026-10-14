'use client';
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
export function SaveButton({jobId,available}:{jobId:string;available:boolean}) {
  const router=useRouter();const [saved,setSaved]=useState(false),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[known,setKnown]=useState(false),[retry,setRetry]=useState(0);
  useEffect(()=>{const abort=new AbortController();setLoading(true);setError('');fetch('/api/v1/me/saved-jobs/'+jobId,{signal:abort.signal,cache:'no-store'}).then(async r=>{
    if(r.ok){setSaved((await r.json()).data.saved);setKnown(true);}else if(r.status===401){setKnown(true);setSaved(false);}else throw new Error();
  }).catch(()=>{if(!abort.signal.aborted){setKnown(false);setError('Couldn’t load your shortlist. Please retry.');}}).finally(()=>setLoading(false));return()=>abort.abort();},[jobId,retry]);
  async function save(){if(busy)return;setBusy(true);setError('');try{
    const response=await fetch('/api/v1/me/saved-jobs/'+jobId,{method:saved?'DELETE':'PUT',headers:{'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(20000)});
    if(response.status===401){router.push('/login?next='+encodeURIComponent('/jobs/'+jobId));return;}
    const payload=await response.json();if(!response.ok){setError(payload.error?.message||'Couldn’t save this role.');return;}setSaved(payload.data.saved);
  }catch{setError('Connection interrupted. Please try again.');}finally{setBusy(false);}}
  return <div className="save-control"><button className="button secondary" disabled={loading||busy||(known&&!available&&!saved)} aria-pressed={saved} onClick={known?save:()=>setRetry(retry+1)}>{loading?'Loading shortlist…':busy?'Updating…':!known?'Retry shortlist':saved?'✓ Saved · Remove':'＋ Save this job'}</button>{error&&<p role="alert" className="form-message">{error}</p>}</div>;
}

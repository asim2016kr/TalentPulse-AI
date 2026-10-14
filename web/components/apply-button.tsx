'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { applicationDestination } from '../lib/application-policy';

export function ApplyButton({jobId, available}: {jobId: string; available: boolean}) {
  const pending = useRef(false);
  const requestId = useRef<string|null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [signInRequired,setSignInRequired]=useState(false);
  const [unavailable, setUnavailable] = useState(!available);

  async function apply() {
    if (pending.current || unavailable) return;
    pending.current = true;
    setBusy(true);
    setMessage('');
    setSignInRequired(false);
    try {
      const response = await fetch(`/api/v1/jobs/${jobId}/apply-click`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify({request_id: requestId.current ??= crypto.randomUUID()}),
        signal: AbortSignal.timeout(20_000),
      });
      const payload = await response.json();
      if (!response.ok) {
        if(response.status===401){setSignInRequired(true);setMessage('Your session has expired. Sign in again before continuing.');return;}
        if (response.status === 404 || response.status === 410) setUnavailable(true);
        setMessage(response.status === 429 ? 'Please wait a minute before trying again.' :
          response.status === 404 || response.status === 410 ? 'This listing is no longer available to apply. Explore other jobs.' :
          'We couldn’t open the application site. Please try again.');
        return;
      }
      const destination = applicationDestination({source: 'remoteok', application_url: payload.data?.redirect_url,
        application_url_kind: payload.data?.destination_kind, eligible: true});
      if (!destination) throw new Error('Unapproved destination');
      window.location.assign(destination);
    } catch {
      setMessage('We couldn’t open the application site. Please check your connection and try again.');
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return <div className="apply-control">
    <button type="button" className="button" disabled={busy || unavailable} onClick={apply} aria-describedby="apply-explanation" aria-busy={busy}>
      {busy ? 'Checking availability…' : unavailable ? 'Apply unavailable' : 'Apply on Remote OK ↗'}
    </button>
    <p id="apply-explanation" className="fine-print">You’ll leave TalentPulse to apply. If signed in, we record that you opened the site. This does not mean you submitted an application.</p>
    {message && <p className="apply-feedback" role="alert">{message}</p>}
    {signInRequired&&<Link className="clear" href={'/login?next='+encodeURIComponent('/jobs/'+jobId)}>Sign in again</Link>}
    <noscript><p className="notice">Enable JavaScript to check availability and continue to the application site.</p></noscript>
  </div>;
}

import {AuthForm,type AuthMode} from './auth-form';
import {safeNext} from '../lib/account-policy';
export function AccountPage({mode,next,notice}:{mode:AuthMode;next?:unknown;notice?:string}) {
  return <main id="main" className="account-shell"><section className="account-story"><p className="eyebrow">YOUR CAREER, WITH DIRECTION</p><h2>Make room for <br/>your next chapter<span className="dot">.</span></h2><p>Good opportunities deserve more than another open tab.</p><div className="account-benefits"><div><span>01</span><h3>Keep your shortlist</h3><p>Save the roles you want to come back to.</p></div><div><span>02</span><h3>Know where you stand</h3><p>Track your own progress from applied to offer.</p></div><div><span>03</span><h3>Take the next step</h3><p>Apply directly through the original job listing.</p></div></div><p className="fine-print">Your account. Your job search. One place to stay organised.</p></section><AuthForm mode={mode} next={safeNext(next)} notice={notice}/></main>;
}

import type { ReactNode } from 'react';
import Link from 'next/link';
import './globals.css';
import {AccountNav} from '../components/account-nav';
// Every document must receive its own script nonce, including error/auth pages.
export const dynamic='force-dynamic';
export const metadata = {title: {default:'TalentPulse | Find your next opportunity',template:'%s | TalentPulse'},description:'Discover technology jobs, explore opportunities and connect with the original listing.'};
export default function RootLayout({children}: {children: ReactNode}) {
  return <html lang="en"><body><a className="skip" href="#main">Skip to content</a><header className="header"><Link href="/" className="brand"><span aria-hidden="true" className="brand-icon">↗</span>talentpulse<span className="dot">.</span></Link><nav aria-label="Main navigation"><Link href="/jobs">Find jobs</Link><Link href="/#how-it-works">How it works</Link></nav><AccountNav/></header>{children}<footer><Link className="brand" href="/">talentpulse.</Link><p>Your next chapter starts with an opportunity.</p><span>Listings sourced from <a href="https://remoteok.com" target="_blank" rel="noopener noreferrer">Remote OK ↗</a></span></footer></body></html>;
}

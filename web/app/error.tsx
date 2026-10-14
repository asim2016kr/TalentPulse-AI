'use client';
import Link from 'next/link';
export default function ErrorPage({reset}:{reset:()=>void}) {return <main id="main" className="section empty" role="alert"><h1>We couldn’t load this page.</h1><p>The job service may be temporarily unavailable. Please try again.</p><button className="button" onClick={reset}>Try again</button><Link href="/" className="clear">Back to home</Link></main>;}

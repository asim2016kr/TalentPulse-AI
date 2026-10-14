import {NextResponse} from 'next/server';
import {authClient} from '../../../lib/auth';
import {safeNext,callbackOrigin} from '../../../lib/account-policy';
import {applicationOrigins} from '../../../lib/apply-handler';
export async function GET(request:Request) {
  const url=new URL(request.url);
  const origins=applicationOrigins({APP_BASE_URL:process.env.APP_BASE_URL,APP_ENV:process.env.APP_ENV});
  let origin:string;
  try{origin=callbackOrigin(request.headers.get('host'),{APP_ENV:process.env.APP_ENV,APP_BASE_URL:process.env.APP_BASE_URL});}catch{return new Response('Invalid callback configuration',{status:400});}
  if(!origins.has(origin)) return new Response('Invalid callback origin',{status:400});
  const code=url.searchParams.get('code');
  let ok=false;
  if(code && code.length<2048) {try{const client=await authClient();const {error}=await client.auth.exchangeCodeForSession(code);ok=!error;}catch{}}
  const destination=ok?safeNext(url.searchParams.get('next')):'/login?notice=link-expired';
  const response=NextResponse.redirect(new URL(destination,origin),303);
  response.headers.set('Cache-Control','no-store');response.headers.set('Referrer-Policy','no-referrer');return response;
}

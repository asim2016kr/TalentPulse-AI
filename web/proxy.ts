import {NextResponse,type NextRequest} from 'next/server';
import {createServerClient} from '@supabase/ssr';
import {authConfig,cookieSettings} from './lib/auth-config';
import {randomBytes} from 'node:crypto';
import {contentSecurityPolicy} from './lib/security-policy';
export async function proxy(request:NextRequest) {
  const requestHeaders=new Headers(request.headers);
  const nonce=randomBytes(24).toString('base64');
  const policy=contentSecurityPolicy(nonce,process.env.NODE_ENV==='development');
  requestHeaders.set('x-nonce',nonce);
  requestHeaders.set('Content-Security-Policy',policy);
  requestHeaders.set('x-tp-had-session',request.cookies.getAll().some(c=>/^sb-.*-auth-token(?:\.\d+)?$/.test(c.name))?'1':'0');
  let response=NextResponse.next({request:{headers:requestHeaders}});
  if(request.cookies.getAll().some(c=>/^sb-.*-auth-token(?:\.\d+)?$/.test(c.name))) {
    try {
      const {url,key}=authConfig();
      const client=createServerClient(url,key,{cookieOptions:cookieSettings(),global:{fetch:(input,init)=>fetch(input,{...init,signal:AbortSignal.timeout(10000)})},cookies:{
        getAll:()=>request.cookies.getAll(),setAll:values=>{
          values.forEach(({name,value})=>request.cookies.set(name,value));
          requestHeaders.set('cookie',request.cookies.toString());
          response=NextResponse.next({request:{headers:requestHeaders}});
          values.forEach(({name,value,options})=>response.cookies.set(name,value,{...options,...cookieSettings()}));
        }
      }});
      await client.auth.getUser();
    }catch{/* Protected handlers independently verify identity and fail closed. */}
  }
  response.headers.set('Cache-Control','private, no-store');
  response.headers.set('Referrer-Policy','no-referrer');
  response.headers.set('Content-Security-Policy',policy);
  return response;
}
export const config={matcher:['/((?!_next/static|_next/image|favicon.ico).*)']};

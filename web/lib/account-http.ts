import {AccountError} from './account-policy';
import {applicationOrigins} from './apply-handler';
export function checkOrigin(request:Request) {
  const origins=applicationOrigins({APP_BASE_URL:process.env.APP_BASE_URL,APP_ENV:process.env.APP_ENV});
  if(!origins.has(request.headers.get('origin')||'') || request.headers.get('sec-fetch-site')==='cross-site') throw new AccountError(403,'ORIGIN_DENIED','Open TalentPulse to perform this action.');
}
export async function accountBody(request:Request):Promise<Record<string,unknown>> {
  checkOrigin(request);
  if(request.headers.get('content-type')?.split(';')[0]!=='application/json') throw new AccountError(415,'INVALID_CONTENT','Send a JSON request.');
  const reader=request.body?.getReader();if(!reader) throw new AccountError(400,'INVALID_INPUT','Invalid request.');
  let text='',size=0;const decoder=new TextDecoder();
  try {
    while(true){const {done,value}=await reader.read();if(done) break;size+=value.length;if(size>4096){await reader.cancel();throw new Error();}text+=decoder.decode(value,{stream:true});}
    const data=JSON.parse(text+decoder.decode());if(!data||typeof data!=='object'||Array.isArray(data)) throw new Error();return data;
  }catch{throw new AccountError(400,'INVALID_INPUT','Invalid request.');}finally{reader.releaseLock();}
}

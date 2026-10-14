import { randomUUID } from 'node:crypto';
import { InputError } from './search';
import { AccountError } from './account-policy';
export function json(value:unknown,status=200) {
  return Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}
export function failure(error:unknown) {
  const requestId=randomUUID();
  if(error instanceof AccountError) {
    const response=json({error:{code:error.code,message:error.message,request_id:requestId}},error.status);
    if(error.status===429) response.headers.set('Retry-After','900');
    return response;
  }
  const known=error instanceof InputError;
  // Correlate unexpected failures without logging SQL, credentials, tokens or PII.
  if(!known) console.error(JSON.stringify({event:'api_failure',request_id:requestId}));
  return json({error:{code:known?'INVALID_REQUEST':'SERVICE_UNAVAILABLE',
    message:known?error.message:'Job service is temporarily unavailable.',request_id:requestId}},known?error.status:503);
}

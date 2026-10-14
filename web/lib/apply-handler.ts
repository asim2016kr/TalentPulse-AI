import { randomUUID } from 'node:crypto';
import { validUUID } from './search';
import { json, failure } from './response';
import { applicationDestination, type ApplicationRecord } from './application-policy';

type Lookup = (id: string) => Promise<ApplicationRecord | null>;
function error(status: number, code: string, message: string) {
  return json({error: {code, message, request_id: randomUUID()}}, status);
}

// Bounded process-wide protection for the local MVP. This deliberately ignores
// untrusted forwarded IP headers. Shared deployment limits belong in Phase 6.
export function createApplyLimiter(limit = 120, windowMs = 60_000, clock = Date.now) {
  let windowStart = clock();
  let count = 0;
  return () => {
    const now = clock();
    if (now - windowStart >= windowMs) { windowStart = now; count = 0; }
    return ++count <= limit;
  };
}

export function applicationOrigins(env: {APP_BASE_URL?: string; APP_ENV?: string}) {
  const origins = new Set<string>();
  if (env.APP_BASE_URL) origins.add(new URL(env.APP_BASE_URL).origin);
  if (env.APP_ENV === 'development') {
    origins.add('http://127.0.0.1:3000');
    origins.add('http://localhost:3000');
  }
  return origins;
}

async function readBody(request: Request): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('Invalid body');
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > 1024) { await reader.cancel(); throw new Error('Invalid body'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

export function createApplyHandler(lookup: Lookup, allow: () => boolean, origins: () => Set<string>, accountClick?: (jobId:string,requestId:string)=>Promise<unknown|null>) {
  return async (request: Request, id: string): Promise<Response> => {
    try {
      if (request.method !== 'POST') return error(405, 'METHOD_NOT_ALLOWED', 'Use POST to continue to the application site.');
      if (!validUUID(id)) return error(400, 'INVALID_REQUEST', 'Invalid job ID.');
      if (new URL(request.url).search) return error(400, 'INVALID_REQUEST', 'Query parameters are not accepted.');
      const origin = request.headers.get('origin');
      if (!origin || !origins().has(origin) || request.headers.get('sec-fetch-site') === 'cross-site') {
        return error(403, 'ORIGIN_DENIED', 'Open this listing on TalentPulse before continuing.');
      }
      // Auth is not implemented in Phase 4. Never silently downgrade a supplied
      // bearer token or Supabase/TalentPulse session to an anonymous click.
      if (!accountClick && (request.headers.has('authorization') || /(?:^|;\s*)(?:sb-[^=]*|talentpulse_session|tp-session)=/i.test(request.headers.get('cookie') || ''))) {
        return error(401, 'AUTH_UNAVAILABLE', 'Account sessions are not supported by this version. Use a guest session.');
      }
      if (!allow()) {
        const response = error(429, 'RATE_LIMITED', 'Too many requests. Please wait a minute and try again.');
        response.headers.set('Retry-After', '60');
        return response;
      }
      if (request.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json') {
        return error(415, 'UNSUPPORTED_MEDIA_TYPE', 'Send a JSON request.');
      }
      let body: unknown;
      try { body = await readBody(request); }
      catch { return error(400, 'INVALID_REQUEST', 'Invalid application request.'); }
      if (!body || typeof body !== 'object' || Array.isArray(body) ||
          Object.keys(body).length !== 1 || !('request_id' in body) ||
          typeof body.request_id !== 'string' || !validUUID(body.request_id)) {
        return error(400, 'INVALID_REQUEST', 'A valid request_id is required.');
      }
      if(accountClick) {
        const tracked=await accountClick(id,body.request_id);
        if(tracked) return json({data:tracked});
      }
      const row = await lookup(id);
      if (!row) return error(404, 'NOT_FOUND', 'This job is no longer available.');
      const destination = applicationDestination(row);
      if (!destination) return error(410, 'APPLICATION_UNAVAILABLE', 'This listing is expired, awaiting a recheck, or has no approved application destination.');
      return json({data: {redirect_url: destination, destination_kind: 'source_listing', tracked: false, application_status: null}});
    } catch (cause) { return failure(cause); }
  };
}

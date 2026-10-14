import { applicationRecord } from '../../../../../../lib/jobs';
import { applicationOrigins, createApplyHandler, createApplyLimiter } from '../../../../../../lib/apply-handler';
import {currentUser} from '../../../../../../lib/auth';
import {consumeLimit} from '../../../../../../lib/member-db';
import {trackClick} from '../../../../../../lib/personal';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const apply = createApplyHandler(applicationRecord, createApplyLimiter(), () => applicationOrigins({
  APP_BASE_URL: process.env.APP_BASE_URL, APP_ENV: process.env.APP_ENV,
}),async (jobId,requestId)=>{
  const user=await currentUser();
  await consumeLimit(user?.id||'guest-apply','action');
  return user ? trackClick(user.id,jobId,requestId) : null;
});

export async function POST(request: Request, {params}: {params: Promise<{id: string}>}) {
  return apply(request, (await params).id);
}

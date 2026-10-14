import { InputError, validUUID } from '../../../../../lib/search';
import { jobDetail } from '../../../../../lib/jobs';
import { json,failure } from '../../../../../lib/response';
import { randomUUID } from 'node:crypto';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
  try {
    const {id}=await params;
    if (!validUUID(id)) throw new InputError('Invalid job ID');
    const row=await jobDetail(id);
    return row ? json({data:row}) : json({error:{code:'NOT_FOUND',message:'Job not found.',request_id:randomUUID()}},404);
  } catch(error) {return failure(error);}
}

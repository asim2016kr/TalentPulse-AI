import { parseSearch } from '../../../../lib/search';
import { listJobs } from '../../../../lib/jobs';
import { json,failure } from '../../../../lib/response';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET(request:Request) {
  try {return json(await listJobs(parseSearch(new URL(request.url).searchParams)));}
  catch(error) {return failure(error);}
}

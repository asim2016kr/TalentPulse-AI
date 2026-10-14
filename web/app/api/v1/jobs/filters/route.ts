import { jobFilters } from '../../../../../lib/jobs';
import { json,failure } from '../../../../../lib/response';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET() {
  try {return json(await jobFilters());} catch(error) {return failure(error);}
}

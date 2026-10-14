import { database } from '../../../../lib/database';
import { json,failure } from '../../../../lib/response';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function GET() {
  try {
    await database(async client=> {await client.query('SELECT id FROM app.jobs LIMIT 0');});
    return json({data:{status:'ready'}});
  } catch(error) {return failure(error);}
}

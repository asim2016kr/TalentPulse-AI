import {currentUser} from '../../../../../lib/auth';
import {accountBody} from '../../../../../lib/account-http';
import {AccountError,applicationStatuses} from '../../../../../lib/account-policy';
import {consumeLimit,memberDatabase} from '../../../../../lib/member-db';
import {personalList,saveJob,updateApplication} from '../../../../../lib/personal';
import {validUUID} from '../../../../../lib/search';
import {failure,json} from '../../../../../lib/response';
type Context={params:Promise<{path:string[]}>};
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:Context) {
  try {
    const path=(await params).path;
    if(path.length===2&&path[0]==='saved-jobs'&&validUUID(path[1])) {
      const user=await currentUser(true);
      const saved=await memberDatabase(user!.id,async db=>(await db.query('SELECT 1 FROM app.saved_jobs WHERE user_id=$1 AND job_id=$2',[user!.id,path[1]])).rowCount!>0);
      return json({data:{job_id:path[1],saved}});
    }
    if(path.length!==1||!['saved-jobs','applications'].includes(path[0])) throw new AccountError(404,'NOT_FOUND','Page not found.');
    const user=await currentUser(true);const query=new URL(request.url).searchParams;
    if([...query.keys()].some(k=>!['page','status'].includes(k)||query.getAll(k).length!==1)) throw new AccountError(400,'INVALID_INPUT','Invalid query.');
    const page=Number(query.get('page')||1),status=query.get('status')||'';
    if(!Number.isInteger(page)||page<1||page>500||(status&&!['clicked',...applicationStatuses].includes(status))) throw new AccountError(400,'INVALID_INPUT','Invalid filters.');
    return json(await personalList(user!.id,path[0]==='saved-jobs'?'saved':'applications',page,status));
  }catch(e){return failure(e);}
}
async function mutate(request:Request,{params}:Context) {
  try {
    const body=await accountBody(request);const [kind,id,...extra]=(await params).path;
    if(extra.length||!validUUID(id||'')||!['saved-jobs','applications'].includes(kind)) throw new AccountError(400,'INVALID_INPUT','Invalid job action.');
    const user=await currentUser(true);await consumeLimit(user!.id,'action');
    if(kind==='saved-jobs') {
      if(Object.keys(body).length) throw new AccountError(400,'INVALID_INPUT','Unexpected field.');
      return json({data:await saveJob(user!.id,id,request.method==='PUT')});
    }
    if(request.method!=='PUT'||Object.keys(body).length!==1||typeof body.status!=='string') throw new AccountError(400,'INVALID_INPUT','Choose a status.');
    return json({data:await updateApplication(user!.id,id,body.status)});
  }catch(e){return failure(e);}
}
export const PUT=mutate;
export const DELETE=mutate;

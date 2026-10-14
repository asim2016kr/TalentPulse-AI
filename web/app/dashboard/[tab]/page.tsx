import {redirect,notFound} from 'next/navigation';
import {currentUser} from '../../../lib/auth';
import {personalList} from '../../../lib/personal';
import {AccountError} from '../../../lib/account-policy';
import {Workspace} from '../../../components/workspace';
export const dynamic='force-dynamic';
export const metadata={title:'Your workspace',robots:{index:false,follow:false}};
export default async function Dashboard({params,searchParams}:{params:Promise<{tab:string}>;searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const {tab}=await params;if(tab!=='saved'&&tab!=='applications')notFound();
  let user;
  try{user=await currentUser(true);}catch(e){if(e instanceof AccountError&&e.status===401)redirect('/login?next='+encodeURIComponent('/dashboard/'+tab));throw e;}
  const search=await searchParams;const page=Number(search.page||1);
  if(!Number.isInteger(page)||page<1||page>500)redirect('/dashboard/'+tab);
  const list=await personalList(user!.id,tab,page);
  return <Workspace name={user!.display_name} kind={tab} list={list}/>;
}

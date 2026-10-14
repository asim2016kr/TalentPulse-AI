import {AccountPage} from '../../components/account-page';
export const metadata={title:'Sign in',robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{next?:string;notice?:string}>}){const query=await searchParams;return <AccountPage mode="login" next={query.next} notice={query.notice}/>;}

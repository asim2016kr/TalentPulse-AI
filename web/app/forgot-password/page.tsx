import {AccountPage} from '../../components/account-page';
export const metadata={title:'Reset your password',robots:{index:false,follow:false}};
export default async function Page({searchParams}:{searchParams:Promise<{next?:string;notice?:string}>}){const query=await searchParams;return <AccountPage mode="forgot-password" next={query.next} notice={query.notice}/>;}

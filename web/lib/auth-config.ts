export function authConfig() {
  const url=process.env.SUPABASE_URL,key=process.env.SUPABASE_PUBLISHABLE_KEY;
  if(!url || !key || !/^https:\/\/[a-z0-9]+\.supabase\.co$/.test(url)) throw new Error('Authentication unavailable');
  return {url,key};
}
export function cookieSettings() {
  return {httpOnly:true,sameSite:'lax' as const,secure:process.env.APP_ENV!=='development',path:'/'};
}

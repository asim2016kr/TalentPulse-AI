export function jobsHref(values:Record<string,string>,changes:Record<string,string>={}) {
  const merged={...values,...changes};
  if (!Object.hasOwn(changes,'page')) delete merged.page;
  const params=new URLSearchParams(Object.entries(merged).filter(([,v])=>v!==''));
  return '/jobs'+(params.size?'?'+params.toString():'');
}

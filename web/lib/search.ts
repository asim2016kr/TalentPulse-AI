export class InputError extends Error {
  constructor(message: string, public status = 400) { super(message); }
}
const roles = ['Data Engineer','Analytics Engineer','Data Scientist','Data Analyst','Machine Learning Engineer','AI Engineer','Software Engineer','DevOps / Cloud Engineer','Database Engineer','Cybersecurity','Product / Project Manager','QA / Test Engineer','IT / Technical Support','UX / UI Designer','Hardware / Embedded Engineer','Other'];
const categories = ['Data Engineering','Data Science','Data Analytics','Artificial Intelligence','Software Engineering','Cloud & DevOps','Database','Cybersecurity','Product & Project Management','IT Operations','Design','Hardware & Embedded','Other'];
export const filterValues = {
  role: roles, category: categories,
  experience_level: ['Intern','Junior','Mid','Senior','Lead','Principal','Other'],
  work_mode: ['Remote','Hybrid','On-site','Unknown'],
  job_type: ['Unknown','Internship','Contract','Part-Time','Freelance','Full-Time']
};
export type Search = {
  q: string; location: string; source_tag: string; company_id: string;
  role: string; category: string; experience_level: string; work_mode: string; job_type: string;
  page: number; page_size: number; sort: 'newest' | 'relevance';
};
export function validUUID(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
export function parseSearch(params: URLSearchParams): Search {
  const allowed = new Set(['q','location','source_tag','company_id','page','page_size','sort',...Object.keys(filterValues)]);
  for (const key of params.keys()) {
    if (!allowed.has(key) || params.getAll(key).length !== 1) throw new InputError('Unknown or repeated query parameter');
  }
  const text = (key: string, limit: number) => {
    const value = (params.get(key) ?? '').trim();
    if (value.length > limit || /[\x00-\x1f\x7f]/.test(value)) throw new InputError('Invalid search field');
    return value;
  };
  const integer = (key: string, defaultValue: number, max: number) => {
    const value = params.get(key);
    if (value === null) return defaultValue;
    if (!/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) > max) throw new InputError('Invalid pagination');
    return Number(value);
  };
  const result = { q:text('q',200), location:text('location',100), source_tag:text('source_tag',100),
    company_id:text('company_id',36), page:integer('page',1,10001), page_size:integer('page_size',20,50),
    sort:text('sort',20) || 'newest' } as Search;
  if (result.company_id && !validUUID(result.company_id)) throw new InputError('Invalid company ID');
  for (const key of Object.keys(filterValues) as (keyof typeof filterValues)[]) {
    result[key] = text(key,100);
    if (result[key] && !filterValues[key].includes(result[key])) throw new InputError('Invalid filter value',422);
  }
  if ((result.sort !== 'newest' && result.sort !== 'relevance') || (result.sort === 'relevance' && !result.q)) throw new InputError('Invalid sort');
  if ((result.page - 1) * result.page_size > 10000) throw new InputError('Pagination limit exceeded');
  return result;
}
export function developmentPreview(env: {APP_ENV?:string; ALLOW_DEVELOPMENT_JOBS?:string; NODE_ENV?:string}): boolean {
  if (env.ALLOW_DEVELOPMENT_JOBS === 'true') {
    if (env.APP_ENV !== 'development' || env.NODE_ENV === 'production') throw new Error('Development preview denied');
    return true;
  }
  return false;
}
export const ACTIVE = "j.status='active' AND NOT j.is_development AND j.fresh_until>now() AND (j.expires_at IS NULL OR j.expires_at>now())";
export function queryPlan(search: Search, preview = false) {
  const values: unknown[] = [];
  const add = (v: unknown) => { values.push(v); return '$'+values.length; };
  const clauses = [preview ? `(${ACTIVE} OR (j.is_development AND j.status='unverified'))` : ACTIVE];
  const escapeLike = (v: string) => v.replace(/[\\%_]/g, '\\$&');
  let rank = '0';
  if (search.q) {
    const q = add(search.q);
    const company = add('%'+escapeLike(search.q)+'%');
    clauses.push(`(j.search_document @@ websearch_to_tsquery('english',${q}) OR c.name ILIKE ${company})`);
    rank = `ts_rank(j.search_document,websearch_to_tsquery('english',${q}))`;
  }
  for (const key of Object.keys(filterValues) as (keyof typeof filterValues)[]) {
    if (search[key]) clauses.push(`j.${key}=${add(search[key])}`);
  }
  if (search.location) clauses.push(`j.location_text ILIKE ${add('%'+escapeLike(search.location)+'%')}`);
  if (search.company_id) clauses.push(`j.company_id=${add(search.company_id)}::uuid`);
  if (search.source_tag) clauses.push(`EXISTS(SELECT FROM unnest(j.source_tags) tag WHERE lower(tag)=lower(${add(search.source_tag)}))`);
  const order = (search.sort==='relevance' ? rank+' DESC, ' : '')+'j.published_at DESC NULLS LAST,j.id DESC';
  return {where:clauses.join(' AND '),values,order};
}

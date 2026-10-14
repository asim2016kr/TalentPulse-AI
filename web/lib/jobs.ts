import 'server-only';
import { database } from './database';
import { ACTIVE, queryPlan, type Search } from './search';
import { publicDescription } from './listing-text';
import { applicationDestination, type ApplicationRecord } from './application-policy';

const SUMMARY = `j.id,j.title,json_build_object('id',c.id,'name',c.name,'domain',c.domain) AS company,
  j.location_text,j.work_mode,j.job_type,j.role,j.category,j.experience_level,j.source_tags,
  j.published_at,j.status,j.freshness_checked_at,j.is_development,
  json_build_object('name','Remote OK','url',j.source_url) AS source`;
const JOIN = 'FROM app.jobs j JOIN app.companies c ON c.id=j.company_id';
export async function listJobs(search:Search) {
  return database(async (client,preview) => {
    const plan=queryPlan(search,preview);
    const count=await client.query(`SELECT count(*) ${JOIN} WHERE ${plan.where}`,plan.values);
    const total=Number(count.rows[0].count);
    const rows=await client.query(`SELECT ${SUMMARY} ${JOIN} WHERE ${plan.where} ORDER BY ${plan.order}
      LIMIT $${plan.values.length+1} OFFSET $${plan.values.length+2}`,
      [...plan.values,search.page_size,(search.page-1)*search.page_size]);
    return {data:rows.rows,pagination:{page:search.page,page_size:search.page_size,total,total_pages:Math.ceil(total/search.page_size)}};
  });
}
export async function jobDetail(id:string) {
  return database(async (client,preview) => {
    const visible = preview ? "(NOT j.is_development AND j.status IN ('active','expired')) OR (j.is_development AND j.status='unverified')" : "NOT j.is_development AND j.status IN ('active','expired')";
    const rows=await client.query(`SELECT ${SUMMARY},j.description_text,j.application_url_kind,j.application_url,j.source AS source_key,
      j.fresh_until,j.expires_at,j.updated_at,(${ACTIVE}) AS eligible
      ${JOIN} WHERE j.id=$1::uuid AND (${visible})`,[id]);
    if (!rows.rowCount) return null;
    const row=rows.rows[0];
    const eligible=Boolean(applicationDestination({source:row.source_key,application_url:row.application_url,application_url_kind:row.application_url_kind,eligible:row.eligible}));
    delete row.eligible; delete row.application_url; delete row.source_key;
    return {...row,description_text:publicDescription(row.description_text),can_apply:eligible,
      availability_message:row.is_development ? 'Development listing; availability has not been checked.' :
        eligible ? 'Source listing checked. Confirm availability and apply on Remote OK.' : 'This listing is expired or awaiting an availability recheck.'};
  });
}
export async function applicationRecord(id: string): Promise<ApplicationRecord | null> {
  return database(async client => {
    const rows = await client.query(`SELECT j.source,j.application_url,j.application_url_kind,
      (${ACTIVE}) AS eligible FROM app.jobs j
      WHERE j.id=$1::uuid AND NOT j.is_development AND j.status IN ('active','expired')`, [id]);
    return rows.rows[0] ?? null;
  });
}
export async function jobFilters() {
  return database(async (client,preview) => {
    const where=preview ? `(${ACTIVE} OR (j.is_development AND j.status='unverified'))` : ACTIVE;
    const fields = {roles:'role',categories:'category',work_modes:'work_mode',experience_levels:'experience_level',job_types:'job_type'};
    const data:Record<string,string[]>={};
    for (const [key,column] of Object.entries(fields)) {
      const rows=await client.query(`SELECT DISTINCT j.${column} AS value FROM app.jobs j WHERE ${where} ORDER BY value`);
      data[key]=rows.rows.map(r=>r.value);
    }
    return {data};
  });
}

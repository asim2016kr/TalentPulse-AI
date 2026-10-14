import Link from 'next/link';
export type Job = {id:string;title:string;company:{id:string;name:string};location_text:string;work_mode:string;job_type:string;role:string;experience_level:string;source_tags:string[];published_at:string|Date|null;freshness_checked_at:string|Date|null;source:{name:string;url:string}};
export function dateLabel(value:string|Date|null) {return value ? new Date(value).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}) : 'Date unavailable';}
export function SearchForm({q='',location=''}:{q?:string;location?:string}) {
  return <form key={q+"|"+location} action="/jobs" className="search-form" role="search"><label><span>What are you looking for?</span><input name="q" defaultValue={q} maxLength={200} placeholder="Job title, keyword or company" /></label><label><span>Where?</span><input name="location" defaultValue={location} maxLength={100} placeholder="City, country or region" /></label><button className="button" type="submit">Search jobs <span aria-hidden="true">↗</span></button></form>;
}
export function JobCard({job}:{job:Job}) {
  const tags=[job.role,job.work_mode,job.experience_level,job.job_type].filter(t=>t && !['Other','Unknown'].includes(t));
  return <article className="job-card"><div className="company-icon" aria-hidden="true">{job.company.name.slice(0,2).toUpperCase()}</div><div className="job-body"><p className="company-name">{job.company.name}</p><h3><Link href={`/jobs/${job.id}`}>{job.title}</Link></h3><p className="muted">{job.location_text || 'Location not specified'}</p><div className="tags">{[...new Set(tags)].map(t=><span key={t}>{t}</span>)}</div><p className="job-date">Posted {dateLabel(job.published_at)} · Source: {job.source.name}</p></div><Link className="card-arrow" href={`/jobs/${job.id}`} aria-label={`View ${job.title} at ${job.company.name}`}>↗</Link></article>;
}

import Link from 'next/link';
import {notFound} from 'next/navigation';
import {jobDetail} from '../../../lib/jobs';
import {validUUID} from '../../../lib/search';
import {applicationDestination} from '../../../lib/application-policy';
import {dateLabel} from '../../../components/jobs';
import {SaveButton} from '../../../components/save-button';
import {ApplyButton} from '../../../components/apply-button';

export const dynamic = 'force-dynamic';
export const metadata = {title: 'Job details'};

export default async function Detail({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  if (!validUUID(id)) notFound();
  const job = await jobDetail(id);
  if (!job) notFound();
  const sourceUrl = applicationDestination({source: 'remoteok', application_url: job.source.url,
    application_url_kind: 'source_listing', eligible: true});
  const labels = [...new Set<string>([job.work_mode, job.experience_level, job.job_type]
    .filter(v => v && !['Other', 'Unknown'].includes(v)))];

  return <main id="main" className="detail section">
    <Link href="/jobs" className="text-link">← Explore all jobs</Link>
    <div className="detail-heading">
      <p className="eyebrow">{job.company.name}</p>
      <h1>{job.title}</h1>
      <p className="muted">{job.location_text || 'Location not specified'} · {job.role}</p>
      <div className="tags">{labels.map(label => <span key={label}>{label}</span>)}</div>
    </div>
    <div className="detail-grid">
      <article className="description">
        <h2>About this opportunity</h2>
        <p className="muted">Description supplied by the source; it may be an excerpt. Visit the original listing for complete details and application instructions.</p>
        <div>{job.description_text}</div>
        {job.source_tags?.length > 0 && <section className="source-tags">
          <h3>Tags from the source</h3>
          <p className="muted">These labels come from the listing provider and may not represent required skills.</p>
          <div className="tags">{[...new Set<string>(job.source_tags)].map(tag => <span key={tag}>{tag}</span>)}</div>
        </section>}
      </article>
      <aside className="source-panel">
        <h2>At a glance</h2>
        <dl>
          <dt>Company</dt><dd>{job.company.name}</dd>
          <dt>Role category</dt><dd>{job.category}</dd>
          <dt>Posted</dt><dd>{dateLabel(job.published_at)}</dd>
          <dt>Source last checked</dt><dd>{dateLabel(job.freshness_checked_at)}</dd>
          <dt>Source</dt><dd>{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noopener noreferrer">{job.source.name} ↗</a> : job.source.name}</dd>
        </dl>
        <p className={job.can_apply ? 'availability' : 'notice'}>{job.availability_message}</p>
        <SaveButton key={id} jobId={id} available={job.can_apply}/>
        <ApplyButton key={id+String(job.can_apply)} jobId={id} available={job.can_apply}/>
        {!job.can_apply && <Link className="clear" href="/jobs">Find other opportunities</Link>}
      </aside>
    </div>
  </main>;
}

export type ApplicationRecord = {
  source: string;
  application_url: string;
  application_url_kind: string;
  eligible: boolean;
};

// This MVP has one reviewed source adapter. Employer destinations require a
// separate reviewed adapter, not a wildcard hostname or a caller-supplied URL.
export function applicationDestination(record: ApplicationRecord): string | null {
  if (!record.eligible || record.source !== 'remoteok' || record.application_url_kind !== 'source_listing') return null;
  try {
    const raw = record.application_url;
    if (typeof raw !== 'string' || raw !== raw.trim() || /[\s\\]/.test(raw)) return null;
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.hostname !== 'remoteok.com' || url.port ||
        url.username || url.password || url.search || url.hash ||
        !/^\/remote-jobs\/[a-zA-Z0-9-]+$/.test(url.pathname)) return null;
    return url.href;
  } catch { return null; }
}

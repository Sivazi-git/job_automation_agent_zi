'use client';

import Link from 'next/link';
import { type JobSummary } from '@/lib/api';

const COLUMNS: { label: string; value: string; accent: string }[] = [
  { label: 'New',      value: 'new',     accent: 'border-slate-600' },
  { label: 'Queued',   value: 'queued',  accent: 'border-indigo-600' },
  { label: 'Applied',  value: 'applied', accent: 'border-emerald-600' },
  { label: 'Filtered', value: 'skipped', accent: 'border-yellow-600' },
  { label: 'Failed',   value: 'failed',  accent: 'border-red-700' },
];

const ATS_COLOR = (score: number | null) => {
  if (score == null) return 'text-slate-500';
  if (score >= 75) return 'text-emerald-400';
  if (score >= 60) return 'text-yellow-400';
  return 'text-red-400';
};

const sourceColors: Record<string, string> = {
  linkedin:      'bg-blue-900/40 text-blue-300',
  indeed:        'bg-purple-900/40 text-purple-300',
  glassdoor:     'bg-emerald-900/40 text-emerald-300',
  zip_recruiter: 'bg-orange-900/40 text-orange-300',
};

interface Props {
  jobs: JobSummary[];
}

export default function JobsBoard({ jobs }: Props) {
  const grouped = Object.fromEntries(
    COLUMNS.map((col) => [col.value, jobs.filter((j) => j.status === col.value)])
  );

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 min-h-0">
      {COLUMNS.map((col) => {
        const colJobs = grouped[col.value] ?? [];
        return (
          <div
            key={col.value}
            className={`shrink-0 w-64 flex flex-col rounded-xl border-t-2 bg-slate-900 border border-slate-800 ${col.accent}`}
          >
            {/* Column header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <span className="text-sm font-semibold text-slate-200">{col.label}</span>
              <span className="text-xs font-medium bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full">
                {colJobs.length}
              </span>
            </div>

            {/* Cards */}
            <div className="flex-1 overflow-y-auto p-2 space-y-2 max-h-[calc(100vh-240px)]">
              {colJobs.length === 0 && (
                <p className="text-xs text-slate-600 text-center py-6">No jobs</p>
              )}
              {colJobs.map((job) => {
                const srcClass = job.source
                  ? (sourceColors[job.source.toLowerCase()] ?? 'bg-slate-700/40 text-slate-300')
                  : null;
                return (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="block bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg p-3 space-y-2 transition-colors"
                  >
                    <p className="text-sm font-medium text-slate-100 leading-snug line-clamp-2">
                      {job.title}
                    </p>
                    <p className="text-xs text-slate-400">{job.company}</p>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {job.ats_score != null && (
                        <span className={`text-xs font-semibold tabular-nums ${ATS_COLOR(job.ats_score)}`}>
                          {Math.round(job.ats_score)}
                        </span>
                      )}
                      {srcClass && job.source && (
                        <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${srcClass}`}>
                          {job.source.replace('_', ' ')}
                        </span>
                      )}
                      {job.created_at && (
                        <span className="text-xs text-slate-600 ml-auto">
                          {new Date(job.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </span>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

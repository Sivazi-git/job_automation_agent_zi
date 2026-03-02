'use client';

import { useRouter } from 'next/navigation';
import { ExternalLink } from 'lucide-react';
import StatusBadge from './StatusBadge';
import type { JobSummary } from '@/lib/api';

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null)
    return <span className="text-slate-600 text-sm">—</span>;

  const colorClass =
    score >= 70
      ? 'text-green-400'
      : score >= 50
      ? 'text-yellow-400'
      : 'text-red-400';

  return (
    <span className={`font-semibold tabular-nums text-sm ${colorClass}`}>
      {Math.round(score)}
    </span>
  );
}

const sourceColors: Record<string, string> = {
  linkedin: 'bg-blue-900/40 text-blue-300',
  indeed: 'bg-purple-900/40 text-purple-300',
  glassdoor: 'bg-emerald-900/40 text-emerald-300',
  zip_recruiter: 'bg-orange-900/40 text-orange-300',
};

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return <span className="text-slate-600 text-sm">—</span>;
  const cls = sourceColors[source.toLowerCase()] ?? 'bg-slate-700 text-slate-400';
  return (
    <span className={`px-2 py-0.5 text-xs rounded font-medium capitalize ${cls}`}>
      {source.replace('_', ' ')}
    </span>
  );
}

interface JobsTableProps {
  jobs: JobSummary[];
}

export default function JobsTable({ jobs }: JobsTableProps) {
  const router = useRouter();

  if (jobs.length === 0) {
    return (
      <div className="py-16 text-center text-slate-500 bg-slate-800/30 rounded-xl border border-slate-700">
        <p className="text-base font-medium text-slate-400">No jobs found</p>
        <p className="text-sm mt-1">
          Run the pipeline to scrape and score jobs.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 bg-slate-800/60">
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3">
              Title
            </th>
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3">
              Company
            </th>
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3 hidden md:table-cell">
              Location
            </th>
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3 hidden lg:table-cell">
              Source
            </th>
            <th className="text-right text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3">
              ATS
            </th>
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3">
              Status
            </th>
            <th className="text-left text-xs text-slate-400 font-medium uppercase tracking-wide px-4 py-3 hidden xl:table-cell">
              Date
            </th>
            <th className="px-4 py-3 w-10" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => router.push(`/jobs/${job.id}`)}
              className="hover:bg-slate-700/30 cursor-pointer transition-colors"
            >
              <td className="px-4 py-3">
                <p className="font-medium text-slate-100 truncate max-w-[220px]">
                  {job.title}
                </p>
              </td>
              <td className="px-4 py-3 text-slate-300 truncate max-w-[140px]">
                {job.company}
              </td>
              <td className="px-4 py-3 text-slate-400 text-xs hidden md:table-cell truncate max-w-[120px]">
                {job.location ?? '—'}
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                <SourceBadge source={job.source} />
              </td>
              <td className="px-4 py-3 text-right">
                <ScoreBadge score={job.ats_score} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={job.status} />
              </td>
              <td className="px-4 py-3 text-slate-500 text-xs hidden xl:table-cell">
                {job.created_at
                  ? new Date(job.created_at).toLocaleDateString()
                  : '—'}
              </td>
              <td className="px-4 py-3">
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-slate-600 hover:text-indigo-400 transition-colors"
                  title="Open job listing"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

'use client';

import { useEffect, useState, useCallback } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw, LayoutList, LayoutGrid } from 'lucide-react';
import JobsTable from '@/components/JobsTable';
import JobsBoard from '@/components/JobsBoard';
import { fetchJobs, type JobSummary } from '@/lib/api';

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'New', value: 'new' },
  { label: 'Queued', value: 'queued' },
  { label: 'Applied', value: 'applied' },
  { label: 'Filtered', value: 'skipped' },
  { label: 'Failed', value: 'failed' },
];

const PAGE_SIZE = 25;

type ViewMode = 'table' | 'board';

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('table');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJobs({
        status: status === 'all' ? undefined : status,
        limit: view === 'board' ? 200 : PAGE_SIZE,
        offset: view === 'board' ? 0 : page * PAGE_SIZE,
        sort: 'ats_score_desc',
      });
      setJobs(data.jobs);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [status, page, view]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function handleTabChange(value: string) {
    setStatus(value);
    setPage(0);
  }

  function handleViewChange(v: ViewMode) {
    setView(v);
    setPage(0);
  }

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Jobs</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {total.toLocaleString()} jobs total
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center gap-0.5 p-1 bg-slate-800 border border-slate-700 rounded-lg">
            <button
              onClick={() => handleViewChange('table')}
              title="Table view"
              className={`p-1.5 rounded transition-colors ${
                view === 'table'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutList className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleViewChange('board')}
              title="Board view"
              className={`p-1.5 rounded transition-colors ${
                view === 'board'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
          <button
            onClick={load}
            className="p-2 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 p-1 bg-slate-800 rounded-lg w-fit flex-wrap">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => handleTabChange(tab.value)}
            className={`px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${
              status === tab.value
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
        </div>
      ) : view === 'board' ? (
        <JobsBoard jobs={jobs} />
      ) : (
        <JobsTable jobs={jobs} />
      )}

      {/* Pagination — table view only */}
      {!loading && view === 'table' && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>
            Showing {page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, total)} of{' '}
            {total.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 tabular-nums">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() =>
                setPage((p) => Math.min(totalPages - 1, p + 1))
              }
              disabled={page >= totalPages - 1}
              className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

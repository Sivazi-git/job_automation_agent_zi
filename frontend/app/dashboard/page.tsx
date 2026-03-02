'use client';

import { useEffect, useState } from 'react';
import {
  Database,
  CheckCircle2,
  Filter,
  Send,
  XCircle,
  Clock,
} from 'lucide-react';
import StatsCard from '@/components/StatsCard';
import JobsTable from '@/components/JobsTable';
import {
  fetchStats,
  fetchJobs,
  fetchPipelineStatus,
  type StatsData,
  type JobSummary,
  type PipelineStatus,
} from '@/lib/api';

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobSummary[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [statsData, jobsData, pipeData] = await Promise.all([
          fetchStats(),
          fetchJobs({ limit: 10, sort: 'created_at_desc' }),
          fetchPipelineStatus(),
        ]);
        setStats(statsData);
        setRecentJobs(jobsData.jobs);
        setPipelineStatus(pipeData);
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'Failed to connect to backend'
        );
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-5">
          <p className="text-sm font-semibold text-red-400 mb-1">
            Connection Error
          </p>
          <p className="text-sm text-red-300/70">{error}</p>
          <p className="text-xs text-slate-500 mt-3">
            Make sure the backend is running:{' '}
            <code className="text-slate-400">
              uvicorn app.main:app --reload --port 8000
            </code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-7">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Job automation pipeline overview
          </p>
        </div>

        {pipelineStatus && (
          <div className="flex items-center gap-2 text-sm">
            {pipelineStatus.status === 'in_progress' ? (
              <span className="flex items-center gap-1.5 text-indigo-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                Pipeline Running
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-green-400 font-medium">
                <span className="w-2 h-2 rounded-full bg-green-400" />
                Pipeline Idle
              </span>
            )}
            {pipelineStatus.last_run_at && (
              <span className="text-slate-500">
                · Last:{' '}
                {new Date(pipelineStatus.last_run_at).toLocaleDateString()}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Stats grid */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
          <StatsCard
            label="Total Scraped"
            value={stats.total}
            icon={Database}
            color="text-slate-300"
          />
          <StatsCard
            label="ATS Passed"
            value={stats.passed_ats}
            icon={CheckCircle2}
            color="text-green-400"
          />
          <StatsCard
            label="Filtered Out"
            value={stats.filtered}
            icon={Filter}
            color="text-yellow-400"
          />
          <StatsCard
            label="Queued"
            value={stats.queued}
            icon={Clock}
            color="text-indigo-400"
          />
          <StatsCard
            label="Applied"
            value={stats.applied}
            icon={Send}
            color="text-blue-400"
          />
          <StatsCard
            label="Failed"
            value={stats.failed}
            icon={XCircle}
            color="text-red-400"
          />
        </div>
      )}

      {/* Recent jobs */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-100">
            Recent Jobs
          </h2>
          <a
            href="/jobs"
            className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            View all →
          </a>
        </div>
        <JobsTable jobs={recentJobs} />
      </div>
    </div>
  );
}

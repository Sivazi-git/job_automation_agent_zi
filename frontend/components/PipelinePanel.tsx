'use client';

import { useState, useEffect, useCallback } from 'react';
import { Play, Loader2, CheckCircle2, XCircle, Circle } from 'lucide-react';
import {
  triggerPipeline,
  fetchPipelineStatus,
  type PipelineStatus,
  type PipelineRun,
} from '@/lib/api';

// ── Run History Log ────────────────────────────────────────────────────────────

function RunStatusIcon({ status }: { status: PipelineRun['status'] }) {
  if (status === 'running')
    return <Loader2 className="w-4 h-4 text-indigo-400 animate-spin shrink-0" />;
  if (status === 'completed')
    return <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />;
  return <XCircle className="w-4 h-4 text-red-400 shrink-0" />;
}

function RunHistoryLog({ runs }: { runs: PipelineRun[] }) {
  if (runs.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-4 text-center">
        No pipeline runs yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {runs.map((run, i) => (
        <div
          key={i}
          className="flex items-start gap-3 p-3.5 rounded-lg bg-slate-800/60 border border-slate-700"
        >
          <div className="mt-0.5">
            <RunStatusIcon status={run.status} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-slate-200 truncate">
                {run.search_term || '(no search term)'}
                {run.location ? (
                  <span className="text-slate-500 font-normal">
                    {' '}
                    · {run.location}
                  </span>
                ) : null}
              </p>
              <span className="text-xs text-slate-500 shrink-0 whitespace-nowrap">
                {new Date(run.started_at).toLocaleString()}
              </span>
            </div>
            {run.status !== 'running' && (
              <p className="text-xs text-slate-500 mt-0.5">
                {run.jobs_found} found · {run.passed} passed · {run.filtered}{' '}
                filtered · {run.failed} failed
                {run.should_apply ? ' · auto-apply on' : ''}
              </p>
            )}
            {run.error && (
              <p className="text-xs text-red-400 mt-0.5 truncate">
                {run.error}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function PipelinePanel() {
  const [searchTerm, setSearchTerm] = useState('');
  const [location, setLocation] = useState('');
  const [shouldApply, setShouldApply] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(
    null
  );

  const loadStatus = useCallback(async () => {
    try {
      const status = await fetchPipelineStatus();
      setPipelineStatus(status);
    } catch {
      // silently ignore polling errors
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  async function handleRun() {
    if (!searchTerm.trim()) {
      setFormError('Search term is required.');
      return;
    }
    setFormError(null);
    setLoading(true);
    try {
      const result = await triggerPipeline({
        search_term: searchTerm.trim(),
        location: location.trim(),
        should_apply: shouldApply,
      });
      if (result.error) {
        setFormError(result.error);
      } else {
        await loadStatus();
      }
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  const isRunning = pipelineStatus?.status === 'in_progress';

  return (
    <div className="space-y-6">
      {/* Status Indicator */}
      <div className="flex items-center gap-3 p-4 rounded-xl bg-slate-800 border border-slate-700">
        {isRunning ? (
          <>
            <Loader2 className="w-5 h-5 text-indigo-400 animate-spin shrink-0" />
            <div>
              <p className="text-sm font-semibold text-slate-100">
                Pipeline Running
              </p>
              {pipelineStatus?.current_search && (
                <p className="text-xs text-slate-400 mt-0.5">
                  Searching: &ldquo;{pipelineStatus.current_search}&rdquo;
                </p>
              )}
            </div>
          </>
        ) : (
          <>
            <Circle className="w-2.5 h-2.5 text-green-400 fill-green-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-slate-100">
                Pipeline Idle
              </p>
              {pipelineStatus?.last_run_at && (
                <p className="text-xs text-slate-400 mt-0.5">
                  Last run:{' '}
                  {new Date(pipelineStatus.last_run_at).toLocaleString()}
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* Run Form */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
        <h2 className="text-base font-semibold text-slate-100">
          New Pipeline Run
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
              Search Term
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="e.g. Software Engineer"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
              Location
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Remote, New York"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
            />
          </div>
        </div>

        {/* Auto-Apply Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-slate-900/60 border border-slate-700">
          <div>
            <p className="text-sm font-medium text-slate-200">Auto-Apply</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Automatically submit applications for matching jobs
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShouldApply((v) => !v)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
              shouldApply ? 'bg-indigo-600' : 'bg-slate-600'
            }`}
            aria-checked={shouldApply}
            role="switch"
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                shouldApply ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {formError && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <XCircle className="w-4 h-4 shrink-0" />
            {formError}
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={loading || isRunning}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg text-sm font-semibold transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Starting…
            </>
          ) : isRunning ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Pipeline Running…
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Run Pipeline
            </>
          )}
        </button>
      </div>

      {/* Recent Runs */}
      <div>
        <h2 className="text-base font-semibold text-slate-100 mb-3">
          Recent Runs
        </h2>
        <RunHistoryLog runs={pipelineStatus?.runs ?? []} />
      </div>
    </div>
  );
}

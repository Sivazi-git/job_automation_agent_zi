'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Play, Square, Loader2, CheckCircle2, XCircle, Circle, Terminal } from 'lucide-react';
import {
  triggerPipeline,
  fetchPipelineStatus,
  stopPipeline,
  PIPELINE_LOGS_URL,
  type PipelineStatus,
  type PipelineRun,
  type LogEntry,
} from '@/lib/api';
import { getToken } from '@/lib/auth';
import { cn } from '@/lib/utils';

// ── Run History ───────────────────────────────────────────────────────────────

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
      <p className="text-sm text-slate-500 py-4 text-center">No pipeline runs yet.</p>
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
                {run.location && (
                  <span className="text-slate-500 font-normal"> · {run.location}</span>
                )}
              </p>
              <span className="text-xs text-slate-500 shrink-0 whitespace-nowrap">
                {new Date(run.started_at).toLocaleString()}
              </span>
            </div>
            {run.status !== 'running' && (
              <p className="text-xs text-slate-500 mt-0.5">
                {run.jobs_found} found · {run.passed} passed · {run.filtered} filtered ·{' '}
                {run.failed} failed
                {run.should_apply ? ' · auto-apply on' : ''}
              </p>
            )}
            {run.error && (
              <p className="text-xs text-red-400 mt-0.5 truncate">{run.error}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Live Log Terminal ──────────────────────────────────────────────────────────

const LEVEL_COLOR: Record<string, string> = {
  error: 'text-red-400',
  warn:  'text-amber-300',
  info:  'text-green-400',
};

const LEVEL_PREFIX: Record<string, string> = {
  error: '[ERR]',
  warn:  '[WRN]',
  info:  '[INF]',
};

function LogLine({ entry }: { entry: LogEntry }) {
  const time = new Date(entry.ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const color = LEVEL_COLOR[entry.level] ?? 'text-green-400';
  const prefix = LEVEL_PREFIX[entry.level] ?? '[INF]';
  return (
    <div className="flex gap-2 font-mono text-xs leading-5 select-text">
      <span className="text-zinc-600 shrink-0 tabular-nums">{time}</span>
      <span className={cn('shrink-0', color)}>{prefix}</span>
      <span className={cn(color, 'break-all')}>{entry.message}</span>
    </div>
  );
}

function LiveLogs({ isRunning, onDone }: { isRunning: boolean; onDone?: () => void }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>(isRunning ? 'running' : 'idle');
  const bottomRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll only when user hasn't scrolled up
  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: 'instant' });
    }
  }, [logs, autoScroll]);

  function handleScroll() {
    const el = bodyRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }

  // Open SSE when pipeline starts, keep logs after it stops
  useEffect(() => {
    if (!isRunning) return;

    const token = getToken();
    if (!token) return;

    setLogs([]);
    setPhase('running');
    setAutoScroll(true);

    const es = new EventSource(`${PIPELINE_LOGS_URL}?token=${encodeURIComponent(token)}`);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as LogEntry & { done?: boolean };
        if (data.done) {
          setPhase('done');
          es.close();
          onDone?.();
          return;
        }
        setLogs((prev) => [...prev.slice(-999), data]);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setPhase('done');
      es.close();
    };

    return () => es.close();
  }, [isRunning]);

  return (
    <div className="rounded-xl overflow-hidden border border-zinc-700 shadow-lg">
      {/* Terminal title bar */}
      <div className="flex items-center gap-2 px-4 py-2 bg-zinc-800 border-b border-zinc-700">
        {/* Traffic lights */}
        <span className="w-3 h-3 rounded-full bg-red-500/80" />
        <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
        <span className="w-3 h-3 rounded-full bg-green-500/80" />
        <span className="mx-auto flex items-center gap-2 text-xs text-zinc-400 font-mono">
          <Terminal className="w-3 h-3" />
          pipeline — logs
        </span>
        {phase === 'running' && (
          <span className="flex items-center gap-1 text-xs text-indigo-400 font-mono">
            <Loader2 className="w-3 h-3 animate-spin" />
            live
          </span>
        )}
        {phase === 'done' && (
          <span className="text-xs text-green-400 font-mono">done</span>
        )}
        {phase === 'idle' && (
          <span className="text-xs text-zinc-600 font-mono">idle</span>
        )}
      </div>

      {/* Log body */}
      <div
        ref={bodyRef}
        onScroll={handleScroll}
        className="bg-zinc-950 p-4 h-72 overflow-y-auto space-y-px"
      >
        {logs.length === 0 && phase === 'idle' && (
          <p className="font-mono text-xs text-zinc-600">
            ~ Run the pipeline to see live output here.
          </p>
        )}
        {logs.length === 0 && phase === 'running' && (
          <p className="font-mono text-xs text-zinc-600 animate-pulse">
            ~ Connecting…
          </p>
        )}
        {logs.map((entry, i) => (
          <LogLine key={i} entry={entry} />
        ))}
        {phase === 'running' && logs.length > 0 && (
          <span className="inline-block w-1.5 h-3.5 bg-green-400 animate-pulse ml-0.5 align-middle" />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Footer */}
      {!autoScroll && (
        <div className="flex justify-end bg-zinc-900 border-t border-zinc-800 px-4 py-1.5">
          <button
            onClick={() => {
              setAutoScroll(true);
              bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="text-xs text-zinc-400 hover:text-zinc-200 font-mono transition-colors"
          >
            ↓ scroll to bottom
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function PipelinePanel() {
  const [searchTerm, setSearchTerm] = useState('');
  const [location, setLocation] = useState('');
  const [shouldApply, setShouldApply] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);

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
    const interval = setInterval(loadStatus, 4000);
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

  async function handleStop() {
    setStopping(true);
    setFormError(null);
    try {
      await stopPipeline();
      await loadStatus();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Stop failed');
    } finally {
      setStopping(false);
    }
  }

  const isRunning = pipelineStatus?.status === 'in_progress';
  const runsRemaining = pipelineStatus?.runs_remaining ?? 3;
  const dailyLimit = pipelineStatus?.daily_limit ?? 3;
  const limitReached = runsRemaining === 0;

  return (
    <div className="space-y-6">
      {/* Status Indicator */}
      <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-slate-800 border border-slate-700">
        <div className="flex items-center gap-3">
          {isRunning ? (
            <Loader2 className="w-5 h-5 text-indigo-400 animate-spin shrink-0" />
          ) : (
            <Circle className="w-2.5 h-2.5 text-green-400 fill-green-400 shrink-0" />
          )}
          <div>
            <p className="text-sm font-semibold text-slate-100">
              {isRunning ? 'Pipeline Running' : 'Pipeline Idle'}
            </p>
            {isRunning && pipelineStatus?.current_search && (
              <p className="text-xs text-slate-400 mt-0.5">
                Searching: &ldquo;{pipelineStatus.current_search}&rdquo;
              </p>
            )}
            {!isRunning && pipelineStatus?.last_run_at && (
              <p className="text-xs text-slate-400 mt-0.5">
                Last run: {new Date(pipelineStatus.last_run_at).toLocaleString()}
              </p>
            )}
          </div>
        </div>

        {/* Daily run counter */}
        {!isRunning && (
          <div className="flex items-center gap-1.5">
            {Array.from({ length: dailyLimit }).map((_, i) => (
              <span
                key={i}
                className={cn(
                  'w-2.5 h-2.5 rounded-full',
                  i < runsRemaining ? 'bg-indigo-500' : 'bg-slate-600'
                )}
              />
            ))}
            <span className={cn('text-xs ml-1', limitReached ? 'text-red-400' : 'text-slate-400')}>
              {limitReached ? 'Limit reached' : `${runsRemaining}/${dailyLimit} runs left`}
            </span>
          </div>
        )}

        {/* Stop button — only when running */}
        {isRunning && (
          <button
            onClick={handleStop}
            disabled={stopping}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-red-700/60 text-red-400 hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {stopping ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Square className="w-3.5 h-3.5 fill-current" />
            )}
            {stopping ? 'Stopping…' : 'Stop'}
          </button>
        )}
      </div>

      {/* Live Logs */}
      <LiveLogs isRunning={isRunning} onDone={loadStatus} />

      {/* Run Form */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
        <h2 className="text-base font-semibold text-slate-100">New Pipeline Run</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
              Search Term
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !loading && !isRunning) handleRun(); }}
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
              onKeyDown={(e) => { if (e.key === 'Enter' && !loading && !isRunning) handleRun(); }}
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

        {limitReached && (
          <div className="flex items-center gap-2 text-sm text-amber-400 bg-amber-900/20 border border-amber-800/40 rounded-lg px-3 py-2.5">
            <XCircle className="w-4 h-4 shrink-0" />
            Daily limit reached ({dailyLimit} runs/day). Resets at midnight UTC.
          </div>
        )}

        {formError && !limitReached && (
          <div className="flex items-center gap-2 text-sm text-red-400">
            <XCircle className="w-4 h-4 shrink-0" />
            {formError}
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={loading || isRunning || limitReached}
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
        <h2 className="text-base font-semibold text-slate-100 mb-3">Recent Runs</h2>
        <RunHistoryLog runs={pipelineStatus?.runs ?? []} />
      </div>
    </div>
  );
}

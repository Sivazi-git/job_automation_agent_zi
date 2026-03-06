'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, ExternalLink, FileText, Calendar, Download,
  RefreshCw, Send, ChevronDown, ChevronUp,
} from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import ATSBreakdown from '@/components/ATSBreakdown';
import KeywordTags from '@/components/KeywordTags';
import ScreeningForm from '@/components/ScreeningForm';
import {
  fetchJob, generateJobResume, getJobResume, applyToJob,
  type JobDetail, type ResumeRecord,
} from '@/lib/api';
import JobDescription from '@/components/JobDescription';

const sourceColors: Record<string, string> = {
  linkedin:
    'bg-blue-900/40 text-blue-300 border border-blue-700/40',
  indeed:
    'bg-purple-900/40 text-purple-300 border border-purple-700/40',
  glassdoor:
    'bg-emerald-900/40 text-emerald-300 border border-emerald-700/40',
  zip_recruiter:
    'bg-orange-900/40 text-orange-300 border border-orange-700/40',
};

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Resume state
  const [resume, setResume] = useState<ResumeRecord | null>(null);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [resumeExpanded, setResumeExpanded] = useState(false);

  // Apply state
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  const loadJob = useCallback(async () => {
    try {
      const data = await fetchJob(id);
      setJob(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load job');
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadResume = useCallback(async () => {
    try {
      const r = await getJobResume(id);
      setResume(r);
    } catch {
      // 404 is fine — no resume yet
    }
  }, [id]);

  useEffect(() => {
    loadJob();
    loadResume();
  }, [loadJob, loadResume]);

  async function handleGenerateResume() {
    setResumeLoading(true);
    setResumeError(null);
    try {
      const r = await generateJobResume(id);
      setResume(r);
    } catch (e) {
      setResumeError(e instanceof Error ? e.message : 'Failed to generate resume');
    } finally {
      setResumeLoading(false);
    }
  }

  async function handleApply() {
    setApplying(true);
    setApplyError(null);
    try {
      await applyToJob(id);
      // Reload job after a short delay to reflect queued status
      setTimeout(() => loadJob(), 1500);
    } catch (e) {
      setApplyError(e instanceof Error ? e.message : 'Apply failed');
    } finally {
      setApplying(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="p-6">
        <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-5">
          <p className="text-sm font-semibold text-red-400">Error</p>
          <p className="text-sm text-red-300/70 mt-1">{error ?? 'Job not found'}</p>
        </div>
      </div>
    );
  }

  const srcColorClass = job.source
    ? (sourceColors[job.source.toLowerCase()] ??
      'bg-slate-700 text-slate-300 border border-slate-600')
    : null;

  return (
    <div className="p-6 space-y-5 max-w-4xl">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Jobs
      </button>

      {/* Header Card */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          {/* Left: title + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2.5">
              {job.source && srcColorClass && (
                <span
                  className={`px-2 py-0.5 text-xs rounded font-medium capitalize ${srcColorClass}`}
                >
                  {job.source.replace('_', ' ')}
                </span>
              )}
              <StatusBadge status={job.status} />
              {job.applied_at && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Calendar className="w-3 h-3" />
                  Applied {new Date(job.applied_at).toLocaleDateString()}
                </span>
              )}
            </div>

            <h1 className="text-xl font-bold text-slate-100 leading-snug">
              {job.title}
            </h1>
            <p className="text-slate-400 mt-1">
              {job.company}
              {job.location && (
                <span className="text-slate-500"> · {job.location}</span>
              )}
            </p>
            {job.posted_at && (
              <p className="text-xs text-slate-600 mt-1.5">
                Posted {new Date(job.posted_at).toLocaleDateString()}
              </p>
            )}
            {job.created_at && (
              <p className="text-xs text-slate-600 mt-0.5">
                Scraped {new Date(job.created_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Right: action buttons */}
          <div className="flex gap-2 shrink-0">
            {job.resume_url && (
              <a
                href={job.resume_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-2 text-sm bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors"
              >
                <FileText className="w-4 h-4" />
                Resume
              </a>
            )}
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors font-medium"
            >
              <ExternalLink className="w-4 h-4" />
              View Job
            </a>
          </div>
        </div>
      </div>

      {/* ATS Analysis */}
      {job.ats_score != null && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h2 className="text-base font-semibold text-slate-100 mb-5">
            ATS Analysis
          </h2>
          <ATSBreakdown score={job.ats_score} breakdown={job.ats_breakdown} />
        </div>
      )}

      {/* Keywords */}
      {((job.ats_matched_keywords?.length ?? 0) > 0 ||
        (job.ats_missing_keywords?.length ?? 0) > 0) && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h2 className="text-base font-semibold text-slate-100 mb-4">
            Keywords
          </h2>
          <KeywordTags
            matched={job.ats_matched_keywords ?? []}
            missing={job.ats_missing_keywords ?? []}
          />
        </div>
      )}

      {/* Resume */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">Tailored Resume</h2>
          {resume && (
            <button
              onClick={handleGenerateResume}
              disabled={resumeLoading}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${resumeLoading ? 'animate-spin' : ''}`} />
              Regenerate
            </button>
          )}
        </div>

        {resumeError && (
          <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-3 text-red-400 text-sm">
            {resumeError}
          </div>
        )}

        {!resume && !resumeLoading && (
          <button
            onClick={handleGenerateResume}
            disabled={resumeLoading}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
          >
            Generate Resume
          </button>
        )}

        {resumeLoading && !resume && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-indigo-500" />
            Generating tailored resume…
          </div>
        )}

        {resume && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500">
                Generated {resume.created_at ? new Date(resume.created_at).toLocaleDateString() : '—'}
              </p>
              {resume.file_url && (
                <a
                  href={resume.file_url}
                  download
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download PDF
                </a>
              )}
            </div>

            {resume.tailored_content && (
              <div>
                <button
                  onClick={() => setResumeExpanded((v) => !v)}
                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {resumeExpanded ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                  {resumeExpanded ? 'Hide' : 'Preview'} tailored content
                </button>
                {resumeExpanded && (
                  <pre className="mt-2 p-3 rounded-lg bg-slate-900 text-xs text-slate-400 overflow-x-auto max-h-64 overflow-y-auto">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(resume.tailored_content), null, 2);
                      } catch {
                        return resume.tailored_content;
                      }
                    })()}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Apply */}
      {job.status !== 'applied' && resume && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-3">
          <h2 className="text-base font-semibold text-slate-100">Apply</h2>
          {applyError && (
            <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-3 text-red-400 text-sm">
              {applyError}
            </div>
          )}
          {job.apply_status_detail && (
            <p className="text-xs text-slate-500">{job.apply_status_detail}</p>
          )}
          <button
            onClick={handleApply}
            disabled={applying || job.status === 'queued'}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
          >
            <Send className="w-4 h-4" />
            {applying
              ? 'Starting…'
              : job.status === 'queued'
              ? 'Applying…'
              : 'Apply Now'}
          </button>
        </div>
      )}

      {/* Screening review */}
      {job.status === 'needs_review' && job.screening_questions && job.screening_questions.length > 0 && (
        <div className="bg-slate-800 border border-amber-700/40 rounded-xl p-6 space-y-4">
          <div>
            <h2 className="text-base font-semibold text-amber-300">Screening Questions — Review Required</h2>
            <p className="text-xs text-slate-500 mt-1">
              Claude drafted answers below. Highlighted questions have low confidence — please review before submitting.
            </p>
          </div>
          <ScreeningForm
            jobId={id}
            questions={job.screening_questions}
            onSubmit={() => {
              loadJob();
            }}
          />
        </div>
      )}

      {/* Job Description */}
      {job.description && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h2 className="text-base font-semibold text-slate-100 mb-4">
            Job Description
          </h2>
          <div className="max-h-[600px] overflow-y-auto pr-2">
            <JobDescription text={job.description} />
          </div>
        </div>
      )}
    </div>
  );
}

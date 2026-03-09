import { getToken, clearToken } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  target_role: string | null;
  target_location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  master_resume_url: string | null;
  ats_threshold: number;
  daily_limit: number;
  onboarding_complete: boolean;
  created_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface StatsData {
  total: number;
  passed_ats: number;
  filtered: number;
  applied: number;
  failed: number;
  queued: number;
  needs_review: number;
}

export interface JobSummary {
  id: string;
  title: string;
  company: string;
  location: string | null;
  source: string | null;
  status: string;
  ats_score: number | null;
  url: string;
  created_at: string | null;
}

export interface ATSBreakdownData {
  skills_score: number;
  experience_score: number;
  title_score: number;
  keywords_score: number;
  final_score: number;
  reasoning?: string;
}

export interface ScreeningQuestion {
  question: string;
  claude_answer: string;
  confidence: number;
  needs_review: boolean;
}

export interface ResumeRecord {
  resume_id: string;
  file_url: string;
  tailored_content: string;
  created_at: string | null;
}

export interface ApplyStatusResponse {
  status: string;
  message?: string;
}

export interface JobDetail extends JobSummary {
  description: string | null;
  ats_breakdown: ATSBreakdownData | null;
  ats_matched_keywords: string[] | null;
  ats_missing_keywords: string[] | null;
  posted_at: string | null;
  resume_url: string | null;
  applied_at: string | null;
  screening_questions: ScreeningQuestion[] | null;
  apply_status_detail: string | null;
}

export interface JobsResponse {
  total: number;
  jobs: JobSummary[];
}

export interface PipelineRun {
  started_at: string;
  search_term: string;
  location: string;
  should_apply: boolean;
  jobs_found: number;
  passed: number;
  filtered: number;
  failed: number;
  status: 'running' | 'completed' | 'failed';
  error?: string;
}

export interface PipelineStatus {
  status: 'idle' | 'in_progress';
  last_run_at: string | null;
  processed: number;
  current_search: string | null;
  runs: PipelineRun[];
  runs_today: number;
  runs_remaining: number;
  daily_limit: number;
}

export interface ResumePreview {
  name: string;
  email: string;
  skills_count: number;
  experience_count: number;
  parsed_data: Record<string, unknown>;
}

// ── Fetch helper ──────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Auth API functions ─────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<AuthResponse> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<AuthResponse>;
}

export async function register(formData: FormData): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<AuthResponse>;
}

export const getMe = (): Promise<User> =>
  apiFetch<User>('/api/auth/me');

export const updateProfile = (data: Partial<User>): Promise<User> =>
  apiFetch<User>('/api/auth/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

export async function uploadResume(file: File): Promise<User> {
  const fd = new FormData();
  fd.append('resume_file', file);
  return apiFetch<User>('/api/auth/upload-resume', { method: 'POST', body: fd });
}

export async function uploadResumePreview(file: File): Promise<ResumePreview> {
  const fd = new FormData();
  fd.append('resume_file', file);
  // Preview endpoint doesn't need auth
  const res = await fetch(`${API_BASE}/api/auth/upload-resume-preview`, {
    method: 'POST',
    body: fd,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<ResumePreview>;
}

// ── API functions ─────────────────────────────────────────────────────────────

export const fetchStats = (): Promise<StatsData> =>
  apiFetch<StatsData>('/api/stats');

export function fetchJobs(params?: {
  status?: string;
  limit?: number;
  offset?: number;
  sort?: string;
}): Promise<JobsResponse> {
  const sp = new URLSearchParams();
  if (params?.status && params.status !== 'all') sp.set('status', params.status);
  if (params?.limit != null) sp.set('limit', String(params.limit));
  if (params?.offset != null) sp.set('offset', String(params.offset));
  if (params?.sort) sp.set('sort', params.sort);
  const qs = sp.toString();
  return apiFetch<JobsResponse>(`/api/jobs${qs ? `?${qs}` : ''}`);
}

export const fetchJob = (id: string): Promise<JobDetail> =>
  apiFetch<JobDetail>(`/api/jobs/${id}`);

export function triggerPipeline(payload: {
  search_term: string;
  location: string;
  should_apply: boolean;
}): Promise<{ status: string; message?: string; error?: string }> {
  return apiFetch('/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export const fetchPipelineStatus = (): Promise<PipelineStatus> =>
  apiFetch<PipelineStatus>('/api/pipeline/status');

export const stopPipeline = (): Promise<{ status: string; message: string }> =>
  apiFetch('/api/pipeline/stop', { method: 'POST' });

export interface LogEntry {
  ts: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}

export const PIPELINE_LOGS_URL = `${API_BASE}/api/pipeline/logs`;

// ── Auto-apply API functions ───────────────────────────────────────────────────

export const generateJobResume = (jobId: string): Promise<ResumeRecord> =>
  apiFetch<ResumeRecord>(`/api/jobs/${jobId}/generate-resume`, { method: 'POST' });

export function getJobResume(jobId: string): Promise<ResumeRecord | null> {
  return apiFetch<ResumeRecord>(`/api/jobs/${jobId}/resume`).catch((e: unknown) => {
    if (e instanceof Error && e.message.includes('404')) return null;
    throw e;
  });
}

export const applyToJob = (jobId: string): Promise<ApplyStatusResponse> =>
  apiFetch<ApplyStatusResponse>(`/api/jobs/${jobId}/apply`, { method: 'POST' });

export const getScreeningQuestions = (jobId: string): Promise<{ questions: ScreeningQuestion[] }> =>
  apiFetch<{ questions: ScreeningQuestion[] }>(`/api/jobs/${jobId}/screening`);

export const submitScreeningAnswers = (
  jobId: string,
  answers: Record<string, string>,
): Promise<ApplyStatusResponse> =>
  apiFetch<ApplyStatusResponse>(`/api/jobs/${jobId}/screening-answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });

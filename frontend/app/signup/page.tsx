'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Bot, Upload, CheckCircle, ChevronRight } from 'lucide-react';
import { register, uploadResumePreview, type ResumePreview } from '@/lib/api';
import { setToken } from '@/lib/auth';
import { useAuth } from '@/components/AuthProvider';

// ── Step types ────────────────────────────────────────────────────────────────

interface Credentials {
  email: string;
  password: string;
  confirmPassword: string;
}

interface Profile {
  full_name: string;
  phone: string;
  target_role: string;
  target_location: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
}

interface Preferences {
  ats_threshold: number;
  daily_limit: number;
}

// ── Field component ───────────────────────────────────────────────────────────

function Field({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1.5">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SignupPage() {
  const router = useRouter();
  const { setUser } = useAuth();

  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Step 1
  const [creds, setCreds] = useState<Credentials>({
    email: '',
    password: '',
    confirmPassword: '',
  });

  // Step 2
  const [profile, setProfile] = useState<Profile>({
    full_name: '',
    phone: '',
    target_role: 'Software Engineer',
    target_location: 'Remote',
    linkedin_url: '',
    github_url: '',
    portfolio_url: '',
  });

  // Step 3
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ResumePreview | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  // Step 4
  const [prefs, setPrefs] = useState<Preferences>({ ats_threshold: 60, daily_limit: 8 });

  // ── Step 1 validation ────────────────────────────────────────────────────────

  function validateStep1(): string | null {
    if (!creds.email || !/^[^@]+@[^@]+\.[^@]+$/.test(creds.email)) return 'Valid email required';
    if (creds.password.length < 8) return 'Password must be at least 8 characters';
    if (creds.password !== creds.confirmPassword) return 'Passwords do not match';
    return null;
  }

  // ── Step 3: handle file pick + auto-parse ────────────────────────────────────

  const handleFileChange = useCallback(async (file: File) => {
    if (!file || file.type !== 'application/pdf') {
      setParseError('Please upload a PDF file');
      return;
    }
    setResumeFile(file);
    setPreview(null);
    setParseError(null);
    setParsing(true);
    try {
      const result = await uploadResumePreview(file);
      setPreview(result);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Failed to parse resume');
    } finally {
      setParsing(false);
    }
  }, []);

  // ── Final submit ─────────────────────────────────────────────────────────────

  async function handleFinish() {
    setError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('email', creds.email);
      fd.append('password', creds.password);
      if (profile.full_name) fd.append('full_name', profile.full_name);
      if (profile.phone) fd.append('phone', profile.phone);
      if (profile.target_role) fd.append('target_role', profile.target_role);
      if (profile.target_location) fd.append('target_location', profile.target_location);
      if (profile.linkedin_url) fd.append('linkedin_url', profile.linkedin_url);
      if (profile.github_url) fd.append('github_url', profile.github_url);
      if (profile.portfolio_url) fd.append('portfolio_url', profile.portfolio_url);
      fd.append('ats_threshold', String(prefs.ats_threshold));
      fd.append('daily_limit', String(prefs.daily_limit));
      if (resumeFile) fd.append('resume_file', resumeFile);

      const res = await register(fd);
      setToken(res.access_token);
      setUser(res.user);
      router.push('/dashboard');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Registration failed');
      setSubmitting(false);
    }
  }

  // ── Step indicator ───────────────────────────────────────────────────────────

  const steps = ['Credentials', 'Profile', 'Resume', 'Preferences'];

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <Bot className="w-6 h-6 text-indigo-400" />
          <span className="text-xl font-semibold text-slate-100">Job Agent</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8">
          {/* Step indicator */}
          <div className="flex items-center gap-0 mb-8">
            {steps.map((label, i) => {
              const n = i + 1;
              const active = step === n;
              const done = step > n;
              return (
                <div key={n} className="flex items-center flex-1">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors ${
                        done
                          ? 'bg-indigo-600 border-indigo-600 text-white'
                          : active
                          ? 'border-indigo-500 text-indigo-400'
                          : 'border-slate-700 text-slate-600'
                      }`}
                    >
                      {done ? <CheckCircle className="w-4 h-4" /> : n}
                    </div>
                    <span
                      className={`text-xs mt-1 ${
                        active ? 'text-indigo-400' : done ? 'text-slate-400' : 'text-slate-600'
                      }`}
                    >
                      {label}
                    </span>
                  </div>
                  {i < steps.length - 1 && (
                    <div
                      className={`flex-1 h-px mx-2 mb-4 ${
                        done ? 'bg-indigo-600' : 'bg-slate-700'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* ── Step 1 ── */}
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-base font-semibold text-slate-100 mb-4">Create your account</h2>
              {error && (
                <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}
              <Field
                label="Email"
                type="email"
                value={creds.email}
                onChange={(v) => setCreds((c) => ({ ...c, email: v }))}
                placeholder="you@example.com"
                required
              />
              <Field
                label="Password"
                type="password"
                value={creds.password}
                onChange={(v) => setCreds((c) => ({ ...c, password: v }))}
                placeholder="Min. 8 characters"
                required
              />
              <Field
                label="Confirm Password"
                type="password"
                value={creds.confirmPassword}
                onChange={(v) => setCreds((c) => ({ ...c, confirmPassword: v }))}
                placeholder="Repeat password"
                required
              />
              <button
                onClick={() => {
                  const err = validateStep1();
                  if (err) { setError(err); return; }
                  setError(null);
                  setStep(2);
                }}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
              >
                Continue <ChevronRight className="w-4 h-4" />
              </button>
              <p className="text-center text-sm text-slate-500">
                Already have an account?{' '}
                <Link href="/login" className="text-indigo-400 hover:text-indigo-300 font-medium">
                  Sign in
                </Link>
              </p>
            </div>
          )}

          {/* ── Step 2 ── */}
          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-base font-semibold text-slate-100 mb-4">Your profile</h2>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Full Name" value={profile.full_name} onChange={(v) => setProfile((p) => ({ ...p, full_name: v }))} placeholder="Jane Doe" />
                <Field label="Phone" value={profile.phone} onChange={(v) => setProfile((p) => ({ ...p, phone: v }))} placeholder="+1 555 000 0000" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Target Role" value={profile.target_role} onChange={(v) => setProfile((p) => ({ ...p, target_role: v }))} placeholder="Software Engineer" />
                <Field label="Target Location" value={profile.target_location} onChange={(v) => setProfile((p) => ({ ...p, target_location: v }))} placeholder="Remote" />
              </div>
              <Field label="LinkedIn URL" value={profile.linkedin_url} onChange={(v) => setProfile((p) => ({ ...p, linkedin_url: v }))} placeholder="https://linkedin.com/in/..." />
              <Field label="GitHub URL" value={profile.github_url} onChange={(v) => setProfile((p) => ({ ...p, github_url: v }))} placeholder="https://github.com/..." />
              <Field label="Portfolio URL" value={profile.portfolio_url} onChange={(v) => setProfile((p) => ({ ...p, portfolio_url: v }))} placeholder="https://..." />
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setStep(3)}
                  className="flex-1 py-2.5 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm font-medium rounded-lg transition-colors"
                >
                  Skip for now
                </button>
                <button
                  onClick={() => setStep(3)}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
                >
                  Continue <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 3 ── */}
          {step === 3 && (
            <div className="space-y-4">
              <h2 className="text-base font-semibold text-slate-100 mb-1">Upload your resume</h2>
              <p className="text-sm text-slate-400 mb-4">We&apos;ll parse it with AI to power your applications.</p>

              {parseError && (
                <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-sm text-red-400">
                  {parseError}
                </div>
              )}

              {/* Drop zone */}
              <label
                className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
                  resumeFile && !parseError
                    ? 'border-indigo-500 bg-indigo-900/10'
                    : 'border-slate-700 hover:border-slate-500 bg-slate-800/40'
                }`}
              >
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileChange(f);
                  }}
                />
                {parsing ? (
                  <div className="flex flex-col items-center gap-2 text-slate-400">
                    <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500" />
                    <span className="text-sm">Parsing with AI…</span>
                  </div>
                ) : preview ? (
                  <div className="flex flex-col items-center gap-1 text-center px-4">
                    <CheckCircle className="w-7 h-7 text-indigo-400 mb-1" />
                    <p className="text-sm font-medium text-slate-200">{preview.name || 'Resume parsed'}</p>
                    <p className="text-xs text-slate-400">
                      {preview.skills_count} skills · {preview.experience_count} positions
                    </p>
                    <p className="text-xs text-slate-500 mt-1">Click to replace</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 text-slate-400">
                    <Upload className="w-6 h-6" />
                    <span className="text-sm">Drop PDF here or click to browse</span>
                  </div>
                )}
              </label>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setStep(4)}
                  disabled={!preview}
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* ── Step 4 ── */}
          {step === 4 && (
            <div className="space-y-5">
              <h2 className="text-base font-semibold text-slate-100 mb-4">Preferences</h2>

              {error && (
                <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-slate-400">ATS Threshold</label>
                  <span className="text-sm font-semibold text-indigo-400">{prefs.ats_threshold}</span>
                </div>
                <input
                  type="range"
                  min={40}
                  max={90}
                  value={prefs.ats_threshold}
                  onChange={(e) => setPrefs((p) => ({ ...p, ats_threshold: Number(e.target.value) }))}
                  className="w-full accent-indigo-500"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Jobs scoring below this will be filtered out. Higher = stricter.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Daily Application Limit
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={prefs.daily_limit}
                  onChange={(e) => setPrefs((p) => ({ ...p, daily_limit: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleFinish}
                  disabled={submitting}
                  className="flex-1 py-2.5 border border-slate-700 hover:bg-slate-800 disabled:opacity-50 text-slate-300 text-sm font-medium rounded-lg transition-colors"
                >
                  {submitting ? 'Creating…' : 'Skip & Finish'}
                </button>
                <button
                  onClick={handleFinish}
                  disabled={submitting}
                  className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  {submitting ? 'Creating…' : 'Save & Finish'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

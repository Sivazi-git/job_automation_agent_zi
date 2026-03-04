'use client';

import { useState, useRef } from 'react';
import { Upload, CheckCircle } from 'lucide-react';
import { updateProfile, uploadResume, type User } from '@/lib/api';
import { useAuth } from '@/components/AuthProvider';

function Field({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
      />
    </div>
  );
}

export default function ProfilePage() {
  const { user, setUser } = useAuth();

  const [form, setForm] = useState({
    full_name: user?.full_name ?? '',
    phone: user?.phone ?? '',
    target_role: user?.target_role ?? '',
    target_location: user?.target_location ?? '',
    linkedin_url: user?.linkedin_url ?? '',
    github_url: user?.github_url ?? '',
    portfolio_url: user?.portfolio_url ?? '',
    ats_threshold: user?.ats_threshold ?? 60,
    daily_limit: user?.daily_limit ?? 8,
  });

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadOk, setUploadOk] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function set(key: keyof typeof form, value: string | number) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      const updated = await updateProfile(form as Partial<User>);
      setUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadOk(false);
    setUploadError(null);
    try {
      const updated = await uploadResume(file);
      setUser(updated);
      setUploadOk(true);
      setTimeout(() => setUploadOk(false), 3000);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  if (!user) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Profile</h1>
        <p className="text-sm text-slate-400 mt-0.5">{user.email}</p>
      </div>

      {/* Profile form */}
      <form onSubmit={handleSave} className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-5">
        <h2 className="text-base font-semibold text-slate-100">Personal Info</h2>

        {saveError && (
          <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-sm text-red-400">
            {saveError}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <Field label="Full Name" value={form.full_name} onChange={(v) => set('full_name', v)} placeholder="Jane Doe" />
          <Field label="Phone" value={form.phone} onChange={(v) => set('phone', v)} placeholder="+1 555 000 0000" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Target Role" value={form.target_role} onChange={(v) => set('target_role', v)} placeholder="Software Engineer" />
          <Field label="Target Location" value={form.target_location} onChange={(v) => set('target_location', v)} placeholder="Remote" />
        </div>
        <Field label="LinkedIn URL" value={form.linkedin_url} onChange={(v) => set('linkedin_url', v)} placeholder="https://linkedin.com/in/..." />
        <Field label="GitHub URL" value={form.github_url} onChange={(v) => set('github_url', v)} placeholder="https://github.com/..." />
        <Field label="Portfolio URL" value={form.portfolio_url} onChange={(v) => set('portfolio_url', v)} placeholder="https://..." />

        <hr className="border-slate-800" />
        <h2 className="text-base font-semibold text-slate-100">Pipeline Preferences</h2>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-medium text-slate-400">ATS Threshold</label>
            <span className="text-sm font-semibold text-indigo-400">{form.ats_threshold}</span>
          </div>
          <input
            type="range"
            min={40}
            max={90}
            value={form.ats_threshold}
            onChange={(e) => set('ats_threshold', Number(e.target.value))}
            className="w-full accent-indigo-500"
          />
        </div>

        <Field
          label="Daily Application Limit"
          type="number"
          value={String(form.daily_limit)}
          onChange={(v) => set('daily_limit', Number(v))}
          placeholder="8"
        />

        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saved && <CheckCircle className="w-4 h-4" />}
          {saving ? 'Saving…' : saved ? 'Saved' : 'Save Changes'}
        </button>
      </form>

      {/* Resume card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-semibold text-slate-100">Master Resume</h2>

        {uploadError && (
          <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-sm text-red-400">
            {uploadError}
          </div>
        )}

        {user.master_resume_url ? (
          <div className="flex items-center justify-between p-3 bg-slate-800 rounded-lg">
            <div>
              <p className="text-sm text-slate-200 font-medium">Resume on file</p>
              <a
                href={user.master_resume_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-indigo-400 hover:text-indigo-300"
              >
                View PDF
              </a>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No resume uploaded yet.</p>
        )}

        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={handleResumeUpload}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-2 px-4 py-2.5 border border-slate-700 hover:bg-slate-800 disabled:opacity-50 text-slate-300 text-sm font-medium rounded-lg transition-colors"
        >
          {uploadOk ? (
            <>
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Uploaded
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              {uploading ? 'Uploading…' : user.master_resume_url ? 'Replace Resume' : 'Upload Resume'}
            </>
          )}
        </button>
      </div>
    </div>
  );
}

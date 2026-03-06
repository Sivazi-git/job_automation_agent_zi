'use client';

import { useState } from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import { type ScreeningQuestion, submitScreeningAnswers } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Props {
  jobId: string;
  questions: ScreeningQuestion[];
  onSubmit: () => void;
}

export default function ScreeningForm({ jobId, questions, onSubmit }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const q of questions) {
      init[q.question] = q.claude_answer ?? '';
    }
    return init;
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await submitScreeningAnswers(jobId, answers);
      setSuccess(true);
      onSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="flex items-center gap-2 text-emerald-400 text-sm">
        <CheckCircle className="w-4 h-4 shrink-0" />
        Answers submitted — applying in background
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {questions.map((q, i) => (
        <div key={i} className="space-y-1.5">
          <label className="flex items-start gap-1.5 text-sm text-slate-300">
            {q.needs_review && (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            )}
            <span>{q.question}</span>
          </label>
          {q.needs_review && (
            <p className="text-xs text-amber-400/80 ml-5">
              Low confidence — please review Claude&apos;s draft
            </p>
          )}
          <textarea
            rows={3}
            value={answers[q.question] ?? ''}
            onChange={(e) =>
              setAnswers((prev) => ({ ...prev, [q.question]: e.target.value }))
            }
            className={cn(
              'w-full rounded-lg bg-slate-900 border text-sm text-slate-200 p-2.5',
              'placeholder:text-slate-600 focus:outline-none focus:ring-1',
              q.needs_review
                ? 'border-amber-700/60 focus:ring-amber-500'
                : 'border-slate-700 focus:ring-indigo-500',
            )}
          />
        </div>
      ))}

      {error && (
        <div className="rounded-xl bg-red-900/20 border border-red-800/50 p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
      >
        {submitting ? 'Submitting…' : 'Submit & Apply'}
      </button>
    </form>
  );
}

'use client';

import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';
import type { ATSBreakdownData } from '@/lib/api';

function getScoreColor(score: number): string {
  if (score >= 70) return '#4ade80'; // green-400
  if (score >= 50) return '#facc15'; // yellow-400
  return '#f87171'; // red-400
}

function SubScoreBar({ label, value }: { label: string; value: number }) {
  const colorClass =
    value >= 70 ? 'bg-green-400' : value >= 50 ? 'bg-yellow-400' : 'bg-red-400';

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1.5">
        <span className="text-slate-300">{label}</span>
        <span className="text-slate-400 tabular-nums font-medium">
          {Math.round(value)}
        </span>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} rounded-full transition-all duration-700`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
    </div>
  );
}

interface ATSBreakdownProps {
  score: number;
  breakdown: ATSBreakdownData | null;
}

export default function ATSBreakdown({ score, breakdown }: ATSBreakdownProps) {
  const color = getScoreColor(score);
  const chartData = [{ value: score, fill: color }];

  return (
    <div className="flex flex-col lg:flex-row gap-8 items-start">
      {/* Score Ring */}
      <div className="flex flex-col items-center shrink-0">
        <div className="relative w-44 h-44">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="62%"
              outerRadius="90%"
              startAngle={90}
              endAngle={-270}
              data={chartData}
            >
              <RadialBar
                background={{ fill: '#1e293b' }}
                dataKey="value"
                max={100}
                cornerRadius={6}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span
              className="text-4xl font-bold tabular-nums"
              style={{ color }}
            >
              {Math.round(score)}
            </span>
            <span className="text-xs text-slate-400 mt-0.5">/ 100</span>
          </div>
        </div>
        <p className="text-sm mt-2" style={{ color }}>
          {score >= 70
            ? '✓ Passes threshold'
            : score >= 50
            ? '~ Borderline'
            : '✗ Below threshold'}
        </p>
      </div>

      {/* Sub-scores & Reasoning */}
      {breakdown && (
        <div className="flex-1 space-y-4 min-w-0 w-full">
          <SubScoreBar label="Skills Match" value={breakdown.skills_score} />
          <SubScoreBar
            label="Experience Match"
            value={breakdown.experience_score}
          />
          <SubScoreBar label="Title Match" value={breakdown.title_score} />
          <SubScoreBar
            label="Keywords Match"
            value={breakdown.keywords_score}
          />

          {breakdown.reasoning && (
            <div className="pt-4 border-t border-slate-700">
              <p className="text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wide">
                AI Reasoning
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                {breakdown.reasoning}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

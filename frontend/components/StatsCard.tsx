import type { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  label: string;
  value: number | string;
  icon: LucideIcon;
  color?: string;
  description?: string;
}

export default function StatsCard({
  label,
  value,
  icon: Icon,
  color = 'text-indigo-400',
  description,
}: StatsCardProps) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">
            {label}
          </p>
          <p className={`text-3xl font-bold mt-1.5 tabular-nums ${color}`}>
            {value}
          </p>
          {description && (
            <p className="text-xs text-slate-500 mt-1">{description}</p>
          )}
        </div>
        <div className="p-2 rounded-lg bg-slate-700/60 shrink-0 ml-2">
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
      </div>
    </div>
  );
}

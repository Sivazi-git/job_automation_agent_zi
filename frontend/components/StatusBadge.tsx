const statusConfig: Record<string, { label: string; classes: string }> = {
  new: {
    label: 'New',
    classes: 'bg-slate-700 text-slate-300 border border-slate-600',
  },
  queued: {
    label: 'Queued',
    classes: 'bg-indigo-900/50 text-indigo-300 border border-indigo-700/60',
  },
  applied: {
    label: 'Applied',
    classes: 'bg-green-900/50 text-green-300 border border-green-700/60',
  },
  skipped: {
    label: 'Filtered',
    classes: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700/60',
  },
  filtered: {
    label: 'Filtered',
    classes: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700/60',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-red-900/50 text-red-300 border border-red-700/60',
  },
};

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    label: status,
    classes: 'bg-slate-700 text-slate-300 border border-slate-600',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.classes}`}
    >
      {config.label}
    </span>
  );
}

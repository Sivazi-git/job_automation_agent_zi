interface KeywordTagsProps {
  matched: string[];
  missing: string[];
}

export default function KeywordTags({ matched, missing }: KeywordTagsProps) {
  return (
    <div className="space-y-5">
      {matched.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-2.5">
            Matched Keywords
            <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-green-900/40 text-green-400 rounded">
              {matched.length}
            </span>
          </h4>
          <div className="flex flex-wrap gap-2">
            {matched.map((kw) => (
              <span
                key={kw}
                className="px-2.5 py-1 text-xs font-medium bg-green-900/30 text-green-300 border border-green-700/40 rounded-full"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {missing.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-2.5">
            Missing Keywords
            <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-red-900/40 text-red-400 rounded">
              {missing.length}
            </span>
          </h4>
          <div className="flex flex-wrap gap-2">
            {missing.map((kw) => (
              <span
                key={kw}
                className="px-2.5 py-1 text-xs font-medium bg-red-900/30 text-red-300 border border-red-700/40 rounded-full"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

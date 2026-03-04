type Block =
  | { type: 'heading'; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] };

// Renders a string with **bold** and *bold* markers as inline bold spans.
function InlineText({ text }: { text: string }) {
  // Split on **...** first, then *...* within plain segments
  const parts: { content: string; bold: boolean }[] = [];
  const regex = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ content: text.slice(last, match.index), bold: false });
    }
    // match[1] = **...** capture, match[2] = *...* capture
    parts.push({ content: match[1] ?? match[2], bold: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ content: text.slice(last), bold: false });
  }

  if (parts.length === 0) return <>{text}</>;

  return (
    <>
      {parts.map((p, i) =>
        p.bold ? (
          <strong key={i} className="font-semibold text-slate-100">
            {p.content}
          </strong>
        ) : (
          <span key={i}>{p.content}</span>
        )
      )}
    </>
  );
}

function parseDescription(text: string): Block[] {
  const lines = text.split('\n');
  const blocks: Block[] = [];
  let currentList: string[] | null = null;

  const flushList = () => {
    if (currentList && currentList.length > 0) {
      blocks.push({ type: 'list', items: [...currentList] });
      currentList = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    // Empty line — flush pending list, skip
    if (!line) {
      flushList();
      continue;
    }

    // Bullet point: •, ·, -, *, –
    const bulletMatch = line.match(/^[•·\-\*–]\s+(.+)/);
    // Numbered list: 1. or 1)
    const numberedMatch = line.match(/^\d+[\.\)]\s+(.+)/);

    if (bulletMatch || numberedMatch) {
      const content = bulletMatch?.[1] ?? numberedMatch?.[1] ?? line;
      if (!currentList) currentList = [];
      currentList.push(content);
      continue;
    }

    // Section heading heuristic:
    //   - short line (< 80 chars) ending with ':'
    //   - OR all-uppercase word run with length 3–60
    const endsWithColon = line.endsWith(':') && line.length < 80;
    const isAllCaps =
      line === line.toUpperCase() &&
      line.length >= 3 &&
      line.length <= 60 &&
      /[A-Z]/.test(line);

    if (endsWithColon || isAllCaps) {
      flushList();
      blocks.push({ type: 'heading', text: line.replace(/:$/, '') });
      continue;
    }

    // Regular paragraph text
    flushList();
    blocks.push({ type: 'paragraph', text: line });
  }

  flushList();
  return blocks;
}

interface JobDescriptionProps {
  text: string;
}

export default function JobDescription({ text }: JobDescriptionProps) {
  const blocks = parseDescription(text);

  return (
    <div className="space-y-3 text-sm text-slate-300 leading-relaxed">
      {blocks.map((block, i) => {
        if (block.type === 'heading') {
          return (
            <h3
              key={i}
              className="text-sm font-semibold text-slate-100 pt-3 first:pt-0 border-b border-slate-700 pb-1"
            >
              <InlineText text={block.text} />
            </h3>
          );
        }

        if (block.type === 'list') {
          return (
            <ul key={i} className="space-y-1 pl-4">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                  <span><InlineText text={item} /></span>
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={i} className="text-slate-300">
            <InlineText text={block.text} />
          </p>
        );
      })}
    </div>
  );
}

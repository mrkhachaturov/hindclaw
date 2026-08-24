import { BookOpenIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Source } from '@/lib/ask-ai/protocol';

export function AskAiSources({ data }: { data: { sources?: Source[] } }): ReactNode {
  const sources = data?.sources ?? [];
  if (sources.length === 0) return null;

  return (
    <div className="mt-3 flex flex-col gap-1">
      <p className="text-muted-foreground/70 px-0.5 text-[11px] font-medium tracking-wide uppercase">
        Sources
      </p>
      <ul className="flex flex-col gap-1">
        {sources.map((source) => (
          <li key={source.url}>
            <a
              href={sameOriginHref(source.url)}
              className="border-border/60 hover:bg-muted/50 group flex items-start gap-2 rounded-lg border px-2.5 py-1.5 transition-colors"
            >
              <BookOpenIcon className="text-muted-foreground mt-0.5 size-3.5 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="group-hover:text-foreground block truncate text-xs font-medium">
                  {source.title}
                </span>
                {source.breadcrumbs ? (
                  <span className="text-muted-foreground block truncate text-[11px]">
                    {source.breadcrumbs}
                  </span>
                ) : null}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

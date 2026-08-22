'use client';
import { EditIcon, SparklesIcon, TextIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { MarkdownCopyButton } from '@/components/ai/page-actions';
import { askAi } from '@/lib/ask-ai/store';
import { cn } from '@/lib/utils';

const linkClass =
  'inline-flex items-center gap-1.5 text-xs text-fd-muted-foreground transition-colors hover:text-fd-foreground';

export function TocPageActions({
  markdownUrl,
  githubUrl,
  title,
}: {
  markdownUrl?: string;
  githubUrl?: string;
  title: string;
}): ReactNode {
  return (
    <div className="mt-6 flex shrink-0 flex-col items-start gap-3">
      {markdownUrl && (
        <>
          <MarkdownCopyButton
            markdownUrl={markdownUrl}
            className={cn(linkClass, 'h-auto bg-transparent p-0 shadow-none [&_svg]:size-3')}
          >
            Copy page
          </MarkdownCopyButton>
          <a href={markdownUrl} target="_blank" rel="noreferrer noopener" className={linkClass}>
            <TextIcon className="size-3" />
            View as Markdown
          </a>
        </>
      )}
      {githubUrl && (
        <a href={githubUrl} target="_blank" rel="noreferrer noopener" className={linkClass}>
          <EditIcon className="size-3" />
          Edit on GitHub
        </a>
      )}
      <button type="button" onClick={() => askAi(`Explain ${title}`)} className={linkClass}>
        <SparklesIcon className="size-3" />
        Ask AI
      </button>
    </div>
  );
}

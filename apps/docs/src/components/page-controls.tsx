import type * as PageTree from 'fumadocs-core/page-tree';
import { ArrowLeft, ArrowRight, ChevronDown } from 'lucide-react';
import type { ReactNode } from 'react';
import { MarkdownCopyButton, ViewOptionsPopover } from '@/components/ai/page-actions';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type PageNeighbour = Pick<PageTree.Item, 'name' | 'url'>;

export function PageControls({
  previous,
  next,
  markdownUrl,
  githubUrl,
  pathname,
  className,
}: {
  previous?: PageNeighbour;
  next?: PageNeighbour;
  markdownUrl?: string;
  githubUrl?: string;
  pathname: string;
  className?: string;
}): ReactNode {
  return (
    <div className={cn('not-prose flex shrink-0 items-center gap-2', className)}>
      {markdownUrl && (
        <div className="relative flex items-center rounded-lg bg-secondary">
          <MarkdownCopyButton
            markdownUrl={markdownUrl}
            className="rounded-none rounded-s-lg bg-transparent shadow-none"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-1.5 end-7 w-px bg-foreground/10"
          />
          <ViewOptionsPopover
            markdownUrl={markdownUrl}
            githubUrl={githubUrl}
            pathname={pathname}
            className="size-7 rounded-none rounded-e-lg bg-transparent px-0 shadow-none"
            aria-label="Page options"
          >
            <ChevronDown className="size-4" />
          </ViewOptionsPopover>
        </div>
      )}

      {previous && (
        <Button
          variant="secondary"
          size="icon-sm"
          nativeButton={false}
          render={
            <a href={previous.url}>
              <ArrowLeft />
              <span className="sr-only">Previous: {previous.name}</span>
            </a>
          }
        />
      )}

      {next && (
        <Button
          variant="secondary"
          size="icon-sm"
          nativeButton={false}
          render={
            <a href={next.url}>
              <span className="sr-only">Next: {next.name}</span>
              <ArrowRight />
            </a>
          }
        />
      )}
    </div>
  );
}

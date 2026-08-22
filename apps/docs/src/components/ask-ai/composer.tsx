import { AuiIf, ComposerPrimitive } from '@assistant-ui/react';
import { ArrowUpIcon, SquareIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function AskAiComposer({
  onSubmit,
  className,
  placeholder = 'Ask a question...',
  actions,
}: {
  onSubmit?: () => void;
  className?: string;
  placeholder?: string;
  actions?: ReactNode;
} = {}): ReactNode {
  return (
    <ComposerPrimitive.Root onSubmit={onSubmit} className={cn('pb-2.5', className)}>
      <div className="bg-muted/55 focus-within:bg-muted/75 rounded-3xl border border-transparent transition-colors">
        <ComposerPrimitive.Input asChild>
          <textarea
            placeholder={placeholder}
            className="placeholder:text-muted-foreground field-sizing-content max-h-32 w-full resize-none bg-transparent px-3.5 pt-3 pb-2 text-sm leading-5 focus:outline-none"
            rows={1}
          />
        </ComposerPrimitive.Input>
        <div className="flex items-center justify-between px-2 pb-2">
          <div className="text-muted-foreground/70 ps-1.5 text-xs">{actions}</div>
          <AskAiComposerAction />
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
}

export function AskAiComposerAction(): ReactNode {
  return (
    <>
      <AuiIf condition={(s) => !s.thread.isRunning}>
        <ComposerPrimitive.Send asChild>
          <Button size="icon" className="size-7 rounded-full">
            <ArrowUpIcon className="size-4" />
          </Button>
        </ComposerPrimitive.Send>
      </AuiIf>

      <AuiIf condition={(s) => s.thread.isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <Button type="button" variant="secondary" size="icon" className="size-7 rounded-full">
            <SquareIcon className="size-3 fill-current" />
          </Button>
        </ComposerPrimitive.Cancel>
      </AuiIf>
    </>
  );
}

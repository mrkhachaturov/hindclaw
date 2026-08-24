import { AuiIf, ComposerPrimitive, QueueItemPrimitive } from '@assistant-ui/react';
import { ArrowUpIcon, MicIcon, SquareIcon, XIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { ComposerQuotePreview } from '@/components/assistant-ui/quote';
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
      <AskAiComposerQueue />

      <div className="bg-muted/55 focus-within:bg-muted/75 rounded-3xl border border-transparent transition-colors">
        <ComposerQuotePreview className="mx-3.5 mt-2.5" />

        <ComposerPrimitive.Input asChild>
          <textarea
            placeholder={placeholder}
            className="placeholder:text-muted-foreground field-sizing-content max-h-32 w-full resize-none bg-transparent px-3.5 pt-3 pb-2 text-sm leading-5 focus:outline-none"
            rows={1}
          />
        </ComposerPrimitive.Input>

        <ComposerPrimitive.DictationTranscript className="text-muted-foreground/70 px-3.5 pb-1 text-xs italic" />

        <div className="flex items-center justify-between px-2 pb-2">
          <div className="text-muted-foreground/70 ps-1.5 text-xs">{actions}</div>
          <div className="flex items-center gap-1">
            <AskAiDictation />
            <AskAiComposerAction />
          </div>
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
}

function AskAiComposerQueue(): ReactNode {
  return (
    <div className="mb-1.5 flex flex-col gap-1 empty:hidden">
      <ComposerPrimitive.Queue>
        {() => (
          <div className="bg-muted/40 text-muted-foreground flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs">
            <QueueItemPrimitive.Text className="line-clamp-1 flex-1" />
            <QueueItemPrimitive.Remove asChild>
              <Button type="button" variant="ghost" size="icon" className="size-5 shrink-0">
                <XIcon className="size-3" />
              </Button>
            </QueueItemPrimitive.Remove>
          </div>
        )}
      </ComposerPrimitive.Queue>
    </div>
  );
}

function AskAiDictation(): ReactNode {
  return (
    <AuiIf condition={(s) => s.thread.capabilities.dictation}>
      <AuiIf condition={(s) => s.composer.dictation == null}>
        <ComposerPrimitive.Dictate asChild>
          <Button type="button" variant="ghost" size="icon" className="size-7 rounded-full">
            <MicIcon className="size-4" />
          </Button>
        </ComposerPrimitive.Dictate>
      </AuiIf>

      <AuiIf condition={(s) => s.composer.dictation != null}>
        <ComposerPrimitive.StopDictation asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7 animate-pulse rounded-full text-red-500"
          >
            <SquareIcon className="size-3 fill-current" />
          </Button>
        </ComposerPrimitive.StopDictation>
      </AuiIf>
    </AuiIf>
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

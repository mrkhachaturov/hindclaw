import { ChevronDownIcon, SparklesIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { AskAiSurface } from '@/components/ask-ai/surface';
import { pressable } from '@/components/elements/surfaces';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

const DOCK = 'bottom-[calc(0.75rem+env(safe-area-inset-bottom))]';

export function AskAiSheet(): ReactNode {
  const { open, setOpen } = useAskAiPanel();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className={cn(
          'gap-0 pb-[calc(4rem+env(safe-area-inset-bottom))]',
          'data-[side=right]:h-dvh data-[side=right]:w-full data-[side=right]:border-s-0 data-[side=right]:sm:max-w-none',
        )}
      >
        <SheetTitle className="sr-only">Ask AI</SheetTitle>

        <div className="min-h-0 flex-1">
          <AskAiSurface layout="sheet" />
        </div>

        <Button
          size="icon-lg"
          aria-label="Close chat"
          onClick={() => setOpen(false)}
          className={cn(pressable, DOCK, 'absolute end-4 size-11 rounded-full shadow-lg')}
        >
          <ChevronDownIcon className="size-5" />
        </Button>
      </SheetContent>
    </Sheet>
  );
}

export function AskAiMobileLauncher(): ReactNode {
  const { open, setOpen } = useAskAiPanel();

  return (
    <Button
      aria-label="Ask AI"
      onClick={() => setOpen(true)}
      className={cn(
        pressable,
        DOCK,
        'fixed end-4 z-40 h-11 rounded-full px-4 text-sm font-medium shadow-lg',
        'transition-[opacity,scale] duration-200 motion-reduce:transition-none',
        open ? 'pointer-events-none scale-90 opacity-0' : 'scale-100 opacity-100',
      )}
    >
      <SparklesIcon data-icon="inline-start" />
      Ask AI
    </Button>
  );
}

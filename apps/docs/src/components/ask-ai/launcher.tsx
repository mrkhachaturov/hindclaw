import { SparklesIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { pressable } from '@/components/elements/surfaces';
import { Kbd, KbdGroup } from '@/components/ui/kbd';
import { cn } from '@/lib/utils';

export function AskAiLauncher(): ReactNode {
  const { open, setOpen } = useAskAiPanel();

  return (
    <div
      className={cn(
        'fixed end-6 bottom-6 z-40 hidden size-11 transition-[opacity,scale] duration-200 motion-reduce:transition-none md:block',
        open ? 'pointer-events-none scale-90 opacity-0' : 'scale-100 opacity-100',
      )}
    >
      <TooltipIconButton
        variant="default"
        label="Ask AI"
        side="top"
        tooltipClassName="gap-2 rounded-xl border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-lg **:data-[slot=kbd]:h-5 **:data-[slot=kbd]:min-w-5 **:data-[slot=kbd]:text-xs **:data-[slot=tooltip-arrow]:bg-popover **:data-[slot=tooltip-arrow]:fill-popover"
        tooltip={
          <>
            Ask AI
            <KbdGroup className="gap-1">
              <Kbd>⌘</Kbd>
              <Kbd>I</Kbd>
            </KbdGroup>
          </>
        }
        onClick={() => setOpen(true)}
        className={cn(pressable, 'size-full rounded-full hover:scale-105')}
      >
        <SparklesIcon className="size-5" />
      </TooltipIconButton>
    </div>
  );
}

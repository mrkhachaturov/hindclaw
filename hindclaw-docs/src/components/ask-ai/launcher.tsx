import { SparklesIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { pressable } from '@/components/ask-ai/surfaces';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { cn } from '@/lib/utils';

export function AskAiLauncher(): ReactNode {
  const { open, setOpen } = useAskAiPanel();

  return (
    <div
      className={cn(
        'fixed end-4 bottom-4 z-40 hidden size-11 transition-[opacity,scale] duration-200 motion-reduce:transition-none md:block',
        open ? 'pointer-events-none scale-90 opacity-0' : 'scale-100 opacity-100',
      )}
    >
      <TooltipIconButton
        variant="default"
        tooltip="Ask AI"
        side="left"
        onClick={() => setOpen(true)}
        className={cn(pressable, 'size-full rounded-full hover:scale-105')}
      >
        <SparklesIcon className="size-5" />
      </TooltipIconButton>
    </div>
  );
}

import { useAui, useAuiEvent } from '@assistant-ui/react';
import { useStore } from '@nanostores/react';
import { HistoryIcon, PanelRightIcon, PlusIcon, SparklesIcon, XIcon } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { AskAiThread } from '@/components/ask-ai/thread';
import { ThreadList } from '@/components/assistant-ui/thread-list';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { askAiMode, toggleAskAiMode } from '@/lib/ask-ai/store';
import { cn } from '@/lib/utils';

type SurfaceLayout = 'panel' | 'sheet';

type SurfaceHeaderProps = {
  layout: SurfaceLayout;
  showHistory: boolean;
  onToggleHistory: () => void;
  onLeaveHistory: () => void;
  reserveResizeGrip: boolean;
};

export function AskAiSurface({
  layout = 'panel',
  reserveResizeGrip = false,
  children,
}: {
  layout?: SurfaceLayout;
  reserveResizeGrip?: boolean;
  children?: ReactNode;
} = {}): ReactNode {
  const [showHistory, setShowHistory] = useState(false);

  useAuiEvent('threads.selectionChanged', () => setShowHistory(false));

  return (
    <div className="bg-background flex h-full min-h-0 flex-col">
      <SurfaceHeader
        layout={layout}
        showHistory={showHistory}
        onToggleHistory={() => setShowHistory((shown) => !shown)}
        onLeaveHistory={() => setShowHistory(false)}
        reserveResizeGrip={reserveResizeGrip}
      />
      <div className="min-h-0 flex-1">
        {showHistory ? (
          <div className="h-full overflow-y-auto px-2 pb-2">
            <ThreadList />
          </div>
        ) : (
          <AskAiThread />
        )}
      </div>
      {children}
    </div>
  );
}

function SurfaceHeader({
  layout,
  showHistory,
  onToggleHistory,
  onLeaveHistory,
  reserveResizeGrip,
}: SurfaceHeaderProps): ReactNode {
  const { setOpen } = useAskAiPanel();
  const mode = useStore(askAiMode);
  const aui = useAui();

  const sheet = layout === 'sheet';

  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-between px-3',
        sheet ? 'h-14' : 'h-12',
        reserveResizeGrip && 'ps-8',
      )}
    >
      <div className="flex items-center gap-2">
        <span className="bg-muted/50 text-muted-foreground flex size-6 items-center justify-center rounded-md">
          <SparklesIcon className="size-3.5" />
        </span>
        <span className="text-sm font-semibold">Ask AI</span>
      </div>

      <div className={cn('flex items-center', sheet ? 'gap-1' : 'gap-0.5')}>
        {!sheet && (
          <HeaderAction
            layout={layout}
            tooltip={mode === 'docked' ? 'Detach from sidebar' : 'Dock to sidebar'}
            onClick={toggleAskAiMode}
          >
            <PanelRightIcon className={cn('size-4', mode === 'floating' && 'rotate-180')} />
          </HeaderAction>
        )}
        <HeaderAction
          layout={layout}
          tooltip={showHistory ? 'Back to chat' : 'History'}
          onClick={onToggleHistory}
          active={showHistory}
        >
          <HistoryIcon className="size-4" />
        </HeaderAction>
        <HeaderAction
          layout={layout}
          tooltip="New chat"
          onClick={() => {
            aui.threads.switchToNewThread();
            onLeaveHistory();
          }}
        >
          <PlusIcon className="size-4" />
        </HeaderAction>
        <HeaderAction layout={layout} tooltip="Close chat" onClick={() => setOpen(false)}>
          <XIcon className="size-4" />
        </HeaderAction>
      </div>
    </div>
  );
}

function HeaderAction({
  layout,
  tooltip,
  onClick,
  active = false,
  children,
}: {
  layout: SurfaceLayout;
  tooltip: string;
  onClick: () => void;
  active?: boolean;
  children: ReactNode;
}): ReactNode {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size={layout === 'sheet' ? 'icon-lg' : 'icon-sm'}
            onClick={onClick}
            aria-label={tooltip}
            className={cn(active && 'bg-muted text-foreground')}
          >
            {children}
          </Button>
        }
      />
      <TooltipContent side="bottom">{tooltip}</TooltipContent>
    </Tooltip>
  );
}

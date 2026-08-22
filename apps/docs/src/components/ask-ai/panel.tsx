import { type ReactNode, useEffect, useRef } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { AskAiSurface } from '@/components/ask-ai/surface';
import { useDragResize } from '@/hooks/use-drag-resize';
import { cn } from '@/lib/utils';

export function AskAiPanel(): ReactNode {
  const { open, width, isResizing } = useAskAiPanel();

  return (
    <div
      style={{ width }}
      aria-hidden={!open}
      className={cn(
        'fixed inset-y-0 end-0 z-40 hidden md:block',
        isResizing
          ? 'transition-none'
          : 'transition-transform duration-300 ease-out motion-reduce:transition-none',
        open ? 'translate-x-0' : 'pointer-events-none translate-x-full',
      )}
    >
      <div className="relative flex h-full flex-col p-2">
        <div className="border-border/60 bg-background flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border">
          <div className="min-h-0 flex-1">
            <AskAiSurface />
          </div>
        </div>
        <PanelResizeHandle />
      </div>
    </div>
  );
}

function PanelResizeHandle(): ReactNode {
  const { width, setWidth, setIsResizing } = useAskAiPanel();
  const startWidthRef = useRef(0);

  const { isResizing, onPointerDown } = useDragResize({
    onStart: () => {
      startWidthRef.current = width;
    },
    onMove: ({ dx }) => setWidth(startWidthRef.current - dx),
  });

  useEffect(() => setIsResizing(isResizing), [isResizing, setIsResizing]);

  return (
    <div
      onPointerDown={onPointerDown}
      className={cn(
        'absolute inset-y-2 start-1.5 w-1 cursor-col-resize',
        'after:absolute after:inset-y-0 after:start-1/2 after:w-px after:-translate-x-1/2 after:transition-colors',
        isResizing ? 'after:bg-primary/40' : 'after:bg-transparent hover:after:bg-primary/20',
      )}
    />
  );
}

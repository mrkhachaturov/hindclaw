import { type PointerEvent, type ReactNode, useRef, useState } from 'react';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { AskAiSurface } from '@/components/ask-ai/surface';
import { floating } from '@/components/elements/surfaces';
import { useDragResize } from '@/hooks/use-drag-resize';
import { clamp } from '@/lib/math';
import { cn } from '@/lib/utils';

const MIN_WIDTH = 320;
const MAX_WIDTH = 720;
const MIN_HEIGHT = 360;
const VIEWPORT_MARGIN = 32;
const DEFAULT_SIZE = { width: 400, height: 560 };

export function AskAiFloating(): ReactNode {
  const { open } = useAskAiPanel();
  const [size, setSize] = useState(DEFAULT_SIZE);
  const startRef = useRef(DEFAULT_SIZE);

  const { isResizing, onPointerDown } = useDragResize({
    onStart: () => {
      startRef.current = size;
    },
    onMove: ({ dx, dy }) =>
      setSize({
        width: clamp(startRef.current.width - dx, MIN_WIDTH, MAX_WIDTH),
        height: clamp(
          startRef.current.height - dy,
          MIN_HEIGHT,
          window.innerHeight - VIEWPORT_MARGIN,
        ),
      }),
  });

  return (
    <div
      style={{ width: size.width, height: size.height }}
      aria-hidden={!open}
      className={cn(
        'fixed end-4 bottom-4 z-50 hidden md:block',
        isResizing
          ? 'transition-none'
          : 'transition-[opacity,transform] duration-200 ease-out motion-reduce:transition-none',
        open ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-2 opacity-0',
      )}
    >
      <div
        className={cn(
          floating,
          'relative flex h-full flex-col overflow-hidden rounded-[1.75rem] shadow-2xl',
          '[&>*]:bg-inherit',
        )}
      >
        <AskAiSurface reserveResizeGrip />
        <FloatingResizeGrip onPointerDown={onPointerDown} />
      </div>
    </div>
  );
}

function FloatingResizeGrip({
  onPointerDown,
}: {
  onPointerDown: (event: PointerEvent) => void;
}): ReactNode {
  return (
    <div
      onPointerDown={onPointerDown}
      className={cn(
        'absolute start-2 top-2 z-10 size-4 cursor-nwse-resize transition-colors',
        'text-foreground/30 hover:text-foreground/60',
      )}
    >
      <svg viewBox="0 0 16 16" aria-hidden="true" className="size-full">
        <path
          d="M1 8 L8 1 M1 13 L13 1"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          fill="none"
        />
      </svg>
    </div>
  );
}

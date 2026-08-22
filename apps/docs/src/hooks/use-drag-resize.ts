import { useCallback, useRef, useState } from 'react';

export type DragDelta = { dx: number; dy: number };

export function useDragResize({
  onStart,
  onMove,
}: {
  onStart?: () => void;
  onMove: (delta: DragDelta) => void;
}): { isResizing: boolean; onPointerDown: (event: React.PointerEvent) => void } {
  const [isResizing, setIsResizing] = useState(false);
  const originRef = useRef({ x: 0, y: 0 });

  const onPointerDown = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault();
      originRef.current = { x: event.clientX, y: event.clientY };
      onStart?.();
      setIsResizing(true);

      const handleMove = (e: PointerEvent) => {
        onMove({ dx: e.clientX - originRef.current.x, dy: e.clientY - originRef.current.y });
      };

      const handleUp = () => {
        setIsResizing(false);
        document.removeEventListener('pointermove', handleMove);
        document.removeEventListener('pointerup', handleUp);
      };

      document.addEventListener('pointermove', handleMove);
      document.addEventListener('pointerup', handleUp);
    },
    [onMove, onStart],
  );

  return { isResizing, onPointerDown };
}

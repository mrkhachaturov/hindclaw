import { useStore } from '@nanostores/react';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import { askAi, askAiMode, askAiOpen, askAiPending, toggleAskAi } from '@/lib/ask-ai/store';
import { clamp } from '@/lib/math';

const MIN_WIDTH = 320;
const MAX_WIDTH = 600;
const DEFAULT_WIDTH = 400;

interface AskAiPanelContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  width: number;
  setWidth: (width: number) => void;
  isResizing: boolean;
  setIsResizing: (resizing: boolean) => void;
  pendingMessage: string | null;
  clearPendingMessage: () => void;
  askAI: (message: string) => void;
}

const AskAiPanelContext = createContext<AskAiPanelContextValue | null>(null);

export function useAskAiPanel(): AskAiPanelContextValue {
  const ctx = useContext(AskAiPanelContext);
  if (!ctx) throw new Error('useAskAiPanel must be used within AskAiPanelProvider');
  return ctx;
}

export function AskAiPanelProvider({ children }: { children: ReactNode }): ReactNode {
  const open = useStore(askAiOpen);
  const mode = useStore(askAiMode);
  const pendingMessage = useStore(askAiPending);

  const [width, setWidthState] = useState(DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);

  const setOpen = useCallback((next: boolean) => askAiOpen.set(next), []);
  const toggle = useCallback(() => toggleAskAi(), []);
  const clearPendingMessage = useCallback(() => askAiPending.set(null), []);
  const askAI = useCallback((message: string) => askAi(message), []);

  const setWidth = useCallback((next: number) => {
    setWidthState(clamp(next, MIN_WIDTH, MAX_WIDTH));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const docked = open && mode === 'docked';

    const apply = () => {
      root.style.setProperty('--ask-ai-panel-width', docked ? `${width}px` : '0px');
      root.toggleAttribute('data-ask-ai-resizing', isResizing);
    };

    apply();
    document.addEventListener('astro:after-swap', apply);

    return () => {
      document.removeEventListener('astro:after-swap', apply);
      root.style.setProperty('--ask-ai-panel-width', '0px');
    };
  }, [open, width, isResizing, mode]);

  return (
    <AskAiPanelContext.Provider
      value={{
        open,
        setOpen,
        toggle,
        width,
        setWidth,
        isResizing,
        setIsResizing,
        pendingMessage,
        clearPendingMessage,
        askAI,
      }}
    >
      {children}
    </AskAiPanelContext.Provider>
  );
}

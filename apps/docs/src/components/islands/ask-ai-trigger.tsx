import { type ReactNode, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Kbd, KbdGroup } from '@/components/ui/kbd';
import { toggleAskAi } from '@/lib/ask-ai/store';

export function AskAiTrigger(): ReactNode {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'i' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        toggleAskAi();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, []);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => toggleAskAi()}
      className="hidden md:inline-flex"
      aria-label="Ask AI (⌘I)"
    >
      Ask AI
      <KbdGroup className="hidden lg:inline-flex">
        <Kbd>⌘</Kbd>
        <Kbd>I</Kbd>
      </KbdGroup>
    </Button>
  );
}

import { SelectionToolbarPrimitive } from '@assistant-ui/react';
import { QuoteIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export function AskAiSelectionToolbar(): ReactNode {
  return (
    <SelectionToolbarPrimitive.Root className="bg-popover border-border/60 z-50 flex items-center gap-1 rounded-lg border p-1 shadow-md">
      <SelectionToolbarPrimitive.Quote className="text-muted-foreground hover:bg-muted hover:text-foreground flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors">
        <QuoteIcon className="size-3" />
        Quote
      </SelectionToolbarPrimitive.Quote>
    </SelectionToolbarPrimitive.Root>
  );
}

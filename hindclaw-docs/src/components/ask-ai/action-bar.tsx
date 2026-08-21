import { ActionBarPrimitive, AuiIf, useAuiState } from '@assistant-ui/react';
import { CheckIcon, CopyIcon, ThumbsDownIcon, ThumbsUpIcon } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { cn } from '@/lib/utils';

const NON_WHITESPACE_RE = /\S/;

const buttonClass = cn(
  'text-muted-foreground rounded p-1 transition-colors',
  'hover:bg-muted hover:text-foreground',
  'disabled:cursor-not-allowed disabled:opacity-50',
);

export function AskAiActionBar(): ReactNode {
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const content = useAuiState((s) => s.message.content);
  const isRunning = useAuiState((s) => s.message.status?.type === 'running');

  const hasText = content.some(
    (part) => part.type === 'text' && NON_WHITESPACE_RE.test(part.text ?? ''),
  );
  if (isRunning || !hasText) return null;

  return (
    <ActionBarPrimitive.Root className="mt-2 flex items-center gap-1">
      <ActionBarPrimitive.Copy aria-label="Copy response" className={buttonClass}>
        <AuiIf condition={(s) => s.message.isCopied}>
          <CheckIcon className="size-4" />
        </AuiIf>
        <AuiIf condition={(s) => !s.message.isCopied}>
          <CopyIcon className="size-4" />
        </AuiIf>
      </ActionBarPrimitive.Copy>

      <button
        type="button"
        onClick={() => setFeedback('positive')}
        disabled={feedback !== null}
        aria-label="Good response"
        className={cn(buttonClass, feedback === 'positive' && 'text-green-600 dark:text-green-400')}
      >
        <ThumbsUpIcon className="size-4" />
      </button>

      <button
        type="button"
        onClick={() => setFeedback('negative')}
        disabled={feedback !== null}
        aria-label="Report issue with response"
        className={cn(buttonClass, feedback === 'negative' && 'text-red-600 dark:text-red-400')}
      >
        <ThumbsDownIcon className="size-4" />
      </button>
    </ActionBarPrimitive.Root>
  );
}

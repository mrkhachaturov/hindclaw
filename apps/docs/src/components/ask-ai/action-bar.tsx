import { ActionBarPrimitive, AuiIf, useAuiState } from '@assistant-ui/react';
import {
  AudioLinesIcon,
  CheckIcon,
  CopyIcon,
  DownloadIcon,
  RefreshCwIcon,
  StopCircleIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const NON_WHITESPACE_RE = /\S/;

const buttonClass = cn(
  'text-muted-foreground rounded p-1 transition-colors',
  'hover:bg-muted hover:text-foreground',
  'disabled:cursor-not-allowed disabled:opacity-50',
);

export function AskAiActionBar(): ReactNode {
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

      <AuiIf condition={(s) => s.thread.capabilities.reload}>
        <ActionBarPrimitive.Reload aria-label="Regenerate response" className={buttonClass}>
          <RefreshCwIcon className="size-4" />
        </ActionBarPrimitive.Reload>
      </AuiIf>

      <AuiIf condition={(s) => s.thread.capabilities.speech}>
        <AuiIf condition={(s) => s.message.speech == null}>
          <ActionBarPrimitive.Speak aria-label="Read aloud" className={buttonClass}>
            <AudioLinesIcon className="size-4" />
          </ActionBarPrimitive.Speak>
        </AuiIf>
        <AuiIf condition={(s) => s.message.speech != null}>
          <ActionBarPrimitive.StopSpeaking aria-label="Stop reading" className={buttonClass}>
            <StopCircleIcon className="size-4" />
          </ActionBarPrimitive.StopSpeaking>
        </AuiIf>
      </AuiIf>

      <ActionBarPrimitive.ExportMarkdown aria-label="Download as Markdown" className={buttonClass}>
        <DownloadIcon className="size-4" />
      </ActionBarPrimitive.ExportMarkdown>

      <AuiIf condition={(s) => s.thread.capabilities.feedback}>
        <ActionBarPrimitive.FeedbackPositive
          aria-label="Good response"
          className={cn(
            buttonClass,
            'data-[submitted]:text-green-600 dark:data-[submitted]:text-green-400',
          )}
        >
          <ThumbsUpIcon className="size-4" />
        </ActionBarPrimitive.FeedbackPositive>

        <ActionBarPrimitive.FeedbackNegative
          aria-label="Report issue with response"
          className={cn(
            buttonClass,
            'data-[submitted]:text-red-600 dark:data-[submitted]:text-red-400',
          )}
        >
          <ThumbsDownIcon className="size-4" />
        </ActionBarPrimitive.FeedbackNegative>
      </AuiIf>
    </ActionBarPrimitive.Root>
  );
}

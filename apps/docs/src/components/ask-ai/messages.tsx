import {
  AuiIf,
  BranchPickerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  type ToolCallMessagePartProps,
  useToolCallElapsed,
} from '@assistant-ui/react';
import { useStore } from '@nanostores/react';
import {
  BookOpenIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  FileTextIcon,
  FolderTreeIcon,
  LoaderIcon,
  type LucideIcon,
  SearchIcon,
} from 'lucide-react';
import type { ComponentType, ReactNode } from 'react';
import { AskAiActionBar } from '@/components/ask-ai/action-bar';
import { DotMatrix } from '@/components/assistant-ui/dot-matrix';
import { MarkdownText } from '@/components/assistant-ui/markdown-text';
import { Reasoning } from '@/components/assistant-ui/reasoning';
import type { SearchArtifact } from '@/lib/ask-ai/protocol';
import { askAiSearch } from '@/lib/ask-ai/store';
import { cn } from '@/lib/utils';

const MS_IN_SECOND = 1_000;

export function UserMessage(): ReactNode {
  return (
    <MessagePrimitive.Root className="flex flex-col items-end py-2" data-role="user">
      <MessagePrimitive.Quote>
        {({ text }) => (
          <div className="text-muted-foreground border-border/60 mb-1 line-clamp-3 max-w-[85%] border-s-2 py-1 ps-2 text-xs italic">
            {text}
          </div>
        )}
      </MessagePrimitive.Quote>
      <div className="bg-muted max-w-[85%] rounded-2xl px-3 py-2 text-sm empty:hidden">
        <MessagePrimitive.Parts />
      </div>
      <AskAiBranchPicker />
    </MessagePrimitive.Root>
  );
}

export function AssistantMessage({
  ToolCallComponent = ToolCall,
}: {
  ToolCallComponent?: ComponentType<ToolCallMessagePartProps>;
} = {}): ReactNode {
  return (
    <MessagePrimitive.Root className="py-2" data-role="assistant">
      <div className="text-sm">
        <MessagePrimitive.Parts>
          {({ part }) => {
            if (part.type === 'text') return <MarkdownText />;
            if (part.type === 'reasoning') return <Reasoning {...part} />;
            if (part.type === 'tool-call') return part.toolUI ?? <ToolCallComponent {...part} />;
            return null;
          }}
        </MessagePrimitive.Parts>

        <AuiIf condition={(s) => s.thread.isRunning && s.message.content.length === 0}>
          <PendingIndicator />
        </AuiIf>
        <MessageError />
      </div>
      <AskAiBranchPicker />
      <AskAiActionBar />
    </MessagePrimitive.Root>
  );
}

function PendingIndicator(): ReactNode {
  const search = useStore(askAiSearch);

  return (
    <div className="text-muted-foreground flex items-center gap-2 py-1">
      <DotMatrix state="connecting" aria-hidden />
      <span className="text-sm">{search ? `Searching “${search.query}”` : 'Connecting'}</span>
    </div>
  );
}

function AskAiBranchPicker(): ReactNode {
  return (
    <AuiIf condition={(s) => s.message.branchCount > 1}>
      <BranchPickerPrimitive.Root className="text-muted-foreground mt-1 flex items-center gap-0.5 text-xs">
        <BranchPickerPrimitive.Previous
          aria-label="Previous answer"
          className="hover:text-foreground rounded p-0.5"
        >
          <ChevronLeftIcon className="size-3.5" />
        </BranchPickerPrimitive.Previous>
        <span className="tabular-nums">
          <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
        </span>
        <BranchPickerPrimitive.Next
          aria-label="Next answer"
          className="hover:text-foreground rounded p-0.5"
        >
          <ChevronRightIcon className="size-3.5" />
        </BranchPickerPrimitive.Next>
      </BranchPickerPrimitive.Root>
    </AuiIf>
  );
}

function getToolDisplay(
  toolName: string,
  args: Record<string, unknown>,
  artifact: SearchArtifact | undefined,
  isRunning: boolean,
): { icon: LucideIcon; label: string; detail: string } {
  switch (toolName) {
    case 'search_docs': {
      const query = artifact?.query ?? (args as { query?: string })?.query ?? '';
      return {
        icon: SearchIcon,
        label: isRunning ? 'Searching' : 'Searched',
        detail: query ? `“${query}”` : 'the documentation',
      };
    }
    case 'list_docs': {
      const path = (args as { path?: string })?.path;
      return {
        icon: FolderTreeIcon,
        label: isRunning ? 'Listing' : 'Listed',
        detail: path ? `/${path}` : 'documentation structure',
      };
    }
    case 'read_doc': {
      const slug = ((args as { slug?: string })?.slug ?? '').replace(/^\/docs\/?/, '');
      return {
        icon: FileTextIcon,
        label: isRunning ? 'Reading' : 'Read',
        detail: `/docs/${slug}`,
      };
    }
    default:
      return {
        icon: BookOpenIcon,
        label: isRunning ? 'Running' : 'Completed',
        detail: toolName,
      };
  }
}

function ToolStatusIcon({
  status,
  FallbackIcon,
}: {
  status: { type: string } | undefined;
  FallbackIcon: LucideIcon;
}): ReactNode {
  switch (status?.type) {
    case 'running':
      return <LoaderIcon className="size-3 animate-spin" />;
    case 'complete':
      return <CheckIcon className="size-3 text-emerald-500" />;
    default:
      return <FallbackIcon className="size-3" />;
  }
}

function formatDuration(ms: number): string {
  return ms < MS_IN_SECOND ? `${ms}ms` : `${(ms / MS_IN_SECOND).toFixed(1)}s`;
}

function ToolCall({ toolName, args, status, artifact }: ToolCallMessagePartProps): ReactNode {
  const isRunning = status?.type === 'running';
  const { icon, label, detail } = getToolDisplay(
    toolName,
    args,
    artifact as SearchArtifact | undefined,
    isRunning,
  );
  const elapsed = useToolCallElapsed();
  const found = (artifact as SearchArtifact | undefined)?.sources?.length;

  return (
    <div
      className={cn(
        'border-border/60 bg-muted/30 text-muted-foreground my-1.5 flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs',
        isRunning && 'animate-pulse',
      )}
    >
      <ToolStatusIcon status={status} FallbackIcon={icon} />
      <span className="flex-1 truncate">
        {label} {detail}
      </span>
      {found === undefined ? null : (
        <span className="text-muted-foreground/60 shrink-0">
          {found} {found === 1 ? 'page' : 'pages'}
        </span>
      )}
      {elapsed === undefined ? null : (
        <span className="text-muted-foreground/60 shrink-0">{formatDuration(elapsed)}</span>
      )}
    </div>
  );
}

function MessageError(): ReactNode {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="border-destructive bg-destructive/10 text-destructive dark:bg-destructive/5 mt-2 rounded-md border p-2 text-xs dark:text-red-200">
        <ErrorPrimitive.Message className="line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
}

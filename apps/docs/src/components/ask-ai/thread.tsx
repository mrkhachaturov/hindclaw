import { AuiIf, ThreadPrimitive, useAui, useAuiState } from '@assistant-ui/react';
import { BookOpenIcon, KeyRoundIcon, RocketIcon, SparklesIcon, TerminalIcon } from 'lucide-react';
import { type ComponentType, type ReactNode, useEffect, useRef } from 'react';
import { AskAiComposer } from '@/components/ask-ai/composer';
import { useAskAiPanel } from '@/components/ask-ai/context';
import { AssistantMessage, UserMessage } from '@/components/ask-ai/messages';

function PendingMessageHandler(): null {
  const { pendingMessage, clearPendingMessage } = useAskAiPanel();
  const aui = useAui();
  const isRunning = useAuiState((s) => s.thread.isRunning);
  const processedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pendingMessage || processedRef.current === pendingMessage) return;
    if (isRunning) return;

    processedRef.current = pendingMessage;
    clearPendingMessage();
    aui.thread.append(pendingMessage);
  }, [pendingMessage, clearPendingMessage, aui, isRunning]);

  return null;
}

type AskAiThreadProps = {
  welcome?: ReactNode;
  composer?: ReactNode;
  footer?: ReactNode;
  UserMessageComponent?: ComponentType;
  AssistantMessageComponent?: ComponentType;
};

export function AskAiThread({
  welcome = <AskAiWelcome />,
  composer = <AskAiComposer />,
  footer,
  UserMessageComponent = UserMessage,
  AssistantMessageComponent = AssistantMessage,
}: AskAiThreadProps = {}): ReactNode {
  return (
    <ThreadPrimitive.Root className="bg-background flex h-full flex-col">
      <PendingMessageHandler />
      <ThreadPrimitive.Viewport className="scrollbar-none mask-[linear-gradient(to_bottom,transparent,black_2rem)] flex flex-1 flex-col overflow-y-auto overscroll-contain px-3 pt-3">
        <AuiIf condition={(s) => s.thread.isEmpty}>{welcome}</AuiIf>

        <div className="px-1.5" data-slot="thread-messages">
          <ThreadPrimitive.Messages>
            {({ message }) => {
              if (message.role === 'user') return <UserMessageComponent />;
              if (message.role === 'assistant') return <AssistantMessageComponent />;
              return null;
            }}
          </ThreadPrimitive.Messages>
        </div>

        <ThreadPrimitive.ViewportFooter className="bg-background sticky bottom-0 mt-auto flex flex-col overflow-visible rounded-t-xl">
          {composer}
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
      {footer}
    </ThreadPrimitive.Root>
  );
}

const SUGGESTIONS = [
  { prompt: 'What is HindClaw?', Icon: BookOpenIcon },
  { prompt: 'How do I install the server extension?', Icon: RocketIcon },
  { prompt: 'How do policies decide who can recall a bank?', Icon: KeyRoundIcon },
  { prompt: 'Show me the Terraform provider setup', Icon: TerminalIcon },
];

function AskAiWelcome(): ReactNode {
  return (
    <div className="flex flex-1 flex-col pb-3">
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <div className="bg-muted/50 text-muted-foreground flex size-10 items-center justify-center rounded-xl">
          <SparklesIcon className="size-5" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium">How can I help?</p>
          <p className="text-muted-foreground mt-1 text-xs">Ask anything about HindClaw.</p>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        {SUGGESTIONS.map(({ prompt, Icon }) => (
          <ThreadPrimitive.Suggestion
            key={prompt}
            prompt={prompt}
            send
            className="border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors"
          >
            <Icon className="text-muted-foreground size-4 shrink-0" />
            {prompt}
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  );
}

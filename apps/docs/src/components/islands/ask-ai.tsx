import {
  AssistantRuntimeProvider,
  type ThreadSuggestion,
  WebSpeechDictationAdapter,
  WebSpeechSynthesisAdapter,
} from '@assistant-ui/react';
import {
  type LangChainMessage,
  type UIMessage,
  unstable_createLangGraphStream,
  useLangGraphRuntime,
} from '@assistant-ui/react-langgraph';
import { useStore } from '@nanostores/react';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { AskAiPanelProvider } from '@/components/ask-ai/context';
import { AskAiFloating } from '@/components/ask-ai/floating';
import { AskAiLauncher } from '@/components/ask-ai/launcher';
import { AskAiPanel } from '@/components/ask-ai/panel';
import { AskAiSources } from '@/components/ask-ai/sources';
import { SelectionToolbar } from '@/components/assistant-ui/quote';
import { createGetCheckpointId } from '@/lib/ask-ai/checkpoints';
import { createAgentClient } from '@/lib/ask-ai/client';
import { bindFeedbackUrl, feedbackAdapter, rememberFeedbackUrl } from '@/lib/ask-ai/feedback';
import { ASSISTANT_ID, isSearchProgress, STREAM_MODES } from '@/lib/ask-ai/protocol';
import { askAiMode, askAiSearch, hydrateAskAiMode } from '@/lib/ask-ai/store';
import { AskAiThreadListAdapter } from '@/lib/ask-ai/thread-list-adapter';

type ThreadValues = {
  messages: LangChainMessage[];
  ui?: UIMessage[];
  follow_ups?: string[];
};

function speechAdapter() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return undefined;
  return new WebSpeechSynthesisAdapter();
}

function dictationAdapter() {
  if (typeof window === 'undefined' || !WebSpeechDictationAdapter.isSupported()) return undefined;
  return new WebSpeechDictationAdapter({
    language: 'en-US',
    continuous: true,
    interimResults: true,
  });
}

export function AskAi(): ReactNode {
  const mode = useStore(askAiMode);

  const client = useMemo(() => createAgentClient(), []);
  const [threadListAdapter] = useState(() => new AskAiThreadListAdapter(client));
  const [adapters] = useState(() => ({
    feedback: feedbackAdapter,
    speech: speechAdapter(),
    dictation: dictationAdapter(),
  }));
  const [suggestions, setSuggestions] = useState<ThreadSuggestion[]>([]);

  const stream = useMemo(
    () =>
      unstable_createLangGraphStream({
        client,
        assistantId: ASSISTANT_ID,
        streamMode: [...STREAM_MODES],
      }),
    [client],
  );

  const getCheckpointId = useMemo(() => createGetCheckpointId(client), [client]);

  const runtime = useLangGraphRuntime({
    stream,
    getCheckpointId,
    suggestions,
    adapters,
    unstable_threadListAdapter: threadListAdapter,
    unstable_allowCancellation: true,
    unstable_enableMessageQueue: true,
    uiComponents: { renderers: { sources: AskAiSources } },
    eventHandlers: {
      onCustomEvent: (_type, data) => {
        if (!isSearchProgress(data)) return;
        askAiSearch.set(data.phase === 'start' ? data : null);
      },
      onMetadata: rememberFeedbackUrl,
      onValues: (values) => {
        bindFeedbackUrl(values);
        const followUps = (values as ThreadValues | undefined)?.follow_ups ?? [];
        setSuggestions(followUps.map((prompt) => ({ prompt })));
      },
    },
    load: async (externalId) => {
      const state = await client.threads.getState<ThreadValues>(externalId);
      return {
        messages: state.values.messages,
        uiMessages: state.values.ui,
        interrupts: state.tasks[0]?.interrupts,
      };
    },
  });

  useEffect(() => hydrateAskAiMode(), []);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AskAiPanelProvider>
        {mode === 'docked' ? <AskAiPanel /> : <AskAiFloating />}
        <AskAiLauncher />
        <SelectionToolbar className="z-50 shadow-md" />
      </AskAiPanelProvider>
    </AssistantRuntimeProvider>
  );
}

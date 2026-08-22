import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  useRemoteThreadListRuntime,
} from '@assistant-ui/react';
import { useStore } from '@nanostores/react';
import { type ReactNode, useEffect, useState } from 'react';
import { AskAiPanelProvider } from '@/components/ask-ai/context';
import { AskAiFloating } from '@/components/ask-ai/floating';
import { AskAiLauncher } from '@/components/ask-ai/launcher';
import { AskAiPanel } from '@/components/ask-ai/panel';
import { previewChatModelAdapter } from '@/lib/ask-ai/preview-adapter';
import { askAiMode, hydrateAskAiMode } from '@/lib/ask-ai/store';
import { AskAiThreadListAdapter } from '@/lib/ask-ai/thread-list-adapter';

function useAskAiThreadRuntime() {
  return useLocalRuntime(previewChatModelAdapter);
}

export function AskAi(): ReactNode {
  const [threadListAdapter] = useState(() => new AskAiThreadListAdapter());
  const mode = useStore(askAiMode);

  const runtime = useRemoteThreadListRuntime({
    adapter: threadListAdapter,
    runtimeHook: useAskAiThreadRuntime,
  });

  useEffect(() => hydrateAskAiMode(), []);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AskAiPanelProvider>
        {mode === 'docked' ? <AskAiPanel /> : <AskAiFloating />}
        <AskAiLauncher />
      </AskAiPanelProvider>
    </AssistantRuntimeProvider>
  );
}

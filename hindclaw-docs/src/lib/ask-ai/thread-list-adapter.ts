import { InMemoryThreadListAdapter, type ThreadMessage } from '@assistant-ui/react';
import { type AssistantStream, createAssistantStream } from 'assistant-stream';

export class AskAiThreadListAdapter extends InMemoryThreadListAdapter {
  override generateTitle(
    _remoteId?: string,
    messages: readonly ThreadMessage[] = [],
  ): Promise<AssistantStream> {
    const text = (messages.find((m) => m.role === 'user')?.content ?? [])
      .map((part) => (part.type === 'text' ? part.text : ''))
      .join('')
      .trim();

    const title = text.length > 48 ? `${text.slice(0, 48)}…` : text;

    return Promise.resolve(
      createAssistantStream(async (controller) => {
        if (title) controller.appendText(title);
      }),
    );
  }
}

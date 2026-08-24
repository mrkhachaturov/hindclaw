import type { Client } from '@langchain/langgraph-sdk';

type HistoryMessage = { id?: string };

export function createGetCheckpointId(client: Client) {
  return async function getCheckpointId(
    threadId: string,
    parentMessages: readonly HistoryMessage[],
  ): Promise<string | null> {
    const history = await client.threads.getHistory<{ messages?: HistoryMessage[] }>(threadId);

    for (const state of history) {
      const messages = state.values?.messages;
      if (!messages || messages.length !== parentMessages.length) continue;

      const stable =
        parentMessages.every((message) => typeof message.id === 'string') &&
        messages.every((message) => typeof message.id === 'string');
      if (!stable) continue;

      const matches = parentMessages.every((message, index) => message.id === messages[index]?.id);
      if (matches) return state.checkpoint?.checkpoint_id ?? null;
    }

    return null;
  };
}

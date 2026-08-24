import type { RemoteThreadListAdapter, ThreadMessage } from '@assistant-ui/react';
import type { Client, Thread } from '@langchain/langgraph-sdk';
import { type AssistantStream, createAssistantStream } from 'assistant-stream';

const MAX_TITLE_LENGTH = 48;
const PAGE_SIZE = 30;

type PageOptions = Parameters<RemoteThreadListAdapter['list']>[0];
type ListResponse = Awaited<ReturnType<RemoteThreadListAdapter['list']>>;
type ThreadSummary = Awaited<ReturnType<RemoteThreadListAdapter['fetch']>>;
type InitializeResponse = Awaited<ReturnType<RemoteThreadListAdapter['initialize']>>;

type ThreadMetadata = { title?: string; archived?: boolean };

function toMetadata(thread: Thread): ThreadSummary {
  const metadata = (thread.metadata ?? {}) as ThreadMetadata;

  return {
    status: metadata.archived ? 'archived' : 'regular',
    remoteId: thread.thread_id,
    externalId: thread.thread_id,
    title: metadata.title,
    lastMessageAt: new Date(thread.updated_at ?? thread.created_at),
  };
}

function firstUserText(messages: readonly ThreadMessage[]): string {
  return (messages.find((message) => message.role === 'user')?.content ?? [])
    .map((part) => (part.type === 'text' ? part.text : ''))
    .join('')
    .trim();
}

export class AskAiThreadListAdapter implements RemoteThreadListAdapter {
  constructor(private readonly client: Client) {}

  async list(params?: PageOptions): Promise<ListResponse> {
    const offset = params?.after ? Number(params.after) : 0;
    const threads = await this.client.threads.search({
      limit: PAGE_SIZE,
      offset: Number.isFinite(offset) ? offset : 0,
    });

    return {
      threads: threads.map(toMetadata),
      ...(threads.length === PAGE_SIZE ? { nextCursor: String(offset + PAGE_SIZE) } : {}),
    };
  }

  async initialize(_threadId: string): Promise<InitializeResponse> {
    const thread = await this.client.threads.create({ metadata: { source: 'ask-ai' } });
    return { remoteId: thread.thread_id, externalId: thread.thread_id };
  }

  async fetch(threadId: string): Promise<ThreadSummary> {
    return toMetadata(await this.client.threads.get(threadId));
  }

  async rename(remoteId: string, newTitle: string): Promise<void> {
    await this.patch(remoteId, { title: newTitle });
  }

  async archive(remoteId: string): Promise<void> {
    await this.patch(remoteId, { archived: true });
  }

  async unarchive(remoteId: string): Promise<void> {
    await this.patch(remoteId, { archived: false });
  }

  async delete(remoteId: string): Promise<void> {
    await this.client.threads.delete(remoteId);
  }

  generateTitle(
    remoteId: string,
    messages: readonly ThreadMessage[] = [],
  ): Promise<AssistantStream> {
    const text = firstUserText(messages);
    const title = text.length > MAX_TITLE_LENGTH ? `${text.slice(0, MAX_TITLE_LENGTH)}…` : text;

    if (title) void this.patch(remoteId, { title }).catch(() => undefined);

    return Promise.resolve(
      createAssistantStream(async (controller) => {
        if (title) controller.appendText(title);
      }),
    );
  }

  private async patch(remoteId: string, patch: ThreadMetadata): Promise<void> {
    const thread = await this.client.threads.get(remoteId);
    await this.client.threads.update(remoteId, {
      metadata: { ...(thread.metadata ?? {}), ...patch },
    });
  }
}

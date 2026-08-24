import type { FeedbackAdapter } from '@assistant-ui/react';
import { FEEDBACK_KEY, FEEDBACK_PATH } from '@/lib/ask-ai/protocol';

const urlByMessageId = new Map<string, string>();
let pending: string | undefined;

export function rememberFeedbackUrl(metadata: unknown): void {
  if (typeof metadata !== 'object' || metadata === null) return;
  const urls = (metadata as { feedback_urls?: Record<string, string> }).feedback_urls;
  pending = urls?.[FEEDBACK_KEY];
}

export function bindFeedbackUrl(values: unknown): void {
  if (!pending) return;
  if (typeof values !== 'object' || values === null) return;

  const messages = (values as { messages?: { id?: string; type?: string }[] }).messages;
  if (!Array.isArray(messages)) return;

  const last = messages.filter((message) => message.type === 'ai').at(-1);
  if (last?.id) urlByMessageId.set(last.id, pending);
}

export function feedbackUrlFor(messageId: string): string | undefined {
  return urlByMessageId.get(messageId);
}

export const feedbackAdapter: FeedbackAdapter = {
  submit({ message, type }) {
    const url = urlByMessageId.get(message.id);
    if (!url) return;

    void fetch(FEEDBACK_PATH, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ url, score: type === 'positive' ? 1 : 0 }),
    }).catch(() => undefined);
  },
};

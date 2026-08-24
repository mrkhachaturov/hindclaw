import type { FeedbackAdapter } from '@assistant-ui/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FEEDBACK_KEY, FEEDBACK_PATH } from '@/lib/ask-ai/protocol';

type Feedback = typeof import('@/lib/ask-ai/feedback');
type Submission = Parameters<FeedbackAdapter['submit']>[0];

const FEEDBACK_URL = 'https://smith.example.net/feedback/abc?token=x';

let feedback: Feedback;
let fetched: ReturnType<typeof vi.fn>;

beforeEach(async () => {
  vi.resetModules();
  fetched = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
  vi.stubGlobal('fetch', fetched);
  feedback = await import('@/lib/ask-ai/feedback');
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function metadata(url: string): unknown {
  return { feedback_urls: { [FEEDBACK_KEY]: url } };
}

function submit(id: string, type: 'positive' | 'negative'): void {
  feedback.feedbackAdapter.submit({ message: { id }, type } as unknown as Submission);
}

function body(): unknown {
  return JSON.parse(fetched.mock.calls[0][1].body);
}

describe('binding a feedback url to a message', () => {
  it('binds the remembered url to the message the agent just wrote', () => {
    feedback.rememberFeedbackUrl(metadata(FEEDBACK_URL));
    feedback.bindFeedbackUrl({
      messages: [
        { id: 'human-1', type: 'human' },
        { id: 'ai-1', type: 'ai' },
      ],
    });

    expect(feedback.feedbackUrlFor('ai-1')).toBe(FEEDBACK_URL);
  });

  it('binds to the last answer when the thread holds several', () => {
    feedback.rememberFeedbackUrl(metadata(FEEDBACK_URL));
    feedback.bindFeedbackUrl({
      messages: [
        { id: 'ai-1', type: 'ai' },
        { id: 'human-2', type: 'human' },
        { id: 'ai-2', type: 'ai' },
      ],
    });

    expect(feedback.feedbackUrlFor('ai-2')).toBe(FEEDBACK_URL);
    expect(feedback.feedbackUrlFor('ai-1')).toBeUndefined();
  });

  it('leaves a message the visitor asked about unbound', () => {
    feedback.rememberFeedbackUrl(metadata(FEEDBACK_URL));
    feedback.bindFeedbackUrl({
      messages: [
        { id: 'human-1', type: 'human' },
        { id: 'ai-1', type: 'ai' },
      ],
    });

    expect(feedback.feedbackUrlFor('human-1')).toBeUndefined();
  });

  it('knows nothing about a message it never saw', () => {
    expect(feedback.feedbackUrlFor('ai-1')).toBeUndefined();
  });

  it('binds nothing when no url was remembered', () => {
    feedback.bindFeedbackUrl({ messages: [{ id: 'ai-1', type: 'ai' }] });

    expect(feedback.feedbackUrlFor('ai-1')).toBeUndefined();
  });

  it.each([
    ['there are no messages', { messages: undefined }],
    ['messages is not an array', { messages: 'ai-1' }],
    ['there is no ai message', { messages: [{ id: 'human-1', type: 'human' }] }],
    ['the ai message has no id', { messages: [{ type: 'ai' }] }],
    ['the values are null', null],
    ['the values are not an object', 'values'],
  ])('binds nothing when %s', (_name, values) => {
    feedback.rememberFeedbackUrl(metadata(FEEDBACK_URL));
    feedback.bindFeedbackUrl(values);

    expect(feedback.feedbackUrlFor('ai-1')).toBeUndefined();
  });

  it.each([
    ['the metadata is null', null],
    ['the metadata is not an object', 'metadata'],
    ['there are no feedback urls', {}],
    ['no url is filed under our key', { feedback_urls: { other_score: FEEDBACK_URL } }],
  ])('remembers nothing when %s', (_name, given) => {
    feedback.rememberFeedbackUrl(given);
    feedback.bindFeedbackUrl({ messages: [{ id: 'ai-1', type: 'ai' }] });

    expect(feedback.feedbackUrlFor('ai-1')).toBeUndefined();
  });
});

describe('feedbackAdapter', () => {
  beforeEach(() => {
    feedback.rememberFeedbackUrl(metadata(FEEDBACK_URL));
    feedback.bindFeedbackUrl({ messages: [{ id: 'ai-1', type: 'ai' }] });
  });

  it('posts to our own feedback route', () => {
    submit('ai-1', 'positive');

    expect(fetched).toHaveBeenCalledWith(
      FEEDBACK_PATH,
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('scores a thumbs up as one', () => {
    submit('ai-1', 'positive');

    expect(body()).toEqual({ url: FEEDBACK_URL, score: 1 });
  });

  it('scores a thumbs down as zero', () => {
    submit('ai-1', 'negative');

    expect(body()).toEqual({ url: FEEDBACK_URL, score: 0 });
  });

  it('sends json', () => {
    submit('ai-1', 'positive');

    expect(fetched.mock.calls[0][1].headers).toEqual({ 'content-type': 'application/json' });
  });

  it('stays quiet about a message it has no url for', () => {
    submit('ai-unknown', 'positive');

    expect(fetched).not.toHaveBeenCalled();
  });

  it('swallows a failed post', async () => {
    fetched.mockRejectedValue(new Error('offline'));

    expect(() => submit('ai-1', 'positive')).not.toThrow();
    await Promise.resolve();
  });
});

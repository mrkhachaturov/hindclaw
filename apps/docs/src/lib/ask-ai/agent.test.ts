import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  agentUrl,
  assistantId,
  isAllowedRoute,
  isFeedbackUrl,
  isRunStream,
  pageUrl,
  withRunContext,
} from '@/lib/ask-ai/agent';
import { FEEDBACK_KEY, PAGE_HEADER } from '@/lib/ask-ai/protocol';

afterEach(() => {
  vi.unstubAllEnvs();
});

function requestWithPage(page: string): Request {
  return new Request('https://docs.example/api/chat/threads', {
    headers: { [PAGE_HEADER]: page },
  });
}

describe('route allowlist', () => {
  it.each([
    ['POST', 'threads'],
    ['GET', 'threads/abc-123'],
    ['DELETE', 'threads/abc-123'],
    ['GET', 'threads/abc-123/state'],
    ['POST', 'threads/abc-123/history'],
    ['POST', 'threads/abc-123/runs/stream'],
    ['POST', 'threads/abc-123/runs/run-9/cancel'],
  ])('allows %s %s', (method, path) => {
    expect(isAllowedRoute(method, path)).toBe(true);
  });

  it.each([
    ['GET', 'assistants'],
    ['POST', 'assistants/search'],
    ['GET', 'store/items'],
    ['POST', 'runs/crons'],
    ['GET', ''],
    ['POST', 'threads/abc/runs'],
  ])('refuses %s %s', (method, path) => {
    expect(isAllowedRoute(method, path)).toBe(false);
  });

  it('refuses a method the path does not serve', () => {
    expect(isAllowedRoute('DELETE', 'threads')).toBe(false);
    expect(isAllowedRoute('GET', 'threads/abc/runs/stream')).toBe(false);
  });

  it('does not let a traversal reach another endpoint', () => {
    expect(isAllowedRoute('POST', 'threads/../assistants')).toBe(false);
  });
});

describe('isRunStream', () => {
  it('is true only for the streaming run', () => {
    expect(isRunStream('POST', 'threads/abc/runs/stream')).toBe(true);
    expect(isRunStream('POST', 'threads/abc/state')).toBe(false);
    expect(isRunStream('GET', 'threads/abc/runs/stream')).toBe(false);
  });
});

describe('agent configuration', () => {
  it('strips a trailing slash from the agent url', () => {
    vi.stubEnv('LANGGRAPH_API_URL', 'http://agent.svc:8000//');

    expect(agentUrl()).toBe('http://agent.svc:8000');
  });

  it('is undefined when unset', () => {
    vi.stubEnv('LANGGRAPH_API_URL', '');

    expect(agentUrl()).toBeUndefined();
  });

  it('defaults the assistant to ask', () => {
    vi.stubEnv('LANGGRAPH_ASSISTANT_ID', '');

    expect(assistantId()).toBe('ask');
  });
});

describe('pageUrl', () => {
  it('keeps a plain path', () => {
    expect(pageUrl(requestWithPage('/docs/guides/access-control'))).toBe(
      '/docs/guides/access-control',
    );
  });

  it('reduces an absolute url to its path', () => {
    expect(pageUrl(requestWithPage('https://docs.example/docs/x?q=1#frag'))).toBe('/docs/x');
  });

  it('keeps only the path, so another host cannot travel in the header', () => {
    expect(pageUrl(requestWithPage('//evil.example/docs'))).toBe('/docs');
    expect(pageUrl(requestWithPage('https://evil.example/docs/x'))).toBe('/docs/x');
  });

  it('drops a javascript url', () => {
    expect(pageUrl(requestWithPage('javascript:alert(1)'))).toBeUndefined();
  });

  it('is undefined when the header is absent', () => {
    expect(pageUrl(new Request('https://docs.example/api/chat/threads'))).toBeUndefined();
  });
});

describe('isFeedbackUrl', () => {
  it('accepts a feedback url on the configured origin', () => {
    vi.stubEnv('LANGSMITH_URL', 'https://smith.example.net');

    expect(isFeedbackUrl('https://smith.example.net/feedback/abc?token=x')).toBe(true);
  });

  it('refuses another origin', () => {
    vi.stubEnv('LANGSMITH_URL', 'https://smith.example.net');

    expect(isFeedbackUrl('https://evil.example/feedback/abc')).toBe(false);
  });

  it('refuses a non-feedback path on the right origin', () => {
    vi.stubEnv('LANGSMITH_URL', 'https://smith.example.net');

    expect(isFeedbackUrl('https://smith.example.net/api/v1/runs')).toBe(false);
  });

  it('refuses everything when no origin is configured', () => {
    vi.stubEnv('LANGSMITH_URL', '');

    expect(isFeedbackUrl('https://smith.example.net/feedback/abc')).toBe(false);
  });
});

describe('withRunContext', () => {
  it('names the visitor and the page', () => {
    const body = withRunContext({ input: { messages: [] } }, { visitorId: 'v1', page: '/docs/x' });

    expect(body.context).toEqual({ visitor_id: 'v1', page_url: '/docs/x' });
  });

  it('omits the page when there is none', () => {
    const body = withRunContext({}, { visitorId: 'v1' });

    expect(body.context).toEqual({ visitor_id: 'v1' });
  });

  it('never carries a tag, which would halve the index', () => {
    const body = withRunContext({ context: { tag: 'api' } }, { visitorId: 'v1' });

    expect(body.context).not.toHaveProperty('tag');
  });

  it('overrides a visitor the browser tried to name', () => {
    const body = withRunContext({ context: { visitor_id: 'someone-else' } }, { visitorId: 'v1' });

    expect(body.context).toEqual({ visitor_id: 'v1' });
  });

  it('asks for all four stream modes by name', () => {
    const body = withRunContext({ stream_mode: ['messages'] }, { visitorId: 'v1' });

    expect(body.stream_mode).toEqual(['messages', 'updates', 'custom', 'values']);
  });

  it('asks for a feedback url', () => {
    expect(withRunContext({}, { visitorId: 'v1' }).feedback_keys).toEqual([FEEDBACK_KEY]);
  });

  it('keeps the caller input', () => {
    const body = withRunContext({ input: { messages: [{ type: 'human' }] } }, { visitorId: 'v1' });

    expect(body.input).toEqual({ messages: [{ type: 'human' }] });
  });
});

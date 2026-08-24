import { Client } from '@langchain/langgraph-sdk';
import { CHAT_BASE, PAGE_HEADER, SESSION_PATH } from '@/lib/ask-ai/protocol';

let sessionPromise: Promise<void> | null = null;

export function ensureSession(): Promise<void> {
  sessionPromise ??= fetch(SESSION_PATH, { cache: 'no-store', credentials: 'same-origin' })
    .then((response) => {
      if (!response.ok) throw new Error('Unable to start an Ask AI session');
    })
    .catch((error: unknown) => {
      sessionPromise = null;
      throw error;
    });
  return sessionPromise;
}

export function forgetSession(): void {
  sessionPromise = null;
}

export const sessionFetch: typeof fetch = async (input, init) => {
  const template = input instanceof Request || init?.body != null ? new Request(input, init) : null;

  const send = () => {
    const headers = new Headers(template?.headers ?? init?.headers);
    headers.set(PAGE_HEADER, window.location.pathname);
    return template
      ? fetch(template.clone(), { headers })
      : fetch(input, { ...init, headers, credentials: 'same-origin' });
  };

  await ensureSession();
  const response = await send();
  if (response.status !== 401) return response;

  forgetSession();
  await ensureSession();
  return send();
};

function origin(): string {
  return typeof window === 'undefined' ? 'http://localhost' : window.location.origin;
}

export function createAgentClient(): Client {
  return new Client({
    apiUrl: new URL(CHAT_BASE, origin()).href,
    apiKey: null,
    callerOptions: { fetch: sessionFetch },
  });
}

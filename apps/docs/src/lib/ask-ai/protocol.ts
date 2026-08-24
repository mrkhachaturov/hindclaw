export const PAGE_HEADER = 'x-hindclaw-page';
export const FEEDBACK_KEY = 'user_score';
export const SEARCH_EVENT = 'search';
export const ASSISTANT_ID = 'ask';
export const CHAT_BASE = '/api/chat';
export const SESSION_PATH = '/api/anonymous-session';
export const FEEDBACK_PATH = '/api/ask-ai/feedback';

export const STREAM_MODES = ['messages', 'updates', 'custom', 'values'] as const;

export type Source = { title: string; url: string; breadcrumbs?: string };

export type SearchArtifact = { query?: string; sources?: Source[] };

export type SearchProgress = {
  event: typeof SEARCH_EVENT;
  phase: 'start' | 'done' | 'failed';
  query: string;
  found?: number;
};

export function isSearchProgress(data: unknown): data is SearchProgress {
  if (typeof data !== 'object' || data === null) return false;
  const candidate = data as Partial<SearchProgress>;
  return (
    candidate.event === SEARCH_EVENT &&
    typeof candidate.query === 'string' &&
    (candidate.phase === 'start' || candidate.phase === 'done' || candidate.phase === 'failed')
  );
}

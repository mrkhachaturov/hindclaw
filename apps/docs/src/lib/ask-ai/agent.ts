import { ASSISTANT_ID, FEEDBACK_KEY, PAGE_HEADER, STREAM_MODES } from '@/lib/ask-ai/protocol';

const PAGE_PATH_RE = /^\/(?!\/)[\w\-./]*$/;
const RUN_STREAM_RE = /^threads\/[\w-]+\/runs\/stream$/;

const ROUTES: ReadonlyArray<readonly [method: string, pattern: RegExp]> = [
  ['POST', /^threads$/],
  ['POST', /^threads\/search$/],
  ['GET', /^threads\/[\w-]+$/],
  ['PATCH', /^threads\/[\w-]+$/],
  ['DELETE', /^threads\/[\w-]+$/],
  ['GET', /^threads\/[\w-]+\/state$/],
  ['POST', /^threads\/[\w-]+\/history$/],
  ['POST', RUN_STREAM_RE],
  ['POST', /^threads\/[\w-]+\/runs\/[\w-]+\/cancel$/],
];

export function isAllowedRoute(method: string, path: string): boolean {
  return ROUTES.some(([allowed, pattern]) => allowed === method && pattern.test(path));
}

export function isRunStream(method: string, path: string): boolean {
  return method === 'POST' && RUN_STREAM_RE.test(path);
}

export function agentUrl(): string | undefined {
  const url = process.env.LANGGRAPH_API_URL?.trim();
  return url ? url.replace(/\/+$/, '') : undefined;
}

export function assistantId(): string {
  return process.env.LANGGRAPH_ASSISTANT_ID?.trim() || ASSISTANT_ID;
}

export function pageUrl(request: Request): string | undefined {
  const raw = request.headers.get(PAGE_HEADER)?.trim();
  if (!raw) return undefined;

  try {
    const { pathname } = new URL(raw, 'https://hindclaw.invalid');
    return PAGE_PATH_RE.test(pathname) ? pathname : undefined;
  } catch {
    return undefined;
  }
}

export function isFeedbackUrl(url: string): boolean {
  const allowed = process.env.LANGSMITH_URL;
  if (!allowed) return false;

  try {
    const target = new URL(url);
    return target.origin === new URL(allowed).origin && target.pathname.includes('/feedback');
  } catch {
    return false;
  }
}

export function withRunContext(
  body: Record<string, unknown>,
  { visitorId, page }: { visitorId: string; page?: string },
): Record<string, unknown> {
  return {
    ...body,
    assistant_id: assistantId(),
    context: { visitor_id: visitorId, ...(page ? { page_url: page } : {}) },
    stream_mode: [...STREAM_MODES],
    feedback_keys: [FEEDBACK_KEY],
  };
}

import type { APIRoute } from 'astro';
import { readSessionCookie, requireSession } from '@/lib/anonymous-session';
import { agentUrl, isAllowedRoute, isRunStream, pageUrl, withRunContext } from '@/lib/ask-ai/agent';

export const prerender = false;

const STRIPPED = ['content-encoding', 'content-length', 'transfer-encoding', 'connection'];

function runBody(text: string, request: Request, visitorId: string): string | undefined {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text || '{}');
  } catch {
    return undefined;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return undefined;

  const page = pageUrl(request);
  return JSON.stringify(
    withRunContext(parsed as Record<string, unknown>, { visitorId, ...(page ? { page } : {}) }),
  );
}

const handler: APIRoute = async ({ request, params, url }) => {
  const session = await requireSession(request);
  if (session instanceof Response) return session;

  const path = params.path ?? '';
  if (!isAllowedRoute(request.method, path)) {
    return Response.json({ error: 'Not found.' }, { status: 404 });
  }

  const upstream = agentUrl();
  const token = readSessionCookie(request);
  if (!upstream || !token) {
    return Response.json({ error: 'Ask AI is unavailable.' }, { status: 503 });
  }

  let body: string | undefined;
  if (request.method === 'POST' || request.method === 'PATCH') {
    const text = await request.text();
    body = isRunStream(request.method, path) ? runBody(text, request, session.id) : text;
    if (body === undefined) {
      return Response.json({ error: 'Malformed request.' }, { status: 400 });
    }
  }

  const response = await fetch(`${upstream}/${path}${url.search}`, {
    method: request.method,
    headers: {
      authorization: `Bearer ${token}`,
      accept: request.headers.get('accept') ?? '*/*',
      ...(body === undefined ? {} : { 'content-type': 'application/json' }),
    },
    ...(body === undefined ? {} : { body }),
    signal: request.signal,
  });

  const headers = new Headers(response.headers);
  for (const name of STRIPPED) headers.delete(name);
  headers.set('cache-control', 'no-store');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const DELETE = handler;

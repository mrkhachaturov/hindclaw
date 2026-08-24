import type { APIRoute } from 'astro';
import {
  createSessionToken,
  getSession,
  isSameOriginFetch,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  sessionKey,
} from '@/lib/anonymous-session';
import { clientAddress, createFixedWindow, tooManyRequests } from '@/lib/rate-limit';

export const prerender = false;

const ISSUANCE_LIMIT = 30;
const ISSUANCE_WINDOW_MS = 60 * 1000;

const takeIssuance = createFixedWindow(ISSUANCE_LIMIT, ISSUANCE_WINDOW_MS);

const NO_STORE = { 'cache-control': 'no-store' };

export const GET: APIRoute = async (context) => {
  const { request } = context;

  if (!isSameOriginFetch(request)) {
    return Response.json(
      { error: 'Sessions are issued through the site.' },
      { status: 403, headers: NO_STORE },
    );
  }

  let key: string | undefined;
  try {
    key = await sessionKey();
  } catch {
    key = undefined;
  }

  if (!key) {
    return Response.json(
      { error: 'Ask AI is not configured.' },
      { status: 503, headers: NO_STORE },
    );
  }

  if (getSession(request, key)) {
    return new Response(null, { status: 204, headers: NO_STORE });
  }

  const verdict = takeIssuance(clientAddress(request, context.clientAddress));
  if (!verdict.success) return tooManyRequests(verdict.reset);

  const token = createSessionToken({ key });
  const cookie = [
    `${SESSION_COOKIE}=${token}`,
    'Path=/',
    'HttpOnly',
    'SameSite=Lax',
    `Max-Age=${SESSION_TTL_SECONDS}`,
    ...(import.meta.env.PROD ? ['Secure'] : []),
  ].join('; ');

  return new Response(null, {
    status: 204,
    headers: { ...NO_STORE, 'set-cookie': cookie },
  });
};

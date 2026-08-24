import { createHmac, randomUUID, timingSafeEqual } from 'node:crypto';
import { secret } from '@/lib/secrets';

export const SESSION_COOKIE = 'hindclaw_ask_session';
export const SESSION_TTL_SECONDS = 24 * 60 * 60;

const SECRET_NAME = 'ASK_AI_SESSION_SECRET';
const DEV_KEY = 'hindclaw-local-ask-ai-session';
const MIN_ID_LENGTH = 16;
const MAX_ID_LENGTH = 128;

type Payload = { v: 1; id: string; exp: number };

export type AnonymousSession = { id: string; expiresAt: number };

function sign(encoded: string, key: string): string {
  return createHmac('sha256', key).update(encoded).digest('base64url');
}

function matches(actual: string, expected: string): boolean {
  const a = Buffer.from(actual);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function createSessionToken({
  key,
  id = randomUUID(),
  now = Date.now(),
}: {
  key: string;
  id?: string;
  now?: number;
}): string {
  const payload: Payload = { v: 1, id, exp: now + SESSION_TTL_SECONDS * 1000 };
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return `${encoded}.${sign(encoded, key)}`;
}

export function verifySessionToken({
  token,
  key,
  now = Date.now(),
}: {
  token: string;
  key: string;
  now?: number;
}): AnonymousSession | null {
  const [encoded, signature, ...rest] = token.split('.');
  if (!encoded || !signature || rest.length > 0) return null;
  if (!matches(signature, sign(encoded, key))) return null;

  let payload: Partial<Payload>;
  try {
    payload = JSON.parse(Buffer.from(encoded, 'base64url').toString('utf8')) as Partial<Payload>;
  } catch {
    return null;
  }

  const { v, id, exp } = payload;
  if (v !== 1) return null;
  if (typeof id !== 'string' || id.length < MIN_ID_LENGTH || id.length > MAX_ID_LENGTH) return null;
  if (typeof exp !== 'number' || !Number.isFinite(exp) || exp <= now) return null;

  return { id, expiresAt: exp };
}

export function readSessionCookie(request: Request): string | null {
  const header = request.headers.get('cookie');
  if (!header) return null;

  for (const item of header.split(';')) {
    const separator = item.indexOf('=');
    if (separator === -1) continue;
    if (item.slice(0, separator).trim() !== SESSION_COOKIE) continue;
    return item.slice(separator + 1).trim() || null;
  }
  return null;
}

export function isSameOriginFetch(request: Request): boolean {
  return (
    request.headers.get('sec-fetch-mode') === 'cors' &&
    request.headers.get('sec-fetch-site') === 'same-origin'
  );
}

export async function sessionKey(): Promise<string | undefined> {
  const key = (await secret(SECRET_NAME).catch(() => undefined))?.trim();
  if (key) return key;
  return import.meta.env.PROD ? undefined : DEV_KEY;
}

export function getSession(request: Request, key: string): AnonymousSession | null {
  const token = readSessionCookie(request);
  return token ? verifySessionToken({ token, key }) : null;
}

export async function requireSession(request: Request): Promise<AnonymousSession | Response> {
  if (!isSameOriginFetch(request)) {
    return Response.json({ error: 'Ask AI is available through the site.' }, { status: 403 });
  }

  const key = await sessionKey();
  if (!key) {
    return Response.json({ error: 'Ask AI is not configured.' }, { status: 503 });
  }

  const session = getSession(request, key);
  if (!session) {
    return Response.json({ error: 'A valid browser session is required.' }, { status: 401 });
  }
  return session;
}

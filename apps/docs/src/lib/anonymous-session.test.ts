import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/secrets', () => ({ secret: vi.fn() }));

import {
  createSessionToken,
  getSession,
  isSameOriginFetch,
  readSessionCookie,
  requireSession,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  sessionKey,
  verifySessionToken,
} from '@/lib/anonymous-session';
import { secret } from '@/lib/secrets';

const KEY = 'a-signing-key';
const ID = '3f1c8a92-7b6d-4e05-9c31-2a8f6d0b4e77';

function browserRequest(headers: Record<string, string> = {}): Request {
  return new Request('https://docs.example/api/chat/threads', {
    headers: { 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin', ...headers },
  });
}

function withToken(token: string): Request {
  return browserRequest({ cookie: `${SESSION_COOKIE}=${token}` });
}

beforeEach(() => {
  vi.mocked(secret).mockReset();
  vi.mocked(secret).mockResolvedValue(KEY);
});

describe('token round trip', () => {
  it('verifies a token it just signed', () => {
    const token = createSessionToken({ key: KEY, id: ID });

    expect(verifySessionToken({ token, key: KEY })).toEqual({
      id: ID,
      expiresAt: expect.any(Number),
    });
  });

  it('expires the token a day out', () => {
    const now = 1_000_000;
    const token = createSessionToken({ key: KEY, id: ID, now });

    expect(verifySessionToken({ token, key: KEY, now })?.expiresAt).toBe(
      now + SESSION_TTL_SECONDS * 1000,
    );
  });

  it('refuses a token signed with another key', () => {
    const token = createSessionToken({ key: 'someone-elses', id: ID });

    expect(verifySessionToken({ token, key: KEY })).toBeNull();
  });

  it('refuses a token past its expiry', () => {
    const now = 1_000_000;
    const token = createSessionToken({ key: KEY, id: ID, now });

    expect(
      verifySessionToken({ token, key: KEY, now: now + SESSION_TTL_SECONDS * 1000 + 1 }),
    ).toBeNull();
  });

  it('refuses a payload edited to name another visitor', () => {
    const token = createSessionToken({ key: KEY, id: ID });
    const signature = token.split('.')[1];
    const edited = Buffer.from(
      JSON.stringify({ v: 1, id: 'someone-elses-visitor', exp: 9e12 }),
    ).toString('base64url');

    expect(verifySessionToken({ token: `${edited}.${signature}`, key: KEY })).toBeNull();
  });

  it.each([
    ['no separator', 'not-a-token'],
    ['too many segments', 'a.b.c'],
    ['empty', ''],
  ])('refuses a malformed token (%s)', (_name, token) => {
    expect(verifySessionToken({ token, key: KEY })).toBeNull();
  });

  it('refuses an id too short to be random', () => {
    const encoded = Buffer.from(JSON.stringify({ v: 1, id: 'short', exp: 9e12 })).toString(
      'base64url',
    );
    const token = `${encoded}.${createSessionToken({ key: KEY }).split('.')[1]}`;

    expect(verifySessionToken({ token, key: KEY })).toBeNull();
  });
});

describe('reading the cookie', () => {
  it('finds the session among other cookies', () => {
    const request = browserRequest({ cookie: `theme=dark; ${SESSION_COOKIE}=abc; other=1` });

    expect(readSessionCookie(request)).toBe('abc');
  });

  it('returns null when there is no cookie header', () => {
    expect(readSessionCookie(browserRequest())).toBeNull();
  });

  it('returns null when the session cookie is absent', () => {
    expect(readSessionCookie(browserRequest({ cookie: 'theme=dark' }))).toBeNull();
  });
});

describe('same origin fetch', () => {
  it('accepts a cors fetch from our own page', () => {
    expect(isSameOriginFetch(browserRequest())).toBe(true);
  });

  it.each([
    ['a navigation', { 'sec-fetch-mode': 'navigate' }],
    ['another site', { 'sec-fetch-site': 'cross-site' }],
  ])('refuses %s', (_name, headers) => {
    expect(isSameOriginFetch(browserRequest(headers))).toBe(false);
  });

  it('refuses a request with no sec-fetch headers at all', () => {
    expect(isSameOriginFetch(new Request('https://docs.example/api/chat/threads'))).toBe(false);
  });
});

describe('sessionKey', () => {
  it('trims what Infisical returns', async () => {
    vi.mocked(secret).mockResolvedValue(`  ${KEY}\n`);

    expect(await sessionKey()).toBe(KEY);
  });

  it('falls back to a development key when the secret is absent', async () => {
    vi.mocked(secret).mockResolvedValue(undefined);

    expect(await sessionKey()).toBeTypeOf('string');
  });

  it('survives an unreachable secret store', async () => {
    vi.mocked(secret).mockRejectedValue(new Error('unreachable'));

    await expect(sessionKey()).resolves.toBeTypeOf('string');
  });
});

describe('requireSession', () => {
  it('returns the session for a signed cookie from our own page', async () => {
    const token = createSessionToken({ key: KEY, id: ID });

    await expect(requireSession(withToken(token))).resolves.toEqual({
      id: ID,
      expiresAt: expect.any(Number),
    });
  });

  it('answers 403 when the request did not come from the site', async () => {
    const token = createSessionToken({ key: KEY, id: ID });
    const request = new Request('https://docs.example/api/chat/threads', {
      headers: { cookie: `${SESSION_COOKIE}=${token}` },
    });

    const response = await requireSession(request);

    expect(response).toBeInstanceOf(Response);
    expect((response as Response).status).toBe(403);
  });

  it('answers 401 without a cookie', async () => {
    const response = await requireSession(browserRequest());

    expect((response as Response).status).toBe(401);
  });

  it('answers 401 for a forged cookie', async () => {
    const forged = createSessionToken({ key: 'someone-elses', id: ID });

    expect(((await requireSession(withToken(forged))) as Response).status).toBe(401);
  });
});

describe('getSession', () => {
  it('returns null when the cookie is absent', () => {
    expect(getSession(browserRequest(), KEY)).toBeNull();
  });
});

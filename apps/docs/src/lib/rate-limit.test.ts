import { describe, expect, it } from 'vitest';
import { clientAddress, createFixedWindow, tooManyRequests } from '@/lib/rate-limit';

const WINDOW = 60_000;

function requestWith(headers: Record<string, string> = {}): Request {
  return new Request('https://docs.example/api/chat/threads', { headers });
}

describe('createFixedWindow', () => {
  it('lets the first call through', () => {
    const take = createFixedWindow(3, WINDOW);

    expect(take('visitor', 0)).toEqual({ success: true, reset: WINDOW });
  });

  it('lets every call up to the limit through', () => {
    const take = createFixedWindow(3, WINDOW);

    expect([take('visitor', 0), take('visitor', 1), take('visitor', 2)]).toEqual([
      { success: true, reset: WINDOW },
      { success: true, reset: WINDOW },
      { success: true, reset: WINDOW },
    ]);
  });

  it('refuses the call past the limit', () => {
    const take = createFixedWindow(2, WINDOW);
    take('visitor', 0);
    take('visitor', 1);

    expect(take('visitor', 2).success).toBe(false);
  });

  it('keeps refusing once the limit is passed', () => {
    const take = createFixedWindow(1, WINDOW);
    take('visitor', 0);

    expect([take('visitor', 1).success, take('visitor', 2).success]).toEqual([false, false]);
  });

  it('lets the visitor back in after the window passes', () => {
    const take = createFixedWindow(1, WINDOW);
    take('visitor', 0);

    expect(take('visitor', WINDOW)).toEqual({ success: true, reset: WINDOW * 2 });
  });

  it('names the same reset for every call inside one window', () => {
    const take = createFixedWindow(5, WINDOW);
    const first = take('visitor', 0);

    expect(take('visitor', WINDOW - 1).reset).toBe(first.reset);
  });

  it('counts each key on its own', () => {
    const take = createFixedWindow(1, WINDOW);
    take('one', 0);

    expect(take('two', 0).success).toBe(true);
  });

  it('forgets an expired key when another key is taken', () => {
    const take = createFixedWindow(1, WINDOW);
    take('stale', 0);
    take('fresh', WINDOW);

    expect(take('stale', WINDOW)).toEqual({ success: true, reset: WINDOW * 2 });
  });
});

describe('tooManyRequests', () => {
  it('answers 429', () => {
    expect(tooManyRequests(WINDOW, 0).status).toBe(429);
  });

  it('says how long to wait, in whole seconds', () => {
    expect(tooManyRequests(30_000, 0).headers.get('retry-after')).toBe('30');
  });

  it('rounds a partial second up', () => {
    expect(tooManyRequests(1_500, 0).headers.get('retry-after')).toBe('2');
  });

  it.each([
    ['the window already passed', 0, 60_000],
    ['the reset is now', 1_000, 1_000],
  ])('asks for at least a second when %s', (_name, reset, now) => {
    expect(Number(tooManyRequests(reset, now).headers.get('retry-after'))).toBeGreaterThanOrEqual(
      1,
    );
  });

  it('explains itself in the body', async () => {
    await expect(tooManyRequests(WINDOW, 0).json()).resolves.toEqual({
      error: 'Too many requests.',
    });
  });
});

describe('clientAddress', () => {
  it('takes the first hop of a forwarded chain', () => {
    expect(clientAddress(requestWith({ 'x-forwarded-for': '203.0.113.7, 10.0.0.1' }))).toBe(
      '203.0.113.7',
    );
  });

  it('trims the forwarded address', () => {
    expect(clientAddress(requestWith({ 'x-forwarded-for': '  203.0.113.7  ' }))).toBe(
      '203.0.113.7',
    );
  });

  it('prefers the forwarded address over the fallback', () => {
    expect(clientAddress(requestWith({ 'x-forwarded-for': '203.0.113.7' }), '10.0.0.1')).toBe(
      '203.0.113.7',
    );
  });

  it('falls back to the socket address when nothing was forwarded', () => {
    expect(clientAddress(requestWith(), '10.0.0.1')).toBe('10.0.0.1');
  });

  it('falls back when the forwarded header is empty', () => {
    expect(clientAddress(requestWith({ 'x-forwarded-for': '' }), '10.0.0.1')).toBe('10.0.0.1');
  });

  it('settles on unknown when there is no address at all', () => {
    expect(clientAddress(requestWith())).toBe('unknown');
  });
});

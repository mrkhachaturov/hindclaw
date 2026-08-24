export type RateLimitVerdict = { success: boolean; reset: number };

export function createFixedWindow(limit: number, windowMs: number) {
  const windows = new Map<string, { count: number; reset: number }>();

  return function take(key: string, now: number = Date.now()): RateLimitVerdict {
    for (const [scanned, window] of windows) {
      if (window.reset <= now) windows.delete(scanned);
    }

    const current = windows.get(key) ?? { count: 0, reset: now + windowMs };
    current.count += 1;
    windows.set(key, current);

    return { success: current.count <= limit, reset: current.reset };
  };
}

export function tooManyRequests(reset: number, now: number = Date.now()): Response {
  const retryAfter = Math.max(1, Math.ceil((reset - now) / 1000));
  return Response.json(
    { error: 'Too many requests.' },
    { status: 429, headers: { 'retry-after': String(retryAfter) } },
  );
}

export function clientAddress(request: Request, fallback?: string): string {
  const forwarded = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  return forwarded || fallback || 'unknown';
}

const FALLBACK_ORIGIN = 'https://hindclaw.invalid';

export function sameOriginHref(url: string): string {
  if (!url.trim()) return url;

  try {
    const parsed = new URL(url, FALLBACK_ORIGIN);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return url;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return url;
  }
}

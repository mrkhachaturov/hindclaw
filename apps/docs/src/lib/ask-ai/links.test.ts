import { describe, expect, it } from 'vitest';
import { sameOriginHref } from '@/lib/ask-ai/links';

describe('sameOriginHref', () => {
  it('keeps a citation on the site the reader is already on', () => {
    expect(sameOriginHref('https://hindclaw.pro/docs/guides/access-control')).toBe(
      '/docs/guides/access-control',
    );
  });

  it('keeps the anchor so a cited heading still lands', () => {
    expect(sameOriginHref('https://hindclaw.pro/docs/reference/configuration#policies')).toBe(
      '/docs/reference/configuration#policies',
    );
  });

  it('keeps a query string', () => {
    expect(sameOriginHref('https://hindclaw.pro/docs/x?tab=cli')).toBe('/docs/x?tab=cli');
  });

  it('leaves an already relative path alone', () => {
    expect(sameOriginHref('/docs/guides/terraform')).toBe('/docs/guides/terraform');
  });

  it.each([['javascript:alert(1)'], ['mailto:someone@example.com'], ['data:text/html,hi']])(
    'refuses to rewrite a non-http url (%s)',
    (url) => {
      expect(sameOriginHref(url)).toBe(url);
    },
  );

  it('returns anything unparseable untouched', () => {
    expect(sameOriginHref('')).toBe('');
  });
});

import { describe, expect, it } from 'vitest';
import { docsOgImage, docsSourceUrl, SITE } from './site';

describe('docsSourceUrl', () => {
  it('points at the docs content directory on the default branch', () => {
    expect(docsSourceUrl('guides/reflect.mdx')).toBe(
      `${SITE.repo}/blob/main/apps/docs/content/docs/guides/reflect.mdx`,
    );
  });

  it('handles a page at the root of the content directory', () => {
    expect(docsSourceUrl('index.mdx')).toBe(
      `${SITE.repo}/blob/main/apps/docs/content/docs/index.mdx`,
    );
  });
});

describe('docsOgImage', () => {
  it('matches the route emitted for a nested page', () => {
    expect(docsOgImage(['guides', 'reflect'])).toBe('/og/docs/guides/reflect/image.webp');
  });

  it('falls back to the index image when there are no slugs', () => {
    expect(docsOgImage([])).toBe('/og/docs/image.webp');
  });
});

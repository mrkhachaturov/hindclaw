import type { StructuredData } from 'fumadocs-core/mdx-plugins';
import { describe, expect, it } from 'vitest';
import { type IndexedPage, toSearchRecord } from './search-index';

const structured: StructuredData = { headings: [], contents: [] };

const page: IndexedPage = {
  url: '/docs/guides/reflect',
  title: 'Reflect on Recall',
  description: 'Reason over memories.',
  structured,
};

describe('toSearchRecord', () => {
  it('keys the record on the page url', () => {
    const record = toSearchRecord(page, 'docs');

    expect(record._id).toBe('/docs/guides/reflect');
    expect(record.url).toBe('/docs/guides/reflect');
  });

  it('carries the tag so results can be filtered by section', () => {
    expect(toSearchRecord(page, 'docs').tag).toBe('docs');
    expect(toSearchRecord(page, 'api').tag).toBe('api');
  });

  it('names a locale, without which the adapter ignores collection settings', () => {
    expect(toSearchRecord(page, 'docs').locale).toBe('en');
  });

  it('falls back to the url when a page has no title', () => {
    const record = toSearchRecord({ url: '/api/users', structured }, 'api');

    expect(record.title).toBe('/api/users');
  });

  it('allows a page without a description', () => {
    const record = toSearchRecord({ url: '/api/users', title: 'Users', structured }, 'api');

    expect(record.description).toBeUndefined();
  });
});

import type { StructuredData } from 'fumadocs-core/mdx-plugins';
import type { DocumentRecord } from 'typesense-fumadocs-adapter';

export type SearchTag = 'docs' | 'api';

// The adapter applies per-collection settings only to records that name a
// locale, and the embedding field is declared through those settings. One
// locale keeps the collection name unsuffixed.
export const SEARCH_LOCALE = 'en';

export interface IndexedPage {
  url: string;
  title?: string;
  description?: string;
  structured: StructuredData;
}

export function toSearchRecord(page: IndexedPage, tag: SearchTag): DocumentRecord {
  return {
    _id: page.url,
    title: page.title ?? page.url,
    description: page.description,
    url: page.url,
    structured: page.structured,
    tag,
    locale: SEARCH_LOCALE,
  };
}

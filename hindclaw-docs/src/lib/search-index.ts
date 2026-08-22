import type { StructuredData } from 'fumadocs-core/mdx-plugins';
import type { DocumentRecord } from 'typesense-fumadocs-adapter';

export type SearchTag = 'docs' | 'api';

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
  };
}

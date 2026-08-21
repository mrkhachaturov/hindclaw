import type { APIRoute } from 'astro';
import { type StructuredData, structure } from 'fumadocs-core/mdx-plugins';
import type { DocumentRecord } from 'typesense-fumadocs-adapter';
import { apiSource } from '@/lib/api';
import { blogLoader } from '@/lib/blog';
import { source } from '@/lib/source';

type Tag = 'docs' | 'blog' | 'api';

interface IndexedPage {
  url: string;
  data: { title?: string; description?: string };
}

function toRecord(page: IndexedPage, tag: Tag, structured: StructuredData): DocumentRecord {
  return {
    _id: page.url,
    title: page.data.title ?? page.url,
    description: page.data.description,
    url: page.url,
    structured,
    tag,
  };
}

export const GET: APIRoute = () =>
  Response.json([
    ...source
      .getPages()
      .map((page) => toRecord(page, 'docs', structure(page.data._raw.body ?? ''))),
    ...blogLoader
      .getPages()
      .map((page) => toRecord(page, 'blog', structure(page.data._raw.body ?? ''))),
    ...apiSource.getPages().map((page) => toRecord(page, 'api', page.data.structuredData)),
  ] satisfies DocumentRecord[]);

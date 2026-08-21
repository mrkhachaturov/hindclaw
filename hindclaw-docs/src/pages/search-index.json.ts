import type { APIRoute } from 'astro';
import { structure } from 'fumadocs-core/mdx-plugins';
import { apiSource } from '@/lib/api';
import { blogLoader } from '@/lib/blog';
import { toSearchRecord } from '@/lib/search-index';
import { source } from '@/lib/source';

export const GET: APIRoute = () =>
  Response.json([
    ...source.getPages().map((page) =>
      toSearchRecord(
        {
          url: page.url,
          title: page.data.title,
          description: page.data.description,
          structured: structure(page.data._raw.body ?? ''),
        },
        'docs',
      ),
    ),
    ...blogLoader.getPages().map((page) =>
      toSearchRecord(
        {
          url: page.url,
          title: page.data.title,
          description: page.data.description,
          structured: structure(page.data._raw.body ?? ''),
        },
        'blog',
      ),
    ),
    ...apiSource.getPages().map((page) =>
      toSearchRecord(
        {
          url: page.url,
          title: page.data.title,
          description: page.data.description,
          structured: page.data.structuredData,
        },
        'api',
      ),
    ),
  ]);

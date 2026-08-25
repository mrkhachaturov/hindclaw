import type { APIRoute } from 'astro';
import { structure } from 'fumadocs-core/mdx-plugins';
import { toSearchRecord } from '@/lib/search-index';
import { source } from '@/lib/source';

// Docs and API reference only. Blog posts stay out of search on purpose.
export const GET: APIRoute = () =>
  Response.json(
    source.getPages().map((page) =>
      page.type === 'openapi'
        ? toSearchRecord(
            {
              url: page.url,
              title: page.data.title,
              description: page.data.description,
              structured: page.data.structuredData,
            },
            'api',
          )
        : toSearchRecord(
            {
              url: page.url,
              title: page.data.title,
              description: page.data.description,
              structured: structure(page.data._raw.body ?? ''),
            },
            'docs',
          ),
    ),
  );

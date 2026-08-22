import type { APIRoute } from 'astro';
import { buildLlmsFullText } from '@/lib/llms';
import { source } from '@/lib/source';

export const GET: APIRoute = ({ site }) => {
  const pages = source.getPages().map((page) => ({
    url: page.url,
    title: page.data.title,
    body: page.data._raw.body ?? '',
  }));

  return new Response(buildLlmsFullText(pages, String(site)), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};

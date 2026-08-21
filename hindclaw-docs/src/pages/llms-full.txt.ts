import type { APIRoute } from 'astro';
import { SITE } from '@/lib/site';
import { source } from '@/lib/source';

export const GET: APIRoute = ({ site }) => {
  const body = source
    .getPages()
    .map((page) => {
      const url = new URL(page.url, site ?? `https://${SITE.name.toLowerCase()}.pro`);
      return `# ${page.data.title} (${url})\n\n${page.data._raw.body ?? ''}`;
    })
    .join('\n\n');

  return new Response(body, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};

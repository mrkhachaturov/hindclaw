import type { APIRoute } from 'astro';
import { searchDocs } from '@/lib/typesense';

export const prerender = false;

export const GET: APIRoute = async ({ url }) => {
  const query = url.searchParams.get('query')?.trim() ?? '';
  if (!query) return Response.json([]);

  const tag = url.searchParams.get('tag') ?? undefined;

  try {
    return Response.json(await searchDocs(query, tag));
  } catch {
    return Response.json({ error: 'search unavailable' }, { status: 503 });
  }
};

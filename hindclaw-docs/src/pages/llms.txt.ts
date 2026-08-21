import type { APIRoute } from 'astro';
import { llms } from 'fumadocs-core/source';
import { source } from '@/lib/source';

export const GET: APIRoute = () =>
  new Response(llms(source).index(), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });

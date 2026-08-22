import type { APIRoute } from 'astro';
import { source } from '@/lib/source';

interface Props {
  slugs: string[];
}

export function getStaticPaths() {
  return source.getPages().map((page) => ({
    params: { slug: page.slugs.length > 0 ? page.slugs.join('/') : undefined },
    props: { slugs: page.slugs } satisfies Props,
  }));
}

export const GET: APIRoute<Props> = ({ props }) => {
  const page = source.getPage(props.slugs);
  if (!page) {
    return new Response(undefined, { status: 404 });
  }

  const { title, description, _raw } = page.data;
  const body = [`# ${title}`, description, _raw.body].filter(Boolean).join('\n\n');

  return new Response(body, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};

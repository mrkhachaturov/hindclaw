import { type CollectionEntry, getCollection } from 'astro:content';
import { loader, type StaticSource } from 'fumadocs-core/source';

export const blogLoader = loader({
  baseUrl: '/blog',
  source: await createSource(),
});

async function createSource() {
  const out: StaticSource<{
    metaData: never;
    pageData: CollectionEntry<'blog'>['data'] & { _raw: CollectionEntry<'blog'> };
  }> = { files: [] };

  for (const post of await getCollection('blog')) {
    out.files.push({
      type: 'page',
      path: `${post.id}.mdx`,
      data: { ...post.data, _raw: post },
    });
  }

  return out;
}

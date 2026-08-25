import { type CollectionEntry, getCollection } from 'astro:content';
import * as path from 'node:path';
import { type StructuredData, structure } from 'fumadocs-core/mdx-plugins';
import { loader, type StaticSource } from 'fumadocs-core/source';
import { openapi } from './openapi';

const CONTENT_DIR = 'content/docs';

function contentPath(entry: CollectionEntry<'docs'> | CollectionEntry<'meta'>): string {
  if (!entry.filePath) {
    throw new Error(`Content entry ${entry.id} has no file path`);
  }

  return path.relative(CONTENT_DIR, entry.filePath);
}

async function createSource() {
  const out: StaticSource<{
    metaData: CollectionEntry<'meta'>['data'];
    pageData: CollectionEntry<'docs'>['data'] & { _raw: CollectionEntry<'docs'> };
  }> = { files: [] };

  for (const page of await getCollection('docs')) {
    out.files.push({
      type: 'page',
      path: contentPath(page),
      data: { ...page.data, _raw: page },
    });
  }

  for (const meta of await getCollection('meta')) {
    out.files.push({
      type: 'meta',
      path: contentPath(meta),
      data: meta.data,
    });
  }

  return out;
}

export const source = loader(
  {
    docs: await createSource(),
    openapi: await openapi.staticSource({
      baseDir: 'api/(generated)',
      meta: {
        folderStyle: 'separator',
      },
      per: 'tag',
    }),
  },
  {
    baseUrl: '/docs',
    icon: (name) => name,
    plugins: [openapi.loaderPlugin()],
  },
);

export type Page = (typeof source)['$inferPage'];
export type Meta = (typeof source)['$inferMeta'];

export function getStructuredData(entry: CollectionEntry<'docs'>): StructuredData {
  return structure(entry.body ?? '');
}

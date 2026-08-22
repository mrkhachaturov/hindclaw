import * as fs from 'node:fs';
import * as path from 'node:path';
import { Client } from 'typesense';
import type { CollectionFieldSchema } from 'typesense/lib/Typesense/Collection';
import {
  type CustomSettings,
  type DocumentRecord,
  getDefaultCollectionFields,
  sync,
} from 'typesense-fumadocs-adapter';
import { SEARCH_LOCALE } from '../src/lib/search-index.ts';

const host = process.env.PUBLIC_TYPESENSE_HOST;
const collection = process.env.PUBLIC_TYPESENSE_COLLECTION ?? 'hindclaw';
const apiKey = process.env.TYPESENSE_ADMIN_API_KEY;
const embeddingModel = process.env.TYPESENSE_EMBEDDING_MODEL;
const embeddingApiKey = process.env.TYPESENSE_EMBEDDING_API_KEY;

if (!host) {
  console.error('PUBLIC_TYPESENSE_HOST is not set.');
  process.exit(1);
}

if (!apiKey) {
  console.error('TYPESENSE_ADMIN_API_KEY is not set — a search-only key cannot write.');
  process.exit(1);
}

const indexPath = path.resolve('dist/search-index.json');
if (!fs.existsSync(indexPath)) {
  console.error(`${indexPath} not found — run \`astro build\` first.`);
  process.exit(1);
}

const documents = JSON.parse(fs.readFileSync(indexPath, 'utf8')) as DocumentRecord[];

const byTag = documents.reduce<Record<string, number>>((acc, doc) => {
  const tag = doc.tag ?? 'untagged';
  acc[tag] = (acc[tag] ?? 0) + 1;
  return acc;
}, {});

// Declaring the embedding field on the collection the adapter creates lets
// Typesense embed each document during the import. Adding it afterwards
// re-embeds the whole corpus instead, on every deploy.
function embeddingField(model: string, key: string): CollectionFieldSchema {
  return {
    name: 'embedding',
    type: 'float[]',
    optional: true,
    embed: {
      from: ['content'],
      model_config: { model_name: model, api_key: key },
    },
  } as CollectionFieldSchema;
}

// The adapter's DocumentRecord types `tag` as a string while the schema it
// generates declares `string[]`, so every document is rejected with "Field
// `tag` must be an array" — and the adapter logs those rejections without
// failing, leaving an empty collection behind a freshly swapped alias.
const fields: CollectionFieldSchema[] = getDefaultCollectionFields(SEARCH_LOCALE).map((field) =>
  field.name === 'tag' ? ({ ...field, type: 'string' } as CollectionFieldSchema) : field,
);

if (embeddingModel && embeddingApiKey) {
  fields.push(embeddingField(embeddingModel, embeddingApiKey));
}

const localeSettings: Record<string, CustomSettings> = {
  [SEARCH_LOCALE]: { field_definitions: fields },
};

console.log(`Syncing ${documents.length} documents to "${collection}" on ${host}`);
for (const [tag, count] of Object.entries(byTag)) console.log(`  ${tag}: ${count}`);
console.log(
  localeSettings
    ? `  embeddings: ${embeddingModel}`
    : '  embeddings: off — set TYPESENSE_EMBEDDING_MODEL and TYPESENSE_EMBEDDING_API_KEY',
);

const client = new Client({
  nodes: [{ host, port: 443, protocol: 'https' }],
  apiKey,
  connectionTimeoutSeconds: 60 * 15,
});

await sync(client, {
  typesenseCollectionName: collection,
  documents,
  customLocaleCollectionSettings: localeSettings,
});
console.log('Done.');

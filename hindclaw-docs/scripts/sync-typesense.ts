import * as fs from 'node:fs';
import * as path from 'node:path';
import { Client } from 'typesense';
import { sync, type DocumentRecord } from 'typesense-fumadocs-adapter';

const host = process.env.PUBLIC_TYPESENSE_HOST;
const collection = process.env.PUBLIC_TYPESENSE_COLLECTION ?? 'hindclaw_fuma';
const apiKey = process.env.TYPESENSE_ADMIN_API_KEY;

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

console.log(`Syncing ${documents.length} documents to "${collection}" on ${host}`);
for (const [tag, count] of Object.entries(byTag)) console.log(`  ${tag}: ${count}`);

const client = new Client({
  nodes: [{ host, port: 443, protocol: 'https' }],
  apiKey,
  connectionTimeoutSeconds: 60 * 5,
});

await sync(client, { typesenseCollectionName: collection, documents });
console.log('Done.');

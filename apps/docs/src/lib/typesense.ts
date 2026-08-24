import type { SortedResult } from 'fumadocs-core/search';
import { Client } from 'typesense';
import { secret } from '@/lib/secrets';

type Document = {
  objectID: string;
  url: string;
  title: string;
  content: string;
  section?: string;
  section_id?: string;
  breadcrumbs?: string[];
};

type Hit = {
  document: Document;
  highlight?: {
    title?: { snippet?: string };
    searchable_title?: { snippet?: string };
    content?: { snippet?: string };
  };
};

const DEFAULT_PORTS: Record<string, number> = { 'http:': 80, 'https:': 443 };

export function typesenseNode(url: string) {
  const parsed = new URL(url);
  return {
    host: parsed.hostname,
    port: parsed.port ? Number(parsed.port) : (DEFAULT_PORTS[parsed.protocol] ?? 8108),
    protocol: parsed.protocol.replace(':', ''),
  };
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

let client: Client | undefined;
let clientKey: string | undefined;

async function getClient(): Promise<Client> {
  const apiKey = await secret('TYPESENSE_API_KEY');
  if (!apiKey) throw new Error('TYPESENSE_API_KEY is not set');

  if (client && clientKey === apiKey) return client;

  client = new Client({
    nodes: [typesenseNode(required('TYPESENSE_URL'))],
    apiKey,
    connectionTimeoutSeconds: 5,
  });
  clientKey = apiKey;
  return client;
}

function group(hits: Hit[]): SortedResult[] {
  const grouped: SortedResult[] = [];
  const scanned = new Set<string>();

  for (const { document, highlight } of hits) {
    if (!scanned.has(document.url)) {
      scanned.add(document.url);
      grouped.push({
        id: document.url,
        type: 'page',
        breadcrumbs: document.breadcrumbs,
        url: document.url,
        content:
          highlight?.searchable_title?.snippet ?? highlight?.title?.snippet ?? document.title,
      });
    }

    grouped.push({
      id: document.objectID,
      type: document.content === document.section ? 'heading' : 'text',
      url: document.section_id ? `${document.url}#${document.section_id}` : document.url,
      content: highlight?.content?.snippet ?? document.content,
    });
  }

  return grouped;
}

export async function searchDocs(query: string, tag?: string): Promise<SortedResult[]> {
  const collection = process.env.TYPESENSE_COLLECTION ?? 'hindclaw';

  const typesense = await getClient();
  const response = await typesense
    .collections(collection)
    .documents()
    .search({
      q: query,
      query_by: 'searchable_title,content',
      group_by: 'page_id',
      exclude_fields: 'out_of,search_time_ms',
      group_limit: 3,
      limit: 10,
      ...(tag ? { filter_by: `tag:${tag}` } : {}),
    });

  const hits = (response.grouped_hits ?? []).flatMap((entry) => entry.hits) as Hit[];
  return group(hits);
}

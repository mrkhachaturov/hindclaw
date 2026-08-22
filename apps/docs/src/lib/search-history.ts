import { isValidElement, type ReactNode } from 'react';

export interface RecentSearch {
  id: string;
  url: string;
  content: string;
  breadcrumbs?: string[];
}

// fumadocs returns a result's content as Markdown carrying <mark> around the
// words the query matched. History outlives that query, so it keeps the text
// and drops the marks rather than printing them.
export function plainText(node: ReactNode): string {
  if (typeof node === 'string') return node.replaceAll(/<\/?mark>/g, '');
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(plainText).join('');
  if (isValidElement<{ children?: ReactNode }>(node)) return plainText(node.props.children);
  return '';
}

const KEY = 'hindclaw:recent-searches';
const LIMIT = 5;

// The store is writable by anything running on the origin, and `navigate()`
// sanitizes nothing, so a `javascript:` entry would run on click. Only paths
// within the site get in or out.
function isInternalPath(url: unknown): url is string {
  return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//');
}

function read(): RecentSearch[] {
  if (typeof localStorage === 'undefined') return [];

  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (item): item is RecentSearch =>
          isInternalPath(item?.url) && typeof item?.content === 'string',
      )
      .slice(0, LIMIT);
  } catch {
    return [];
  }
}

function write(items: RecentSearch[]): void {
  if (typeof localStorage === 'undefined') return;

  try {
    localStorage.setItem(KEY, JSON.stringify(items.slice(0, LIMIT)));
  } catch {
    // A full or blocked store costs the reader nothing but this list.
  }
}

export function getRecentSearches(): RecentSearch[] {
  return read();
}

export function addRecentSearch(item: RecentSearch): RecentSearch[] {
  if (!isInternalPath(item.url)) return read();

  const next = [item, ...read().filter((prev) => prev.url !== item.url)];
  write(next);
  return next.slice(0, LIMIT);
}

export function removeRecentSearch(url: string): RecentSearch[] {
  const next = read().filter((item) => item.url !== url);
  write(next);
  return next;
}

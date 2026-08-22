import { createElement } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  addRecentSearch,
  getRecentSearches,
  plainText,
  type RecentSearch,
  removeRecentSearch,
} from './search-history';

function stubStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  });
  return store;
}

const hit = (url: string, content = url): RecentSearch => ({ id: url, url, content });

describe('recent searches', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    stubStorage();
  });

  it('returns the newest first', () => {
    addRecentSearch(hit('/docs/a'));
    addRecentSearch(hit('/docs/b'));

    expect(getRecentSearches().map((item) => item.url)).toEqual(['/docs/b', '/docs/a']);
  });

  it('moves a repeat visit back to the top rather than duplicating it', () => {
    addRecentSearch(hit('/docs/a'));
    addRecentSearch(hit('/docs/b'));
    addRecentSearch(hit('/docs/a'));

    expect(getRecentSearches().map((item) => item.url)).toEqual(['/docs/b', '/docs/a'].reverse());
  });

  it('keeps at most five', () => {
    for (const n of [1, 2, 3, 4, 5, 6, 7]) addRecentSearch(hit(`/docs/${n}`));

    const urls = getRecentSearches().map((item) => item.url);
    expect(urls).toHaveLength(5);
    expect(urls[0]).toBe('/docs/7');
    expect(urls).not.toContain('/docs/1');
  });

  it('forgets one entry without touching the rest', () => {
    addRecentSearch(hit('/docs/a'));
    addRecentSearch(hit('/docs/b'));

    expect(removeRecentSearch('/docs/a').map((item) => item.url)).toEqual(['/docs/b']);
    expect(getRecentSearches().map((item) => item.url)).toEqual(['/docs/b']);
  });

  it('carries the breadcrumbs a result was found under', () => {
    addRecentSearch({ ...hit('/docs/a'), breadcrumbs: ['Guides', 'Access control'] });

    expect(getRecentSearches()[0].breadcrumbs).toEqual(['Guides', 'Access control']);
  });

  it('reads nothing rather than throwing when the store holds junk', () => {
    stubStorage({ 'hindclaw:recent-searches': '{not json' });

    expect(getRecentSearches()).toEqual([]);
  });

  it('drops entries that lost the fields the dialog renders', () => {
    stubStorage({
      'hindclaw:recent-searches': JSON.stringify([{ id: 'x' }, hit('/docs/a')]),
    });

    expect(getRecentSearches().map((item) => item.url)).toEqual(['/docs/a']);
  });

  it('refuses anything that is not a path within the site', () => {
    for (const url of ['javascript:alert(1)', 'https://evil.example/x', '//evil.example/x']) {
      addRecentSearch({ id: url, url, content: 'looks harmless' });
    }

    expect(getRecentSearches()).toEqual([]);
  });

  it('drops a planted entry already sitting in the store', () => {
    stubStorage({
      'hindclaw:recent-searches': JSON.stringify([
        { id: 'x', url: 'javascript:alert(1)', content: 'x' },
        hit('/docs/a'),
      ]),
    });

    expect(getRecentSearches().map((item) => item.url)).toEqual(['/docs/a']);
  });

  it('stays quiet where there is no storage at all', () => {
    vi.unstubAllGlobals();
    vi.stubGlobal('localStorage', undefined);

    expect(getRecentSearches()).toEqual([]);
    expect(() => addRecentSearch(hit('/docs/a'))).not.toThrow();
  });

  it('survives a storage that refuses to write', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => '[]',
      setItem: () => {
        throw new Error('QuotaExceededError');
      },
      removeItem: () => {},
    });

    expect(() => addRecentSearch(hit('/docs/a'))).not.toThrow();
  });
});

describe('plainText', () => {
  it('keeps a plain string as it is', () => {
    expect(plainText('Access control')).toBe('Access control');
  });

  it('drops the marks fumadocs wraps the matched words in', () => {
    expect(plainText('<mark>Terra</mark>form Provider')).toBe('Terraform Provider');
    expect(plainText('tells Hindsight <mark>wha</mark>t to focus on')).toBe(
      'tells Hindsight what to focus on',
    );
  });

  it('reads through the mark elements fumadocs wraps matches in', () => {
    const highlighted = createElement('span', null, [
      'Enforce ',
      createElement('mark', { key: 'm' }, 'access'),
      ' control',
    ]);

    expect(plainText(highlighted)).toBe('Enforce access control');
  });

  it('drops what carries no text', () => {
    expect(plainText(null)).toBe('');
    expect(plainText(undefined)).toBe('');
    expect(plainText(createElement('br'))).toBe('');
  });
});

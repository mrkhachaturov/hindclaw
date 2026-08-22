import { describe, expect, it } from 'vitest';
import { buildLlmsFullText, type LlmsPage } from './llms';

const ORIGIN = 'https://hindclaw.pro';

const PAGES: LlmsPage[] = [
  { url: '/docs', title: 'HindClaw', body: 'Start here.' },
  { url: '/docs/guides/reflect', title: 'Reflect on Recall', body: 'Reason over memories.' },
];

describe('buildLlmsFullText', () => {
  it('heads each page with its title and absolute url', () => {
    const text = buildLlmsFullText(PAGES, ORIGIN);

    expect(text).toContain('# HindClaw (https://hindclaw.pro/docs)');
    expect(text).toContain('# Reflect on Recall (https://hindclaw.pro/docs/guides/reflect)');
  });

  it('keeps the body of every page', () => {
    const text = buildLlmsFullText(PAGES, ORIGIN);

    expect(text).toContain('Start here.');
    expect(text).toContain('Reason over memories.');
  });

  it('separates pages with a blank line', () => {
    const text = buildLlmsFullText(PAGES, ORIGIN);

    expect(text).toContain('Start here.\n\n# Reflect on Recall');
  });

  it('returns an empty string when there are no pages', () => {
    expect(buildLlmsFullText([], ORIGIN)).toBe('');
  });

  it('survives a page with an empty body', () => {
    const text = buildLlmsFullText([{ url: '/docs', title: 'HindClaw', body: '' }], ORIGIN);

    expect(text).toBe('# HindClaw (https://hindclaw.pro/docs)\n\n');
  });
});

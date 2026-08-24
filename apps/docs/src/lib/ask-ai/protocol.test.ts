import { describe, expect, it } from 'vitest';
import { isSearchProgress, SEARCH_EVENT } from '@/lib/ask-ai/protocol';

describe('isSearchProgress', () => {
  it('accepts the payload the agent sends when a search starts', () => {
    expect(isSearchProgress({ event: SEARCH_EVENT, phase: 'start', query: 'access control' })).toBe(
      true,
    );
  });

  it.each([
    ['done', { event: 'search', phase: 'done', query: 'access control', found: 4 }],
    ['failed', { event: 'search', phase: 'failed', query: 'access control', found: 0 }],
  ])('accepts the %s phase with a count', (_name, data) => {
    expect(isSearchProgress(data)).toBe(true);
  });

  it('accepts an empty query, which the agent may still report', () => {
    expect(isSearchProgress({ event: 'search', phase: 'start', query: '' })).toBe(true);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['a string', 'search'],
    ['a number', 7],
    ['an array', []],
    ['another event', { event: 'answer', phase: 'start', query: 'x' }],
    ['no event', { phase: 'start', query: 'x' }],
    ['no query', { event: 'search', phase: 'start' }],
    ['a non-string query', { event: 'search', phase: 'start', query: 7 }],
    ['no phase', { event: 'search', query: 'x' }],
    ['an unknown phase', { event: 'search', phase: 'running', query: 'x' }],
  ])('refuses %s', (_name, data) => {
    expect(isSearchProgress(data)).toBe(false);
  });
});

import { describe, it, expect } from 'vitest';
import {
  stripMemoryTags,
  formatMemories,
  prepareRetentionTranscript,
  deriveBankId,
} from './index.js';
import type { MemoryResult } from './types.js';

// ---------------------------------------------------------------------------
// Re-export verification — ensure index.ts re-exports the expected symbols
// ---------------------------------------------------------------------------

describe('index re-exports', () => {
  it('re-exports stripMemoryTags', () => {
    expect(typeof stripMemoryTags).toBe('function');
  });

  it('re-exports formatMemories', () => {
    expect(typeof formatMemories).toBe('function');
  });

  it('re-exports prepareRetentionTranscript', () => {
    expect(typeof prepareRetentionTranscript).toBe('function');
  });

  it('re-exports deriveBankId', () => {
    expect(typeof deriveBankId).toBe('function');
  });
});

// ---------------------------------------------------------------------------
// stripMemoryTags (via re-export from hooks/retain)
// ---------------------------------------------------------------------------

describe('stripMemoryTags', () => {
  it('strips simple hindsight_memories tags', () => {
    const input =
      'User: Hello\n<hindsight_memories>\nRelevant memories here...\n</hindsight_memories>\nAssistant: How can I help?';
    expect(stripMemoryTags(input)).toBe('User: Hello\n\nAssistant: How can I help?');
  });

  it('strips hindsight_context tags', () => {
    const input = 'Before\n<hindsight_context>\nSome data\n</hindsight_context>\nAfter';
    expect(stripMemoryTags(input)).toBe('Before\n\nAfter');
  });

  it('strips multiple hindsight_memories blocks', () => {
    const input =
      'Start\n<hindsight_memories>\nBlock 1\n</hindsight_memories>\nMiddle\n<hindsight_memories>\nBlock 2\n</hindsight_memories>\nEnd';
    expect(stripMemoryTags(input)).toBe('Start\n\nMiddle\n\nEnd');
  });

  it('preserves content without memory tags', () => {
    const input = 'User: Hello\nAssistant: Hi there!';
    expect(stripMemoryTags(input)).toBe(input);
  });
});

// ---------------------------------------------------------------------------
// formatMemories (via re-export from format)
// ---------------------------------------------------------------------------

describe('formatMemories', () => {
  const makeMemoryResult = (overrides: Partial<MemoryResult>): MemoryResult => ({
    id: 'mem-1',
    text: 'default text',
    type: 'world',
    entities: [],
    context: '',
    occurred_start: null,
    occurred_end: null,
    mentioned_at: null,
    document_id: null,
    metadata: null,
    chunk_id: null,
    tags: [],
    ...overrides,
  });

  it('formats memories as a bulleted list', () => {
    const memories: MemoryResult[] = [
      makeMemoryResult({ id: '1', text: 'User prefers dark mode', type: 'world', mentioned_at: '2023-01-01T12:00:00Z' }),
      makeMemoryResult({ id: '2', text: 'User is learning Rust', type: 'experience', mentioned_at: null }),
    ];
    const output = formatMemories(memories);
    expect(output).toBe('- User prefers dark mode [world] (2023-01-01T12:00:00Z)\n\n- User is learning Rust [experience]');
  });

  it('returns empty string for empty memories', () => {
    expect(formatMemories([])).toBe('');
  });
});

// ---------------------------------------------------------------------------
// prepareRetentionTranscript (via re-export from hooks/retain)
// Note: The new signature is (messages, retainRoles) instead of (messages, pluginConfig)
// ---------------------------------------------------------------------------

describe('prepareRetentionTranscript', () => {
  it('filters messages by role', () => {
    const messages = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
      { role: 'system', content: 'System context' },
    ];
    const result = prepareRetentionTranscript(messages, ['user', 'assistant']);
    expect(result).toContain('user: Hello');
    expect(result).toContain('assistant: Hi there');
    expect(result).not.toContain('System context');
  });

  it('strips memory tags from content', () => {
    const messages = [
      { role: 'user', content: 'What is dark mode?' },
      { role: 'assistant', content: '<hindsight_memories>\nUser prefers dark mode\n</hindsight_memories>\nHere is how to enable dark mode.' },
    ];
    const result = prepareRetentionTranscript(messages, ['user', 'assistant']);
    expect(result).not.toContain('<hindsight_memories>');
    expect(result).not.toContain('User prefers dark mode');
    expect(result).toContain('Here is how to enable dark mode.');
  });

  it('returns empty string for empty messages', () => {
    const result = prepareRetentionTranscript([], ['user', 'assistant']);
    expect(result).toBe('');
  });

  it('skips messages whose content becomes empty after tag stripping', () => {
    const messages = [
      { role: 'user', content: 'Real message' },
      { role: 'assistant', content: '<hindsight_memories>\nonly tags\n</hindsight_memories>' },
      { role: 'assistant', content: 'Actual response' },
    ];
    const result = prepareRetentionTranscript(messages, ['user', 'assistant']);
    expect(result).toContain('user: Real message');
    expect(result).toContain('assistant: Actual response');
    // The middle message should be skipped (entirely tags)
    const lines = result.split('\n').filter(l => l.startsWith('assistant:'));
    expect(lines).toHaveLength(1);
  });
});

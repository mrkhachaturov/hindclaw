import { describe, it, expect, vi, beforeEach } from 'vitest';
import { stripMemoryTags, prepareRetentionTranscript, handleRetain } from './retain.js';
import type { HindsightClient } from '../client.js';
import type { ResolvedConfig, PluginConfig, PluginHookAgentContext } from '../types.js';

// ── stripMemoryTags ───────────────────────────────────────────────────

describe('stripMemoryTags', () => {
  it('removes hindsight_memories blocks', () => {
    const input = 'Hello <hindsight_memories>secret memories here</hindsight_memories> world';
    expect(stripMemoryTags(input)).toBe('Hello  world');
  });

  it('removes hindsight_context blocks', () => {
    const input = 'Before <hindsight_context>some context</hindsight_context> after';
    expect(stripMemoryTags(input)).toBe('Before  after');
  });

  it('removes both blocks when both present', () => {
    const input = '<hindsight_memories>mem</hindsight_memories> text <hindsight_context>ctx</hindsight_context>';
    expect(stripMemoryTags(input)).toBe('text');
  });

  it('handles multiline blocks', () => {
    const input = 'Start\n<hindsight_memories>\nline1\nline2\n</hindsight_memories>\nEnd';
    expect(stripMemoryTags(input)).toBe('Start\n\nEnd');
  });

  it('returns unchanged text when no tags present', () => {
    expect(stripMemoryTags('plain text')).toBe('plain text');
  });
});

// ── prepareRetentionTranscript ────────────────────────────────────────

describe('prepareRetentionTranscript', () => {
  const messages = [
    { role: 'user', content: 'Hello agent' },
    { role: 'assistant', content: 'Hi there' },
    { role: 'system', content: 'System prompt' },
    { role: 'tool', content: 'Tool result' },
  ];

  it('filters by retainRoles and formats with role prefix', () => {
    const transcript = prepareRetentionTranscript(messages, ['user', 'assistant']);
    expect(transcript).toBe('user: Hello agent\nassistant: Hi there');
  });

  it('includes system and tool roles when specified', () => {
    const transcript = prepareRetentionTranscript(messages, ['user', 'assistant', 'system', 'tool']);
    expect(transcript).toContain('system: System prompt');
    expect(transcript).toContain('tool: Tool result');
  });

  it('strips hindsight_memories tags from content', () => {
    const msgs = [
      { role: 'user', content: 'Question <hindsight_memories>leaked</hindsight_memories>' },
      { role: 'assistant', content: 'Answer' },
    ];
    const transcript = prepareRetentionTranscript(msgs, ['user', 'assistant']);
    expect(transcript).not.toContain('<hindsight_memories>');
    expect(transcript).toContain('user: Question');
  });

  it('skips messages with empty content after stripping', () => {
    const msgs = [
      { role: 'user', content: '<hindsight_memories>only tags</hindsight_memories>' },
      { role: 'assistant', content: 'Response' },
    ];
    const transcript = prepareRetentionTranscript(msgs, ['user', 'assistant']);
    expect(transcript).toBe('assistant: Response');
  });

  it('returns empty string when no messages match roles', () => {
    const transcript = prepareRetentionTranscript(messages, ['tool']);
    expect(transcript).toBe('tool: Tool result');
  });
});

// ── handleRetain ──────────────────────────────────────────────────────

describe('handleRetain', () => {
  let mockRetain: ReturnType<typeof vi.fn>;
  let client: HindsightClient;
  let pluginConfig: PluginConfig;
  let ctx: PluginHookAgentContext;

  beforeEach(() => {
    mockRetain = vi.fn().mockResolvedValue({ message: 'ok', document_id: 'doc1', memory_unit_ids: [] });
    client = { retain: mockRetain } as unknown as HindsightClient;
    pluginConfig = {};
    ctx = {
      agentId: 'r2d2',
      sessionKey: 'test-session',
      messageProvider: 'telegram',
      channelId: 'chan-1',
      senderId: 'user-42',
    };
  });

  const makeEvent = (messages: Array<{ role: string; content: string }>) => ({ messages });

  it('calls client.retain with items[] format', async () => {
    const event = makeEvent([
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'World' },
    ]);
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).toHaveBeenCalledOnce();
    const [bankId, request] = mockRetain.mock.calls[0];
    expect(typeof bankId).toBe('string');
    expect(request.items).toHaveLength(1);
    expect(request.items[0].content).toContain('user: Hello');
    expect(request.items[0].content).toContain('assistant: World');
    expect(request.async).toBe(true);
  });

  it('includes tags, context, and observation_scopes from agentConfig', async () => {
    const event = makeEvent([{ role: 'user', content: 'Hi' }]);
    const agentConfig: ResolvedConfig = {
      retainTags: ['health', 'daily'],
      retainContext: { project: 'astromech', env: 'prod' },
      retainObservationScopes: ['fitness', 'sleep'],
    };

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    const [, request] = mockRetain.mock.calls[0];
    expect(request.items[0].tags).toEqual(['health', 'daily']);
    expect(request.items[0].context).toEqual({ project: 'astromech', env: 'prod' });
    expect(request.items[0].observation_scopes).toEqual(['fitness', 'sleep']);
  });

  it('includes metadata with retained_at, message_count, channel_type, channel_id, sender_id', async () => {
    const event = makeEvent([{ role: 'user', content: 'Test' }]);
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    const [, request] = mockRetain.mock.calls[0];
    const meta = request.items[0].metadata as Record<string, string>;
    expect(meta.retained_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(meta.message_count).toBe('1');
    expect(meta.channel_type).toBe('telegram');
    expect(meta.channel_id).toBe('chan-1');
    expect(meta.sender_id).toBe('user-42');
  });

  it('includes document_id with session key prefix', async () => {
    const event = makeEvent([{ role: 'user', content: 'Test' }]);
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    const [, request] = mockRetain.mock.calls[0];
    expect(request.items[0].document_id).toMatch(/^session-test-session-\d+$/);
  });

  it('skips when autoRetain is false', async () => {
    const event = makeEvent([{ role: 'user', content: 'Hello' }]);
    const agentConfig: ResolvedConfig = { autoRetain: false };

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).not.toHaveBeenCalled();
  });

  it('skips when no messages', async () => {
    const event = { messages: [] };
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).not.toHaveBeenCalled();
  });

  it('skips when messages is undefined', async () => {
    const event = {};
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).not.toHaveBeenCalled();
  });

  it('skips when transcript is empty after role filtering', async () => {
    const event = makeEvent([
      { role: 'system', content: 'System only' },
    ]);
    const agentConfig: ResolvedConfig = { retainRoles: ['user', 'assistant'] };

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).not.toHaveBeenCalled();
  });

  it('reads messages from event.context.sessionEntry.messages when available', async () => {
    const event = {
      context: {
        sessionEntry: {
          messages: [{ role: 'user', content: 'From session entry' }],
        },
      },
    };
    const agentConfig: ResolvedConfig = {};

    await handleRetain(event, ctx, agentConfig, client, pluginConfig);

    expect(mockRetain).toHaveBeenCalledOnce();
    const [, request] = mockRetain.mock.calls[0];
    expect(request.items[0].content).toContain('From session entry');
  });
});

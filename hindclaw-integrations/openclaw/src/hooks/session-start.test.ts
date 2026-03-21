import { describe, it, expect, vi, beforeEach } from 'vitest';
import { handleSessionStart } from './session-start.js';
import { HindsightHttpError } from '../client.js';
import type { HindsightClient } from '../client.js';
import type { ResolvedConfig, MentalModel, RecallResponse, PluginHookAgentContext } from '../types.js';

// ── Helpers ──────────────────────────────────────────────────────────

function makeClient() {
  return {
    getMentalModel: vi.fn<(bankId: string, modelId: string, timeoutMs?: number, ctx?: any) => Promise<MentalModel>>(),
    recall: vi.fn<(bankId: string, request: any, timeoutMs?: number, ctx?: any) => Promise<RecallResponse>>(),
    // Stubs for unused client methods
    httpMode: true,
    retain: vi.fn(),
    reflect: vi.fn(),
    listMentalModels: vi.fn(),
    listTags: vi.fn(),
  } as unknown as HindsightClient;
}

function makeMentalModel(content: string): MentalModel {
  return {
    id: 'model-1',
    bank_id: 'bank-a',
    name: 'Test Model',
    source_query: 'test query',
    content,
    trigger: 'session_start',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
}

function makeRecallResponse(texts: string[]): RecallResponse {
  return {
    results: texts.map((text, i) => ({
      id: `mem-${i}`,
      text,
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
    })),
    entities: null,
    trace: null,
    chunks: null,
  };
}

const baseCtx: PluginHookAgentContext = {
  agentId: 'yoda',
  channelId: 'chan-1',
  senderId: 'user-1',
};

// ── Tests ────────────────────────────────────────────────────────────

describe('handleSessionStart', () => {
  let mockClient: HindsightClient;

  beforeEach(() => {
    mockClient = makeClient();
  });

  it('returns undefined when no _sessionStartModels configured', async () => {
    const config: ResolvedConfig = {};
    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBeUndefined();
  });

  it('returns undefined when _sessionStartModels is empty array', async () => {
    const config: ResolvedConfig = { _sessionStartModels: [] };
    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBeUndefined();
  });

  it('loads a mental model and formats with label', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMentalModel('You are methodical and prefer lists.')
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Communication Style' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBe(
      '<hindsight_context>\n## Communication Style\nYou are methodical and prefer lists.\n</hindsight_context>'
    );
    expect(mockClient.getMentalModel).toHaveBeenCalledWith('bank-a', 'model-1', expect.any(Number), baseCtx);
  });

  it('loads recall results and formats as bullet list with label', async () => {
    (mockClient.recall as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRecallResponse(['Prefers dark mode', 'Uses vim keybindings'])
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'recall', bankId: 'bank-a', query: 'user preferences', label: 'Preferences' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBe(
      '<hindsight_context>\n## Preferences\n- Prefers dark mode\n- Uses vim keybindings\n</hindsight_context>'
    );
    expect(mockClient.recall).toHaveBeenCalledWith('bank-a', {
      query: 'user preferences',
      max_tokens: 256,
      budget: 'low',
    }, expect.any(Number), baseCtx);
  });

  it('assembles multiple models into one hindsight_context block', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMentalModel('Methodical thinker.')
    );
    (mockClient.recall as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRecallResponse(['Likes TypeScript'])
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
        { type: 'recall', bankId: 'bank-a', query: 'tech preferences', label: 'Tech' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBe(
      '<hindsight_context>\n## Style\nMethodical thinker.\n\n## Tech\n- Likes TypeScript\n</hindsight_context>'
    );
  });

  it('skips failed model and returns successful ones (graceful degradation)', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('API error'));
    (mockClient.recall as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRecallResponse(['Dislikes meetings'])
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
        { type: 'recall', bankId: 'bank-a', query: 'work habits', label: 'Work Habits' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBe(
      '<hindsight_context>\n## Work Habits\n- Dislikes meetings\n</hindsight_context>'
    );
  });

  it('returns undefined when all models fail', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('API error'));
    (mockClient.recall as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('timeout'));

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
        { type: 'recall', bankId: 'bank-a', query: 'preferences', label: 'Prefs' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBeUndefined();
  });

  it('returns undefined when mental model has no content', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMentalModel('')
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBeUndefined();
  });

  it('uses custom maxTokens for recall when specified', async () => {
    (mockClient.recall as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRecallResponse(['Note 1'])
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'recall', bankId: 'bank-b', query: 'notes', label: 'Notes', maxTokens: 512 },
      ],
    };

    await handleSessionStart(config, mockClient, baseCtx);
    expect(mockClient.recall).toHaveBeenCalledWith('bank-b', {
      query: 'notes',
      max_tokens: 512,
      budget: 'low',
    }, expect.any(Number), baseCtx);
  });

  it('passes ctx to client methods', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeMentalModel('Test content')
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
      ],
    };

    await handleSessionStart(config, mockClient, baseCtx);
    const callArgs = (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(callArgs[3]).toBe(baseCtx);
  });

  it('handles 403 gracefully without crashing', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockRejectedValue(
      new HindsightHttpError(403, 'Forbidden')
    );
    (mockClient.recall as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeRecallResponse(['Accessible note'])
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Denied Model' },
        { type: 'recall', bankId: 'bank-a', query: 'accessible', label: 'Accessible' },
      ],
    };

    // Should not throw, and should return the accessible model
    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBe(
      '<hindsight_context>\n## Accessible\n- Accessible note\n</hindsight_context>'
    );
  });

  it('returns undefined when all models return 403', async () => {
    (mockClient.getMentalModel as ReturnType<typeof vi.fn>).mockRejectedValue(
      new HindsightHttpError(403, 'Forbidden')
    );

    const config: ResolvedConfig = {
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'bank-a', modelId: 'model-1', label: 'Style' },
      ],
    };

    const result = await handleSessionStart(config, mockClient, baseCtx);
    expect(result).toBeUndefined();
  });
});

import { describe, it, expect } from 'vitest';
import type {
  PluginConfig,
  AgentEntry,
  BankConfig,
  ResolvedConfig,
  SessionStartModelConfig,
  TagGroup,
  RetainItem,
  RetainRequest,
  RetainResponse,
  RecallRequest,
  RecallResponse,
  MemoryResult,
  ReflectRequest,
  ReflectResponse,
  MentalModel,
  BankProfile,
} from './types.js';

describe('types – compile-time checks', () => {
  it('PluginConfig with agents map', () => {
    const cfg: PluginConfig = {
      hindsightApiUrl: 'http://localhost:9077',
      jwtSecret: 'my-secret',
      clientId: 'openclaw',
      apiPort: 9077,
      embedPort: 9078,
      agents: {
        yoda: { bankConfig: 'banks/yoda.json5' },
        r2d2: { bankConfig: 'banks/r2d2.json5' },
      },
    };
    expect(cfg.agents).toBeDefined();
    expect(cfg.agents!['yoda'].bankConfig).toBe('banks/yoda.json5');
  });

  it('PluginConfig with daemon fields', () => {
    const cfg: PluginConfig = {
      embedVersion: '0.5.0',
      embedPackagePath: '/opt/hindsight',
      daemonIdleTimeout: 300,
    };
    expect(cfg.daemonIdleTimeout).toBe(300);
  });

  it('PluginConfig with behavioral defaults', () => {
    const cfg: PluginConfig = {
      autoRecall: true,
      autoRetain: false,
      recallBudget: 'mid',
      recallMaxTokens: 1024,
      recallTypes: ['world', 'experience'],
      recallRoles: ['user', 'assistant'],
      recallTopK: 10,
      recallContextTurns: 3,
      recallMaxQueryChars: 800,
      recallPromptPreamble: 'Recall context:',
      retainRoles: ['user', 'assistant'],
      retainEveryNTurns: 2,
      retainOverlapTurns: 1,
      excludeProviders: ['telegram'],
      debug: true,
      llmProvider: 'openai',
      llmModel: 'gpt-4o-mini',
      llmApiKeyEnv: 'OPENAI_API_KEY',
      dynamicBankGranularity: ['agent', 'channel'],
      dynamicBankId: true,
      bankIdPrefix: 'prod',
    };
    expect(cfg.recallBudget).toBe('mid');
  });

  it('BankConfig with behavioral overrides', () => {
    const bank: BankConfig = {
      autoRecall: false,
      recallBudget: 'high',
      retainRoles: ['user'],
      retainContext: 'telegram context',
      retainObservationScopes: ['health', 'fitness'],
      recallFrom: [{ bankId: 'shared-bank', budget: 'low' }],
    };
    expect(bank.autoRecall).toBe(false);
  });

  it('BankConfig with infrastructure overrides', () => {
    const bank: BankConfig = {
      hindsightApiUrl: 'http://remote:9077',
    };
    expect(bank.hindsightApiUrl).toBe('http://remote:9077');
  });

  it('BankConfig with session start models', () => {
    const bank: BankConfig = {
      sessionStartModels: [
        { type: 'mental_model', bankId: 'yoda', modelId: 'user-profile', label: 'User Profile', roles: ['user'] },
        { type: 'recall', bankId: 'shared', query: 'project status', label: 'Project Status', maxTokens: 512 },
      ],
    };
    expect(bank.sessionStartModels).toHaveLength(2);
  });

  it('BankConfig with reflect fields', () => {
    const bank: BankConfig = {
      reflectOnRecall: true,
      reflectBudget: 'high',
      reflectMaxTokens: 2048,
    };
    expect(bank.reflectOnRecall).toBe(true);
  });

  it('TagGroup compound filters', () => {
    const simple: TagGroup = { tags: ['a', 'b'], match: 'any' };
    const andGroup: TagGroup = { and: [{ tags: ['x'], match: 'all' }, { tags: ['y'], match: 'any' }] };
    const orGroup: TagGroup = { or: [{ tags: ['x'], match: 'all' }] };
    const notGroup: TagGroup = { not: { tags: ['secret'], match: 'all' } };
    expect(simple.tags).toEqual(['a', 'b']);
    expect((andGroup as any).and).toHaveLength(2);
    expect((orGroup as any).or).toHaveLength(1);
    expect((notGroup as any).not).toBeDefined();
  });

  it('SessionStartModelConfig both variants', () => {
    const mm: SessionStartModelConfig = {
      type: 'mental_model',
      bankId: 'yoda',
      modelId: 'user-profile',
      label: 'User Profile',
      roles: ['user'],
    };
    const recall: SessionStartModelConfig = {
      type: 'recall',
      bankId: 'shared',
      query: 'current projects',
      label: 'Projects',
      maxTokens: 512,
    };
    expect(mm.type).toBe('mental_model');
    expect(recall.type).toBe('recall');
  });

  it('RetainItem with all optional fields', () => {
    const item: RetainItem = {
      content: 'The user likes TypeScript.',
      timestamp: '2026-03-18T12:00:00Z',
      context: 'During a coding discussion.',
      metadata: { source: 'chat' },
      document_id: 'doc-123',
      entities: ['user', 'TypeScript'],
      tags: ['preference'],
      observation_scopes: ['dev'],
    };
    expect(item.content).toBeDefined();
    expect(item.tags).toEqual(['preference']);
  });

  it('RecallRequest with tag_groups', () => {
    const req: RecallRequest = {
      query: 'What does the user like?',
      types: ['world', 'experience'],
      budget: 'mid',
      max_tokens: 1024,
      query_timestamp: '2026-03-18T12:00:00Z',
      trace: true,
      tag_groups: [
        { tags: ['preference'], match: 'all' },
        { or: [{ tags: ['work'], match: 'any' }, { tags: ['personal'], match: 'any' }] },
      ],
      include: ['entities', 'metadata'],
    };
    expect(req.query).toBeDefined();
    expect(req.tag_groups).toHaveLength(2);
  });

  it('ReflectRequest and ReflectResponse shapes', () => {
    const req: ReflectRequest = {
      query: 'Summarise user preferences',
      budget: 'high',
      max_tokens: 2048,
      response_schema: { type: 'object', properties: {} },
      tag_groups: [{ tags: ['pref'], match: 'all' }],
      include: ['entities'],
    };
    const res: ReflectResponse = {
      text: 'User prefers TypeScript.',
      structured_output: { key: 'val' },
      based_on: ['mem-1', 'mem-2'],
      usage: { prompt_tokens: 100, completion_tokens: 50 },
    };
    expect(req.query).toBeDefined();
    expect(res.text).toBeDefined();
  });

  it('MentalModel shape', () => {
    const model: MentalModel = {
      id: 'mm-1',
      bank_id: 'yoda',
      name: 'user-profile',
      source_query: 'Who is the user?',
      content: 'The user is a developer.',
      trigger: 'on_session_start',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-03-18T00:00:00Z',
    };
    expect(model.id).toBeDefined();
  });

  it('BankProfile shape', () => {
    const profile: BankProfile = {
      bank_id: 'yoda',
      name: 'Yoda',
      created_at: '2026-01-01T00:00:00Z',
    };
    expect(profile.bank_id).toBeDefined();
  });

  it('ResolvedConfig has merged fields', () => {
    const resolved: ResolvedConfig = {
      hindsightApiUrl: 'http://localhost:9077',
      apiPort: 9077,
      embedPort: 9078,
      autoRecall: true,
      autoRetain: true,
      recallBudget: 'mid',
      dynamicBankId: true,
      dynamicBankGranularity: ['agent', 'channel'],
      _recallFrom: [{ bankId: 'shared', budget: 'low' }],
      _sessionStartModels: [
        { type: 'mental_model', bankId: 'yoda', modelId: 'profile', label: 'Profile' },
      ],
      _reflectOnRecall: true,
      _reflectBudget: 'high',
      _reflectMaxTokens: 2048,
    };
    expect(resolved._recallFrom).toBeDefined();
  });

  it('RetainRequest with items array', () => {
    const req: RetainRequest = {
      items: [
        { content: 'fact one' },
        { content: 'fact two', tags: ['important'] },
      ],
      async: true,
    };
    expect(req.items).toHaveLength(2);
  });
});

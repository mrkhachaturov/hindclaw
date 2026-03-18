import { describe, it, expect } from 'vitest';
import { resolveAgentConfig, parseBankConfigFile } from './config.js';

describe('resolveAgentConfig', () => {
  const pluginDefaults = {
    hindsightApiUrl: 'https://default.server',
    recallBudget: 'mid' as const,
    autoRecall: true,
    autoRetain: true,
    recallMaxTokens: 1024,
    llmProvider: 'anthropic',
  };

  it('returns global defaults when no bank config exists', () => {
    const result = resolveAgentConfig('unknown', pluginDefaults, new Map());
    expect(result.recallBudget).toBe('mid');
    expect(result.hindsightApiUrl).toBe('https://default.server');
    expect(result._serverConfig).toBeNull();
    expect(result._recallFrom).toBeUndefined();
    expect(result._sessionStartModels).toBeUndefined();
    expect(result._reflectOnRecall).toBeUndefined();
  });

  it('overrides behavioral fields from bank config', () => {
    const bankConfigs = new Map([['r4p17', {
      retain_mission: 'Extract financial data',
      recallBudget: 'high' as const,
      recallMaxTokens: 2048,
    }]]);
    const result = resolveAgentConfig('r4p17', pluginDefaults, bankConfigs);
    expect(result.recallBudget).toBe('high');
    expect(result.recallMaxTokens).toBe(2048);
    expect(result.autoRecall).toBe(true); // inherited
    expect(result._serverConfig).toEqual({ retain_mission: 'Extract financial data' });
  });

  it('overrides infrastructure fields from bank config', () => {
    const bankConfigs = new Map([['l337', {
      retain_mission: 'Extract health data',
      hindsightApiUrl: 'https://home.server',
      hindsightApiToken: 'home-token',
    }]]);
    const result = resolveAgentConfig('l337', pluginDefaults, bankConfigs);
    expect(result.hindsightApiUrl).toBe('https://home.server');
    expect(result.hindsightApiToken).toBe('home-token');
    expect(result.recallBudget).toBe('mid'); // inherited
  });

  it('shallow merge — arrays fully replaced', () => {
    const defaults = { ...pluginDefaults, recallTypes: ['world', 'experience'] as Array<'world' | 'experience' | 'observation'> };
    const bankConfigs = new Map([['yoda', {
      retain_mission: 'Strategic',
      recallTypes: ['observation'] as Array<'world' | 'experience' | 'observation'>,
    }]]);
    const result = resolveAgentConfig('yoda', defaults, bankConfigs);
    expect(result.recallTypes).toEqual(['observation']);
  });

  it('extracts recallFrom', () => {
    const bankConfigs = new Map([['yoda', {
      retain_mission: 'Strategic',
      recallFrom: [
        { bankId: 'yoda' },
        { bankId: 'r4p17' },
        { bankId: 'bb9e' },
      ],
    }]]);
    const result = resolveAgentConfig('yoda', pluginDefaults, bankConfigs);
    expect(result._recallFrom).toEqual([
      { bankId: 'yoda' },
      { bankId: 'r4p17' },
      { bankId: 'bb9e' },
    ]);
  });

  it('extracts sessionStartModels', () => {
    const bankConfigs = new Map([['k2s0', {
      retain_mission: 'Tasks',
      sessionStartModels: [
        { type: 'mental_model' as const, bankId: 'k2s0', modelId: 'tasks', label: 'Tasks' }
      ],
    }]]);
    const result = resolveAgentConfig('k2s0', pluginDefaults, bankConfigs);
    expect(result._sessionStartModels).toHaveLength(1);
  });

  it('extracts reflect fields', () => {
    const bankConfigs = new Map([['yoda', {
      retain_mission: 'Strategic',
      reflectOnRecall: true,
      reflectBudget: 'high' as const,
      reflectMaxTokens: 512,
    }]]);
    const result = resolveAgentConfig('yoda', pluginDefaults, bankConfigs);
    expect(result._reflectOnRecall).toBe(true);
    expect(result._reflectBudget).toBe('high');
    expect(result._reflectMaxTokens).toBe(512);
  });

  it('collects multiple server-side fields', () => {
    const bankConfigs = new Map([['r4p17', {
      retain_mission: 'Finance',
      observations_mission: 'Trends',
      reflect_mission: 'Analyst',
      disposition_skepticism: 5,
      disposition_literalism: 5,
      disposition_empathy: 1,
      entity_labels: [{ key: 'dept', description: 'Department', type: 'value' as const }],
      directives: [{ name: 'rule1', content: 'Do this' }],
    }]]);
    const result = resolveAgentConfig('r4p17', pluginDefaults, bankConfigs);
    expect(result._serverConfig).toEqual({
      retain_mission: 'Finance',
      observations_mission: 'Trends',
      reflect_mission: 'Analyst',
      disposition_skepticism: 5,
      disposition_literalism: 5,
      disposition_empathy: 1,
      entity_labels: [{ key: 'dept', description: 'Department', type: 'value' }],
      directives: [{ name: 'rule1', content: 'Do this' }],
    });
  });
});

describe('parseBankConfigFile', () => {
  it('parses JSON5 with comments and trailing commas', () => {
    const content = `{
      // This is a comment
      "retain_mission": "test",
      "recallBudget": "high",
    }`;
    const result = parseBankConfigFile(content);
    expect(result.retain_mission).toBe('test');
    expect(result.recallBudget).toBe('high');
  });

  it('throws on invalid JSON5', () => {
    expect(() => parseBankConfigFile('not valid')).toThrow();
  });
});

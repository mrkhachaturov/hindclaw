import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  scanConfigPath, buildChannelIndex, buildMembershipIndex,
  buildStrategyIndex, validateDiscovery, resolvePermissions,
} from './index.js';
import type { DiscoveryResult } from './types.js';

const TEST_DIR = join(tmpdir(), `hoppro-integration-${Date.now()}`);
let discovery: DiscoveryResult;

function writeJson5(path: string, data: any) {
  writeFileSync(path, JSON.stringify(data, null, 2));
}

beforeAll(() => {
  // Build complete test fixture matching spec Section 11
  mkdirSync(join(TEST_DIR, 'banks'), { recursive: true });
  mkdirSync(join(TEST_DIR, 'groups'), { recursive: true });
  mkdirSync(join(TEST_DIR, 'users'), { recursive: true });

  // Users
  writeJson5(join(TEST_DIR, 'users', 'ruben.json5'), {
    displayName: 'Ruben', email: 'ruben@astrateam.ru',
    channels: { telegram: '123456' },
  });
  writeJson5(join(TEST_DIR, 'users', 'vagan.json5'), {
    displayName: 'Vagan',
    channels: { telegram: '789012' },
  });
  writeJson5(join(TEST_DIR, 'users', 'petya.json5'), {
    displayName: 'Petya',
    channels: { telegram: '345678' },
  });

  // Groups
  writeJson5(join(TEST_DIR, 'groups', '_default.json5'), {
    displayName: 'Anonymous', members: [], recall: false, retain: false,
  });
  writeJson5(join(TEST_DIR, 'groups', 'executive.json5'), {
    displayName: 'Executive', members: ['ruben'],
    recall: true, retain: true,
    retainRoles: ['user', 'assistant', 'tool'],
    retainTags: ['role:executive'],
    recallBudget: 'high', recallMaxTokens: 2048,
    recallTagGroups: null, llmModel: 'claude-sonnet-4-5',
  });
  writeJson5(join(TEST_DIR, 'groups', 'dept-head.json5'), {
    displayName: 'Dept Head', members: ['vagan'],
    recall: true, retain: true,
    retainRoles: ['user', 'assistant'],
    retainTags: ['role:dept-head'],
    recallBudget: 'mid', recallMaxTokens: 1024,
    recallTagGroups: [{ not: { tags: ['sensitivity:restricted'], match: 'any_strict' } }],
  });
  writeJson5(join(TEST_DIR, 'groups', 'staff.json5'), {
    displayName: 'Staff', members: ['petya'],
    recall: true, retain: true,
    retainRoles: ['assistant'],
    retainTags: ['role:staff'],
    recallBudget: 'low', recallMaxTokens: 512,
  });
  writeJson5(join(TEST_DIR, 'groups', 'motors.json5'), {
    displayName: 'AstroMotors', members: ['vagan', 'petya'],
    recallTagGroups: [{ tags: ['department:motors'], match: 'any' }],
    retainTags: ['department:motors'],
  });

  // Banks
  writeJson5(join(TEST_DIR, 'banks', 'yoda.json5'), {
    bank_id: 'yoda',
    retain: { strategies: { 'deep-analysis': { topics: ['280304'] } } },
    permissions: {
      groups: {
        executive: { recall: true, retain: true },
        'dept-head': { recall: true, retain: false },
        _default: { recall: false, retain: false },
      },
    },
  });
  writeJson5(join(TEST_DIR, 'banks', 'r4p17.json5'), {
    bank_id: 'r4p17',
    permissions: {
      groups: {
        executive: { recall: true, retain: true },
        'dept-head': { recall: true, retain: true },
        staff: { recall: true, retain: false },
        _default: { recall: false, retain: false },
      },
      users: { vagan: { recallBudget: 'high', recallMaxTokens: 2048 } },
    },
  });

  // Build
  discovery = scanConfigPath(TEST_DIR);
  discovery.channelIndex = buildChannelIndex(discovery.users);
  discovery.membershipIndex = buildMembershipIndex(discovery.groups);
  discovery.strategyIndex = buildStrategyIndex(discovery.banks);
});

afterAll(() => { rmSync(TEST_DIR, { recursive: true, force: true }); });

describe('Spec Section 11 Walkthroughs', () => {
  it('Scenario A: Ruben (executive) on Yoda', () => {
    const r = resolvePermissions('telegram:123456', 'yoda', discovery);
    expect(r.canonicalId).toBe('ruben');
    expect(r.recall).toBe(true);
    expect(r.retain).toBe(true);
    expect(r.recallBudget).toBe('high');
    expect(r.recallMaxTokens).toBe(2048);
    expect(r.recallTagGroups).toBeNull();
    expect(r.retainRoles).toContain('tool');
    expect(r.retainTags).toContain('role:executive');
    expect(r.retainTags).toContain('user:ruben');
  });

  it('Scenario B: Vagan (dept-head+motors) on Yoda', () => {
    const r = resolvePermissions('telegram:789012', 'yoda', discovery);
    expect(r.recall).toBe(true);
    expect(r.retain).toBe(false);
    expect(r.recallBudget).toBe('mid');
    expect(r.recallTagGroups).toHaveLength(2);
    expect(r.retainTags).toContain('role:dept-head');
    expect(r.retainTags).toContain('department:motors');
    expect(r.retainTags).toContain('user:vagan');
  });

  it('Scenario C: Petya (staff+motors) on Yoda — blocked', () => {
    const r = resolvePermissions('telegram:345678', 'yoda', discovery);
    expect(r.recall).toBe(false);
    expect(r.retain).toBe(false);
  });

  it('Scenario D: Anonymous on Yoda — blocked', () => {
    const r = resolvePermissions('telegram:999999', 'yoda', discovery);
    expect(r.isAnonymous).toBe(true);
    expect(r.recall).toBe(false);
    expect(r.retain).toBe(false);
  });

  it('Scenario E: Vagan on R4P17 with user override', () => {
    const r = resolvePermissions('telegram:789012', 'r4p17', discovery);
    expect(r.recall).toBe(true);
    expect(r.retain).toBe(true);
    expect(r.recallBudget).toBe('high');
    expect(r.recallMaxTokens).toBe(2048);
    expect(r.retainTags).toContain('department:motors');
    expect(r.retainTags).toContain('user:vagan');
  });
});

describe('Strategy index', () => {
  it('maps topic to strategy', () => {
    expect(discovery.strategyIndex.get('yoda:280304')).toBe('deep-analysis');
  });
});

describe('Validation', () => {
  it('no critical warnings for valid config', () => {
    const warnings = validateDiscovery(discovery, discovery.membershipIndex);
    expect(warnings.some(w => w.includes('_default'))).toBe(false);
  });
});

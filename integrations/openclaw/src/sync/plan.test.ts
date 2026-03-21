import { describe, it, expect, vi, beforeEach } from 'vitest';
import { planBank } from './plan.js';
import type { BankConfig, Directive } from '../types.js';
import type { HindsightClient } from '../client.js';

// ── Helpers ──────────────────────────────────────────────────────────

function makeDirective(overrides: Partial<Directive> = {}): Directive {
  return {
    id: 'dir-1',
    bank_id: 'test-bank',
    name: 'test-directive',
    content: 'Be concise.',
    priority: 0,
    is_active: true,
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeClient(opts: {
  overrides?: Record<string, unknown>;
  directives?: Directive[];
  directivesFail?: boolean;
}): HindsightClient {
  const mockClient = {
    getBankConfig: vi.fn().mockResolvedValue({
      config: {},
      overrides: opts.overrides ?? {},
    }),
    listDirectives: opts.directivesFail
      ? vi.fn().mockRejectedValue(new Error('network error'))
      : vi.fn().mockResolvedValue(opts.directives ?? []),
  } as unknown as HindsightClient;
  return mockClient;
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('planBank', () => {
  const AGENT_ID = 'yoda';
  const BANK_ID = 'yoda-main';

  // 1. No changes — file matches server
  it('returns hasChanges: false when file matches server', async () => {
    const bankConfig: BankConfig = {
      retain_mission: 'Remember everything.',
    };
    const client = makeClient({
      overrides: { retain_mission: 'Remember everything.' },
      directives: [],
    });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.hasChanges).toBe(false);
    expect(plan.configChanges).toEqual([]);
    expect(plan.directiveChanges).toEqual([]);
    expect(plan.bankId).toBe(BANK_ID);
    expect(plan.agentId).toBe(AGENT_ID);
  });

  // 2. Config field added — file has field, server doesn't
  it('detects config field added', async () => {
    const bankConfig: BankConfig = {
      retain_mission: 'Remember everything.',
    };
    const client = makeClient({ overrides: {}, directives: [] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toEqual([
      { field: 'retain_mission', action: 'add', newValue: 'Remember everything.' },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 3. Config field changed — file and server have different values
  it('detects config field changed', async () => {
    const bankConfig: BankConfig = {
      retain_mission: 'New mission.',
    };
    const client = makeClient({
      overrides: { retain_mission: 'Old mission.' },
      directives: [],
    });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toEqual([
      {
        field: 'retain_mission',
        action: 'change',
        oldValue: 'Old mission.',
        newValue: 'New mission.',
      },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 4. Config field removed — server has it, file doesn't
  it('detects config field removed', async () => {
    const bankConfig: BankConfig = {};
    const client = makeClient({
      overrides: { retain_mission: 'Server mission.' },
      directives: [],
    });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toEqual([
      { field: 'retain_mission', action: 'remove', oldValue: 'Server mission.' },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 5. Entity labels changed — complex array comparison via JSON.stringify
  it('detects entity_labels changed', async () => {
    const fileLabels = [
      { key: 'mood', description: 'User mood', type: 'value' as const, values: [{ value: 'happy', description: 'Happy' }] },
    ];
    const serverLabels = [
      { key: 'mood', description: 'User mood', type: 'value' as const, values: [{ value: 'sad', description: 'Sad' }] },
    ];
    const bankConfig: BankConfig = { entity_labels: fileLabels };
    const client = makeClient({
      overrides: { entity_labels: serverLabels },
      directives: [],
    });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toHaveLength(1);
    expect(plan.configChanges[0]).toEqual({
      field: 'entity_labels',
      action: 'change',
      oldValue: serverLabels,
      newValue: fileLabels,
    });
    expect(plan.hasChanges).toBe(true);
  });

  // 6. Directive created — in file, not on server
  it('detects directive created', async () => {
    const bankConfig: BankConfig = {
      directives: [{ name: 'style', content: 'Be brief.' }],
    };
    const client = makeClient({ overrides: {}, directives: [] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.directiveChanges).toEqual([
      { name: 'style', action: 'create', content: 'Be brief.' },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 7. Directive updated — in both, content differs
  it('detects directive updated', async () => {
    const bankConfig: BankConfig = {
      directives: [{ name: 'style', content: 'New content.' }],
    };
    const serverDir = makeDirective({ id: 'dir-abc', name: 'style', content: 'Old content.' });
    const client = makeClient({ overrides: {}, directives: [serverDir] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.directiveChanges).toEqual([
      { name: 'style', action: 'update', serverId: 'dir-abc', content: 'New content.' },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 8. Directive deleted — on server, not in file
  it('detects directive deleted', async () => {
    const bankConfig: BankConfig = { directives: [] };
    const serverDir = makeDirective({ id: 'dir-xyz', name: 'old-directive', content: 'Obsolete.' });
    const client = makeClient({ overrides: {}, directives: [serverDir] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.directiveChanges).toEqual([
      { name: 'old-directive', action: 'delete', serverId: 'dir-xyz' },
    ]);
    expect(plan.hasChanges).toBe(true);
  });

  // 9. Directive unchanged — same name and content
  it('does not include unchanged directive', async () => {
    const bankConfig: BankConfig = {
      directives: [{ name: 'style', content: 'Same content.' }],
    };
    const serverDir = makeDirective({ name: 'style', content: 'Same content.' });
    const client = makeClient({ overrides: {}, directives: [serverDir] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.directiveChanges).toEqual([]);
    expect(plan.hasChanges).toBe(false);
  });

  // 10. Mixed changes — multiple config + directive changes
  it('handles multiple config and directive changes together', async () => {
    const bankConfig: BankConfig = {
      retain_mission: 'New mission.',
      disposition_skepticism: 0.8,
      directives: [
        { name: 'style', content: 'Updated.' },
        { name: 'new-dir', content: 'Fresh.' },
      ],
    };
    const serverDir = makeDirective({ id: 'dir-1', name: 'style', content: 'Old.' });
    const deletedDir = makeDirective({ id: 'dir-2', name: 'gone', content: 'Gone.' });
    const client = makeClient({
      overrides: { retain_mission: 'Old mission.' },
      directives: [serverDir, deletedDir],
    });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toHaveLength(2);
    expect(plan.configChanges).toContainEqual({
      field: 'retain_mission',
      action: 'change',
      oldValue: 'Old mission.',
      newValue: 'New mission.',
    });
    expect(plan.configChanges).toContainEqual({
      field: 'disposition_skepticism',
      action: 'add',
      newValue: 0.8,
    });

    expect(plan.directiveChanges).toHaveLength(3);
    expect(plan.directiveChanges).toContainEqual({ name: 'style', action: 'update', serverId: 'dir-1', content: 'Updated.' });
    expect(plan.directiveChanges).toContainEqual({ name: 'new-dir', action: 'create', content: 'Fresh.' });
    expect(plan.directiveChanges).toContainEqual({ name: 'gone', action: 'delete', serverId: 'dir-2' });

    expect(plan.hasChanges).toBe(true);
  });

  // 11. Server has no config yet (empty overrides) — all file fields are 'add'
  it('treats all file fields as add when server has empty overrides', async () => {
    const bankConfig: BankConfig = {
      retain_mission: 'Mission A.',
      observations_mission: 'Observe everything.',
      disposition_empathy: 0.9,
    };
    const client = makeClient({ overrides: {}, directives: [] });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.configChanges).toHaveLength(3);
    expect(plan.configChanges.every(c => c.action === 'add')).toBe(true);
    const fields = plan.configChanges.map(c => c.field);
    expect(fields).toContain('retain_mission');
    expect(fields).toContain('observations_mission');
    expect(fields).toContain('disposition_empathy');
    expect(plan.hasChanges).toBe(true);
  });

  // 12. listDirectives fails — treated as empty server directives
  it('treats all file directives as create when listDirectives fails', async () => {
    const bankConfig: BankConfig = {
      directives: [
        { name: 'style', content: 'Be concise.' },
        { name: 'tone', content: 'Be friendly.' },
      ],
    };
    const client = makeClient({ overrides: {}, directivesFail: true });

    const plan = await planBank(AGENT_ID, BANK_ID, bankConfig, client);

    expect(plan.directiveChanges).toHaveLength(2);
    expect(plan.directiveChanges).toContainEqual({ name: 'style', action: 'create', content: 'Be concise.' });
    expect(plan.directiveChanges).toContainEqual({ name: 'tone', action: 'create', content: 'Be friendly.' });
    expect(plan.hasChanges).toBe(true);
  });
});

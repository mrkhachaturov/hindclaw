import type { Client } from '@langchain/langgraph-sdk';
import { describe, expect, it, vi } from 'vitest';
import { createGetCheckpointId } from '@/lib/ask-ai/checkpoints';

type State = {
  values?: { messages?: { id?: unknown }[] };
  checkpoint?: { checkpoint_id?: string };
};

function withHistory(history: State[]) {
  const getHistory = vi.fn().mockResolvedValue(history);
  const client = { threads: { getHistory } } as unknown as Client;

  return { getCheckpointId: createGetCheckpointId(client), getHistory };
}

function state(ids: unknown[], checkpointId: string): State {
  return {
    values: { messages: ids.map((id) => ({ id })) },
    checkpoint: { checkpoint_id: checkpointId },
  };
}

describe('createGetCheckpointId', () => {
  it('finds the checkpoint whose messages are the ones we branch from', async () => {
    const { getCheckpointId } = withHistory([
      state(['human-1', 'ai-1', 'human-2'], 'cp-3'),
      state(['human-1', 'ai-1'], 'cp-2'),
      state(['human-1'], 'cp-1'),
    ]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }, { id: 'ai-1' }])).resolves.toBe(
      'cp-2',
    );
  });

  it('asks the history for the thread it was given', async () => {
    const { getCheckpointId, getHistory } = withHistory([]);

    await getCheckpointId('thread-1', [{ id: 'human-1' }]);

    expect(getHistory).toHaveBeenCalledWith('thread-1');
  });

  it('returns null when the history holds no matching turn', async () => {
    const { getCheckpointId } = withHistory([state(['human-9'], 'cp-9')]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }])).resolves.toBeNull();
  });

  it('returns null for an empty history', async () => {
    const { getCheckpointId } = withHistory([]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }])).resolves.toBeNull();
  });

  it('skips a turn of a different length', async () => {
    const { getCheckpointId } = withHistory([
      state(['human-1', 'ai-1'], 'cp-2'),
      state(['human-1'], 'cp-1'),
    ]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }])).resolves.toBe('cp-1');
  });

  it('skips a turn whose messages carry no ids', async () => {
    const { getCheckpointId } = withHistory([
      state([undefined, undefined], 'cp-unstable'),
      state(['human-1', 'ai-1'], 'cp-2'),
    ]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }, { id: 'ai-1' }])).resolves.toBe(
      'cp-2',
    );
  });

  it('skips a turn where only some ids are strings', async () => {
    const { getCheckpointId } = withHistory([state(['human-1', 7], 'cp-unstable')]);

    await expect(
      getCheckpointId('thread-1', [{ id: 'human-1' }, { id: 'ai-1' }]),
    ).resolves.toBeNull();
  });

  it('refuses to match when our own messages carry no ids', async () => {
    const { getCheckpointId } = withHistory([state(['human-1'], 'cp-1')]);

    await expect(getCheckpointId('thread-1', [{}])).resolves.toBeNull();
  });

  it('skips a turn holding the same ids in another order', async () => {
    const { getCheckpointId } = withHistory([state(['ai-1', 'human-1'], 'cp-swapped')]);

    await expect(
      getCheckpointId('thread-1', [{ id: 'human-1' }, { id: 'ai-1' }]),
    ).resolves.toBeNull();
  });

  it('skips a turn that carries no messages at all', async () => {
    const { getCheckpointId } = withHistory([{ checkpoint: { checkpoint_id: 'cp-empty' } }]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }])).resolves.toBeNull();
  });

  it('returns null when the matching turn names no checkpoint', async () => {
    const { getCheckpointId } = withHistory([{ values: { messages: [{ id: 'human-1' }] } }]);

    await expect(getCheckpointId('thread-1', [{ id: 'human-1' }])).resolves.toBeNull();
  });
});

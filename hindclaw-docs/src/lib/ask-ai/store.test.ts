import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  askAi,
  askAiMode,
  askAiOpen,
  askAiPending,
  hydrateAskAiMode,
  setAskAiMode,
  toggleAskAi,
  toggleAskAiMode,
} from './store';

function stubLocalStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
  });
  return store;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  askAiOpen.set(false);
  askAiMode.set('docked');
  askAiPending.set(null);
});

describe('toggleAskAi', () => {
  it('flips the panel open and shut', () => {
    toggleAskAi();
    expect(askAiOpen.get()).toBe(true);

    toggleAskAi();
    expect(askAiOpen.get()).toBe(false);
  });
});

describe('askAi', () => {
  it('opens the panel with the question queued', () => {
    askAi('What is HindClaw?');

    expect(askAiOpen.get()).toBe(true);
    expect(askAiPending.get()).toBe('What is HindClaw?');
  });
});

describe('setAskAiMode', () => {
  it('remembers the chosen mode', () => {
    const store = stubLocalStorage();
    setAskAiMode('floating');

    expect(askAiMode.get()).toBe('floating');
    expect(store.get('hindclaw:ask-ai-mode')).toBe('floating');
  });

  it('still switches mode when storage is unavailable', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      setItem: () => {
        throw new Error('denied');
      },
    });

    expect(() => setAskAiMode('floating')).not.toThrow();
    expect(askAiMode.get()).toBe('floating');
  });
});

describe('toggleAskAiMode', () => {
  it('swaps between docked and floating', () => {
    stubLocalStorage();

    toggleAskAiMode();
    expect(askAiMode.get()).toBe('floating');

    toggleAskAiMode();
    expect(askAiMode.get()).toBe('docked');
  });
});

describe('hydrateAskAiMode', () => {
  it('restores a floating panel from storage', () => {
    stubLocalStorage({ 'hindclaw:ask-ai-mode': 'floating' });
    hydrateAskAiMode();

    expect(askAiMode.get()).toBe('floating');
  });

  it('stays docked when nothing was stored', () => {
    stubLocalStorage();
    hydrateAskAiMode();

    expect(askAiMode.get()).toBe('docked');
  });

  it('stays docked when storage throws', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('denied');
      },
    });

    expect(() => hydrateAskAiMode()).not.toThrow();
    expect(askAiMode.get()).toBe('docked');
  });
});

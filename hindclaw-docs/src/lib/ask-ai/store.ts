import { atom } from 'nanostores';

export type AskAiMode = 'docked' | 'floating';

const MODE_KEY = 'hindclaw:ask-ai-mode';

export const askAiOpen = atom(false);
export const askAiMode = atom<AskAiMode>('docked');
export const askAiPending = atom<string | null>(null);

export const toggleAskAi = () => askAiOpen.set(!askAiOpen.get());

export const setAskAiMode = (mode: AskAiMode) => {
  askAiMode.set(mode);
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {}
};

export const toggleAskAiMode = () =>
  setAskAiMode(askAiMode.get() === 'docked' ? 'floating' : 'docked');

export const hydrateAskAiMode = () => {
  try {
    if (localStorage.getItem(MODE_KEY) === 'floating') askAiMode.set('floating');
  } catch {}
};

export const askAi = (message: string) => {
  askAiPending.set(message);
  askAiOpen.set(true);
};

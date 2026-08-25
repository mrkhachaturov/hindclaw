import { atom } from 'nanostores';

export type Theme = 'light' | 'dark';

const KEY = 'theme';

const read = (): Theme => {
  try {
    const stored = localStorage.getItem(KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'dark';
  } catch {
    return 'dark';
  }
};

export const theme = atom<Theme>(read());

export const setTheme = (next: Theme) => {
  theme.set(next);
  try {
    localStorage.setItem(KEY, next);
  } catch {}
  document.documentElement.classList.toggle('dark', next === 'dark');
  document.documentElement.style.colorScheme = next;
};

export const toggleTheme = () => setTheme(theme.get() === 'dark' ? 'light' : 'dark');

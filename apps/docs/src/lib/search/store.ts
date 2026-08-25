import { atom } from 'nanostores';

export type SearchCommand = { action: 'open' };

export const searchCommand = atom<SearchCommand | null>(null);

export const openSearch = () => searchCommand.set({ action: 'open' });

import {
  SearchDialog,
  SearchDialogClose,
  SearchDialogContent,
  SearchDialogFooter,
  SearchDialogHeader,
  SearchDialogIcon,
  SearchDialogInput,
  SearchDialogList,
  SearchDialogOverlay,
  type SharedProps,
} from 'fumadocs-ui/components/dialog/search';
import {
  PUBLIC_TYPESENSE_COLLECTION,
  PUBLIC_TYPESENSE_HOST,
  PUBLIC_TYPESENSE_SEARCH_API_KEY,
} from 'astro:env/client';
import { Sparkles } from 'lucide-react';
import { type ReactNode, useCallback } from 'react';
import { Client } from 'typesense';
import { useTypesenseSearch } from 'typesense-fumadocs-adapter/client';
import { askAi } from '@/lib/ask-ai/store';

const client = new Client({
  nodes: [{ host: PUBLIC_TYPESENSE_HOST, port: 443, protocol: 'https' }],
  apiKey: PUBLIC_TYPESENSE_SEARCH_API_KEY,
});

export function TypesenseSearchDialog(props: SharedProps): ReactNode {
  const { search, setSearch, query } = useTypesenseSearch({
    typesenseCollectionName: PUBLIC_TYPESENSE_COLLECTION,
    client,
  });

  const showAskAI = search.trim().length > 0;

  const handleAskAI = useCallback(() => {
    props.onOpenChange(false);
    askAi(search);
  }, [props, search]);

  return (
    <SearchDialog search={search} onSearchChange={setSearch} isLoading={query.isLoading} {...props}>
      <SearchDialogOverlay />
      <SearchDialogContent>
        <SearchDialogHeader>
          <SearchDialogIcon />
          <SearchDialogInput />
          {showAskAI && (
            <button
              type="button"
              onClick={handleAskAI}
              className="hover:bg-accent hidden shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1 text-pink-500 transition-colors sm:flex"
            >
              <Sparkles className="size-3.5" />
              <span className="text-xs font-medium">Ask AI</span>
            </button>
          )}
          <SearchDialogClose />
        </SearchDialogHeader>
        <SearchDialogList items={query.data !== 'empty' ? query.data : null} />
        <SearchDialogFooter>
          <div className="w-full text-right text-xs text-fd-muted-foreground">
            <a href="https://typesense.org" rel="noreferrer noopener" target="_blank">
              Search powered by Typesense
            </a>
          </div>
        </SearchDialogFooter>
      </SearchDialogContent>
    </SearchDialog>
  );
}

import { navigate } from 'astro:transitions/client';
import { useDocsSearch } from 'fumadocs-core/search/client';
import { fetchClient } from 'fumadocs-core/search/client/fetch';
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
  type SearchItemType,
  type SharedProps,
} from 'fumadocs-ui/components/dialog/search';
import { Clock, Sparkles, X } from 'lucide-react';
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { askAi } from '@/lib/ask-ai/store';
import {
  addRecentSearch,
  getRecentSearches,
  plainText,
  type RecentSearch,
  removeRecentSearch,
} from '@/lib/search-history';

const client = fetchClient({ api: '/api/search' });

export function DocsSearchDialog(props: SharedProps): ReactNode {
  const { search, setSearch, query } = useDocsSearch({ client });
  const [recents, setRecents] = useState<RecentSearch[]>([]);
  const { onOpenChange } = props;

  useEffect(() => {
    if (props.open) setRecents(getRecentSearches());
  }, [props.open]);

  const showAskAI = search.trim().length > 0;

  const handleAskAI = useCallback(() => {
    onOpenChange(false);
    askAi(search);
  }, [onOpenChange, search]);

  const handleSelect = useCallback((item: SearchItemType) => {
    if (item.type === 'action') return;

    setRecents(
      addRecentSearch({
        id: item.id,
        url: item.url,
        content: plainText(item.content),
        breadcrumbs: item.breadcrumbs?.map(plainText),
      }),
    );
  }, []);

  // The list takes any item, not only search results, so the history rides in
  // the same list rather than needing a screen of its own.
  const recentItems = useMemo<SearchItemType[]>(
    () =>
      recents.map((item) => ({
        id: `recent:${item.url}`,
        type: 'action',
        onSelect: () => {
          onOpenChange(false);
          void navigate(item.url);
        },
        node: (
          <div className="flex w-full items-center gap-2">
            <Clock className="size-4 shrink-0 text-fd-muted-foreground" />
            <div className="min-w-0 flex-1 text-left">
              <p className="truncate">{item.content}</p>
              {item.breadcrumbs && item.breadcrumbs.length > 0 && (
                <p className="truncate text-xs text-fd-muted-foreground">
                  {item.breadcrumbs.join(' › ')}
                </p>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`Forget ${item.content}`}
              className="shrink-0 text-fd-muted-foreground"
              onClick={(event) => {
                event.stopPropagation();
                setRecents(removeRecentSearch(item.url));
              }}
            >
              <X />
            </Button>
          </div>
        ),
      })),
    [recents, onOpenChange],
  );

  const items = query.data !== 'empty' ? query.data : recentItems.length > 0 ? recentItems : null;

  return (
    <SearchDialog
      search={search}
      onSearchChange={setSearch}
      onSelect={handleSelect}
      isLoading={query.isLoading}
      {...props}
    >
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
        <SearchDialogList items={items} />
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

import { useSearchContext } from 'fumadocs-ui/contexts/search';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import { SearchIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { TypesenseSearchDialog as SearchDialog } from '@/components/search';
import { Button } from '@/components/ui/button';
import { Kbd, KbdGroup } from '@/components/ui/kbd';

export function SearchIsland({ pathname }: { pathname: string }): ReactNode {
  return (
    <RootProvider pathname={pathname} theme={{ enabled: false }} search={{ SearchDialog }}>
      <SearchTrigger />
    </RootProvider>
  );
}

function SearchTrigger() {
  const { setOpenSearch, hotKey } = useSearchContext();

  return (
    <>
      <button
        type="button"
        onClick={() => setOpenSearch(true)}
        className="text-muted-foreground hover:text-foreground flex size-8 cursor-pointer items-center justify-center transition-colors md:hidden"
        aria-label="Search"
      >
        <SearchIcon className="size-4" />
      </button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpenSearch(true)}
        className="text-muted-foreground hover:text-foreground hidden w-48 shrink justify-start gap-2 font-normal md:inline-flex lg:w-56"
      >
        <SearchIcon className="size-3.5 shrink-0" />
        <span className="flex-1 text-left">Search...</span>
        <KbdGroup>
          {hotKey.map((k, i) => (
            <Kbd key={i}>{k.display}</Kbd>
          ))}
        </KbdGroup>
      </Button>
    </>
  );
}

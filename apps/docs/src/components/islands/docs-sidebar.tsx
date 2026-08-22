import { navigate } from 'astro:transitions/client';
import type { AstroProviderProps } from 'fumadocs-core/framework/astro';
import type { Root } from 'fumadocs-core/page-tree';
import { TreeContextProvider } from 'fumadocs-ui/contexts/tree';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import { type ReactNode, useEffect, useMemo } from 'react';
import { Sidebar, SidebarProvider, useSidebar } from '@/components/docs/sidebar';
import { TypesenseSearchDialog as SearchDialog } from '@/components/search';
import { resolveTreeIcons } from '@/lib/page-tree';
import { SITE } from '@/lib/site';

function CollapsedColumnSync() {
  const { collapsed } = useSidebar();

  useEffect(() => {
    const apply = () => {
      const grid = document.getElementById('nd-docs-layout');
      grid?.style.setProperty('--fd-sidebar-col', collapsed ? '0px' : 'var(--fd-sidebar-width)');
      grid?.setAttribute('data-sidebar-collapsed', String(collapsed));
    };

    apply();
    document.addEventListener('astro:after-swap', apply);
    return () => document.removeEventListener('astro:after-swap', apply);
  }, [collapsed]);

  return null;
}

export function DocsSidebar({
  tree,
  pathname,
  params,
}: {
  tree: Root;
  pathname: string;
  params: AstroProviderProps['params'];
}): ReactNode {
  const resolvedTree = useMemo(() => resolveTreeIcons(tree), [tree]);

  return (
    <RootProvider
      pathname={pathname}
      params={params}
      navigate={navigate}
      theme={{ enabled: false }}
      search={{ SearchDialog }}
    >
      <TreeContextProvider tree={resolvedTree}>
        <SidebarProvider>
          <CollapsedColumnSync />
          <Sidebar className="bg-fd-background" />
        </SidebarProvider>
      </TreeContextProvider>
    </RootProvider>
  );
}

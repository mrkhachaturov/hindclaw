import { navigate } from 'astro:transitions/client';
import type { AstroProviderProps } from 'fumadocs-core/framework/astro';
import type { Root } from 'fumadocs-core/page-tree';
import { TreeContextProvider } from 'fumadocs-ui/contexts/tree';
import { getLayoutTabs } from 'fumadocs-ui/layouts/shared';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import { type ReactNode, useEffect, useMemo } from 'react';
import { Sidebar, SidebarProvider, useSidebar } from '@/components/docs/sidebar';
import { resolveTreeIcons } from '@/lib/page-tree';

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
  const tabs = useMemo(() => getLayoutTabs(resolvedTree), [resolvedTree]);

  return (
    <RootProvider
      pathname={pathname}
      params={params}
      navigate={navigate}
      theme={{ enabled: false }}
      // The header island owns the dialog. A second provider here would
      // register the hotkey twice and stack one dialog inside the other.
      search={{ enabled: false }}
    >
      <TreeContextProvider tree={resolvedTree}>
        <SidebarProvider>
          <CollapsedColumnSync />
          <Sidebar className="bg-fd-background" tabs={tabs} />
        </SidebarProvider>
      </TreeContextProvider>
    </RootProvider>
  );
}

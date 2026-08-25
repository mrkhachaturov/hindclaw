import { navigate } from 'astro:transitions/client';
import type { AstroProviderProps } from 'fumadocs-core/framework/astro';
import type { Root } from 'fumadocs-core/page-tree';
import type { TOCItemType } from 'fumadocs-core/toc';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { getLayoutTabs } from 'fumadocs-ui/layouts/shared';
import { TOCPopover, TOCProvider } from 'fumadocs-ui/layouts/docs/page/slots/toc';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import { MoonIcon, SearchIcon, SunIcon } from 'lucide-react';
import { useStore } from '@nanostores/react';
import { type ComponentProps, type ReactNode, useMemo } from 'react';
import {
  MobileSidebar,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/docs/sidebar';
import { buttonVariants } from '@/components/ui/button';
import { resolveTreeIcons } from '@/lib/page-tree';
import { openSearch } from '@/lib/search/store';
import { SITE } from '@/lib/site';
import { theme, toggleTheme } from '@/lib/theme/store';
import { cn } from '@/lib/utils';

function PassThroughContainer({ children }: ComponentProps<'div'>) {
  return <>{children}</>;
}

function NavTitle({ className, ...props }: ComponentProps<'a'>) {
  return (
    <a href="/" className={className} {...props}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="size-[18px]"
      >
        <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z" />
        <path d="M9 13a4.5 4.5 0 0 0 3-4" />
        <path d="M6.003 5.125A3 3 0 0 0 6.401 6.5" />
        <path d="M3.477 10.896a4 4 0 0 1 .585-.396" />
        <path d="M6 18a4 4 0 0 1-1.967-.516" />
        <path d="M12 13h4" />
        <path d="M12 18h6a2 2 0 0 1 2 2v1" />
        <path d="M12 8h8" />
        <path d="M16 8V5a2 2 0 0 1 2-2" />
        <circle cx="16" cy="13" r=".5" />
        <circle cx="18" cy="3" r=".5" />
        <circle cx="20" cy="21" r=".5" />
        <circle cx="20" cy="8" r=".5" />
      </svg>
      {SITE.name}
    </a>
  );
}

function GitHubLink() {
  return (
    <a
      href={SITE.repo}
      rel="noreferrer noopener"
      target="_blank"
      aria-label="GitHub"
      className={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm', className: 'p-2' }))}
    >
      <svg viewBox="0 0 24 24" fill="currentColor" className="size-4.5" aria-hidden="true">
        <path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 0-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.3-3.1-.2-.4-.6-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.7 1.6.2 2.8.1 3.2.8.8 1.3 1.9 1.3 3.2 0 4.6-2.8 5.6-5.5 5.9.5.4.9 1.1.9 2.3v3.3c0 .3.1.7.8.6A12 12 0 0 0 12 .3" />
      </svg>
    </a>
  );
}

function ThemeToggle() {
  const current = useStore(theme);

  return (
    <button
      type="button"
      aria-label="Toggle theme"
      onClick={() => toggleTheme()}
      className={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm', className: 'p-2' }))}
    >
      {current === 'dark' ? <MoonIcon className="size-4.5" /> : <SunIcon className="size-4.5" />}
    </button>
  );
}

function SearchTriggerSm({ className }: { className?: string }) {
  return (
    <button
      type="button"
      aria-label="Search"
      onClick={() => openSearch()}
      className={cn(buttonVariants({ variant: 'ghost', size: 'icon' }), className)}
    >
      <SearchIcon className="size-4.5" />
    </button>
  );
}

export function DocsMobile({
  tree,
  toc,
  pathname,
  params,
}: {
  tree: Root;
  toc: TOCItemType[];
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
      search={{ enabled: false }}
    >
      <DocsLayout
        tree={resolvedTree}
        tabs={false}
        themeSwitch={{ enabled: false }}
        slots={{
          container: PassThroughContainer,
          navTitle: NavTitle,
          searchTrigger: { sm: SearchTriggerSm, full: SearchTriggerSm },
          sidebar: {
            provider: SidebarProvider,
            root: (props) => (
              <MobileSidebar {...props} tabs={tabs} banner={<GitHubLink />} footer={<ThemeToggle />} />
            ),
            trigger: SidebarTrigger,
            useSidebar,
          },
        }}
      >
        <TOCProvider toc={toc}>
          <TOCPopover />
        </TOCProvider>
      </DocsLayout>
    </RootProvider>
  );
}

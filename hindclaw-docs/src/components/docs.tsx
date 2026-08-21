import { navigate } from 'astro:transitions/client';
import type { AstroProviderProps } from 'fumadocs-core/framework/astro';
import type { Root } from 'fumadocs-core/page-tree';
import type { TOCItemType } from 'fumadocs-core/toc';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { DocsBody, DocsPage, DocsTitle } from 'fumadocs-ui/layouts/docs/page';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import { type ReactNode, useMemo } from 'react';
import { PageControls, type PageNeighbour } from '@/components/page-controls';
import { resolveTreeIcons } from '@/lib/page-tree';

export function Docs({
  tree,
  children,
  pathname,
  params,
  title,
  description,
  toc,
  full,
  markdownUrl,
  githubUrl,
  previous,
  next,
}: {
  tree: Root;
  children: ReactNode;
  pathname: string;
  params: AstroProviderProps['params'];
  title: string;
  description?: string;
  toc: TOCItemType[];
  full?: boolean;
  markdownUrl?: string;
  githubUrl?: string;
  previous?: PageNeighbour;
  next?: PageNeighbour;
}): ReactNode {
  const resolvedTree = useMemo(() => resolveTreeIcons(tree), [tree]);

  return (
    <RootProvider
      pathname={pathname}
      params={params}
      navigate={navigate}
      theme={{ enabled: false }}
    >
      <DocsLayout
        tree={resolvedTree}
        nav={{ enabled: false }}
        sidebar={{ className: 'bg-fd-background' }}
        themeSwitch={{ enabled: false }}
        searchToggle={{ enabled: false }}
      >
        <DocsPage
          toc={toc}
          full={full}
          tableOfContent={{ style: 'clerk', enabled: toc.length > 0 }}
        >
          <div className="flex flex-col gap-2 border-b pb-6">
            <div className="flex items-center justify-between gap-4 md:items-start">
              <DocsTitle className="tracking-tight">{title}</DocsTitle>
              <PageControls
                pathname={pathname}
                previous={previous}
                next={next}
                markdownUrl={markdownUrl}
                githubUrl={githubUrl}
              />
            </div>
            {description && (
              <p className="text-lg text-fd-muted-foreground sm:text-balance md:max-w-[80%]">
                {description}
              </p>
            )}
          </div>
          <DocsBody className="prose-gray dark:prose-invert mt-4">{children}</DocsBody>
        </DocsPage>
      </DocsLayout>
    </RootProvider>
  );
}

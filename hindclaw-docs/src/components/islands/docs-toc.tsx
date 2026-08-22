import type { TOCItemType } from 'fumadocs-core/toc';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import type { ReactNode } from 'react';
import { TOC, TOCProvider } from '@/components/docs/toc';
import { TocPageActions } from '@/components/docs/toc-page-actions';

export function DocsToc({
  toc,
  pathname,
  markdownUrl,
  githubUrl,
}: {
  toc: TOCItemType[];
  pathname: string;
  markdownUrl?: string;
  githubUrl?: string;
}): ReactNode {
  return (
    <RootProvider pathname={pathname} theme={{ enabled: false }} search={{ enabled: false }}>
      <TOCProvider toc={toc}>
        <TOC
          footer={
            <TocPageActions markdownUrl={markdownUrl} githubUrl={githubUrl} pathname={pathname} />
          }
        />
      </TOCProvider>
    </RootProvider>
  );
}

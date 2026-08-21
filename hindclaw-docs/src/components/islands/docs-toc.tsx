import type { TOCItemType } from 'fumadocs-core/toc';
import { RootProvider } from 'fumadocs-ui/provider/astro';
import type { ReactNode } from 'react';
import { TOC, TOCProvider } from '@/components/docs/toc';

export function DocsToc({ toc, pathname }: { toc: TOCItemType[]; pathname: string }): ReactNode {
  return (
    <RootProvider pathname={pathname} theme={{ enabled: false }} search={{ enabled: false }}>
      <TOCProvider toc={toc}>
        <TOC />
      </TOCProvider>
    </RootProvider>
  );
}

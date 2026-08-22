'use client';
import { useTranslations } from '@fuma-translate/react';
import * as Base from 'fumadocs-ui/components/toc';
import * as TocClerk from 'fumadocs-ui/components/toc/clerk';
import * as TocDefault from 'fumadocs-ui/components/toc/default';
import { Text } from 'lucide-react';
import type { ComponentProps, ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type TOCProviderProps = Base.TOCProviderProps;

export function TOCProvider(props: TOCProviderProps) {
  return <Base.TOCProvider {...props} />;
}

export type TOCProps = {
  container?: ComponentProps<'div'>;
  /**
   * Custom content in TOC container, before the main TOC
   */
  header?: ReactNode;

  /**
   * Custom content in TOC container, after the main TOC
   */
  footer?: ReactNode;
} & (
  | {
      style?: 'normal';
      list?: TocDefault.TOCItemsProps;
    }
  | {
      style: 'clerk';
      list?: TocClerk.TOCItemsProps;
    }
);

export function TOC({ container, header, footer, style = 'normal', list }: TOCProps) {
  const t = useTranslations({ note: 'table of contents' });
  const items = Base.useTOCItems();
  const { TOCItems, TOCEmpty, TOCItem } = style === 'clerk' ? TocClerk : TocDefault;

  if (items.length === 0 && !header && !footer) {
    return <div id="nd-toc-placeholder" className="hidden xl:layout:[--fd-toc-width:268px]" />;
  }

  return (
    <div
      id="nd-toc"
      {...container}
      className={cn(
        'sticky top-(--fd-docs-row-1) h-[calc(var(--fd-docs-height)-var(--fd-docs-row-1))] flex flex-col [grid-area:toc] w-(--fd-toc-width) pt-12 pe-4 pb-6 xl:layout:[--fd-toc-width:268px] max-xl:hidden',
        container?.className,
      )}
    >
      {header}
      <h3
        id="toc-title"
        className="inline-flex items-center gap-1.5 text-sm text-fd-muted-foreground"
      >
        <Text className="size-4" />
        {t('On this page')}
      </h3>
      <Base.TOCScrollArea className="ms-px">
        <TOCItems {...list}>
          {items.length === 0 && <TOCEmpty />}
          {items.map((item) => (
            <TOCItem key={item.url} item={item} />
          ))}
        </TOCItems>
      </Base.TOCScrollArea>
      {footer}
    </div>
  );
}

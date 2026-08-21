import { cn } from '@/lib/utils';

/**
 * Keyboard hint chips. Ported from assistant-ui's Base UI registry
 * (`packages/ui/src/components/ui/base/kbd.tsx` in `.upstream/assistant-ui`),
 * which is what makes their ⌘K / ⌘I hints legible instead of microscopic.
 */

function Kbd({ className, ...props }: React.ComponentProps<'kbd'>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "text-muted-foreground border-border/60 bg-muted/50 pointer-events-none inline-flex h-4 w-fit min-w-4 items-center justify-center rounded-[3px] border px-1 font-mono text-[10px] select-none",
        "[&_svg:not([class*='size-'])]:size-3",
        className,
      )}
      {...props}
    />
  );
}

function KbdGroup({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <kbd
      data-slot="kbd-group"
      className={cn('inline-flex items-center gap-0.5', className)}
      {...props}
    />
  );
}

export { Kbd, KbdGroup };

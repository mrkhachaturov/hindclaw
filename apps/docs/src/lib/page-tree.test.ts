import type { Root } from 'fumadocs-core/page-tree';
import { isValidElement } from 'react';
import { describe, expect, it } from 'vitest';
import { resolveTreeIcons } from './page-tree';

function tree(): Root {
  return {
    name: 'Docs',
    children: [
      { type: 'page', name: 'Installation', url: '/docs/install', icon: 'Package' },
      {
        type: 'folder',
        name: 'Guides',
        icon: 'BookOpen',
        children: [{ type: 'page', name: 'Reflect', url: '/docs/reflect', icon: 'MessageSquare' }],
      },
    ],
  } as unknown as Root;
}

describe('resolveTreeIcons', () => {
  it('turns a lucide icon name into a react element', () => {
    const resolved = resolveTreeIcons(tree());
    const page = resolved.children[0] as { icon?: unknown };

    expect(isValidElement(page.icon)).toBe(true);
  });

  it('resolves icons inside nested folders', () => {
    const resolved = resolveTreeIcons(tree());
    const folder = resolved.children[1] as { icon?: unknown; children: { icon?: unknown }[] };

    expect(isValidElement(folder.icon)).toBe(true);
    expect(isValidElement(folder.children[0].icon)).toBe(true);
  });

  it('drops an icon name that lucide does not export', () => {
    const input = {
      name: 'Docs',
      children: [{ type: 'page', name: 'X', url: '/x', icon: 'NopeNotAnIcon' }],
    } as unknown as Root;
    const resolved = resolveTreeIcons(input);

    expect((resolved.children[0] as { icon?: unknown }).icon).toBeUndefined();
  });

  it('leaves the input tree untouched', () => {
    const input = tree();
    resolveTreeIcons(input);

    expect((input.children[0] as { icon?: unknown }).icon).toBe('Package');
  });

  it('keeps nodes that carry no icon', () => {
    const input = {
      name: 'Docs',
      children: [{ type: 'page', name: 'X', url: '/x' }],
    } as unknown as Root;
    const resolved = resolveTreeIcons(input);

    expect((resolved.children[0] as { icon?: unknown }).icon).toBeUndefined();
  });
});

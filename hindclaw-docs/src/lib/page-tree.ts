import type { Node, Root } from 'fumadocs-core/page-tree';
import * as lucide from 'lucide-react';
import { createElement, type FC } from 'react';

export function resolveTreeIcons<T extends Root | Node>(node: T): T {
  const next = { ...node } as T & { icon?: unknown; children?: Node[] };

  if (typeof next.icon === 'string') {
    const Icon = lucide[next.icon as keyof typeof lucide] as FC | undefined;
    next.icon = Icon ? createElement(Icon) : undefined;
  }

  if (Array.isArray(next.children)) {
    next.children = next.children.map(resolveTreeIcons);
  }

  return next;
}

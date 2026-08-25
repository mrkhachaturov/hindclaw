// @ts-check
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';
import react from '@astrojs/react';
import mdx from '@astrojs/mdx';
import tailwindcss from '@tailwindcss/vite';
import { unified } from '@astrojs/markdown-remark';
import {
  rehypeCode,
  remarkCodeTab,
  remarkHeading,
  remarkMdxMermaid,
  remarkNpm,
  remarkStructure,
} from 'fumadocs-core/mdx-plugins';
import { visit } from 'unist-util-visit';

function rehypeLineNumbers() {
  return (/** @type {any} */ tree) => {
    visit(tree, 'element', (/** @type {any} */ node) => {
      if (node.tagName === 'pre') node.properties['data-line-numbers'] = true;
    });
  };
}

/** @type {any[]} */
const remarkPlugins = [
  remarkHeading,
  remarkCodeTab,
  remarkNpm,
  // rewrites ```mermaid code fences into the <Mermaid /> component
  remarkMdxMermaid,
  [remarkStructure, { exportAs: 'structuredData' }],
];

/** @type {any[]} */
const rehypePlugins = [rehypeCode, rehypeLineNumbers];

export default defineConfig({
  site: 'https://hindclaw.pro',
  session: false,
  adapter: node({ mode: 'standalone' }),
  experimental: {
    // Docs routes return a `cacheKey` from getStaticPaths, so only pages whose
    // content changed are re-rendered between builds.
    incrementalBuild: true,
  },
  markdown: {
    syntaxHighlight: false,
    processor: unified({ remarkPlugins, rehypePlugins }),
  },
  integrations: [
    react(),
    mdx({
      extendMarkdownConfig: true,
      syntaxHighlight: false,
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
    ssr: {
      // Vite, not Node, must resolve these so their internals are processed.
      noExternal: ['fumadocs-core', 'fumadocs-ui', '@fumadocs/base-ui', 'fumadocs-openapi'],
    },
  },
});

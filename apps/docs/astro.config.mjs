// @ts-check
import { defineConfig, envField } from 'astro/config';
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
const rehypePlugins = [rehypeCode];

export default defineConfig({
  site: 'https://hindclaw.pro',
  session: false,
  env: {
    schema: {
      PUBLIC_TYPESENSE_HOST: envField.string({ context: 'client', access: 'public' }),
      PUBLIC_TYPESENSE_SEARCH_API_KEY: envField.string({ context: 'client', access: 'public' }),
      PUBLIC_TYPESENSE_COLLECTION: envField.string({
        context: 'client',
        access: 'public',
        default: 'hindclaw_fuma',
      }),
    },
  },
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

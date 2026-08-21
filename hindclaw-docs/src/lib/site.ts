export const SITE = {
  name: 'HindClaw',
  repo: 'https://github.com/mrkhachaturov/hindclaw',
  socialCard: '/img/hindclaw-social-card.png',
} as const;

const DOCS_CONTENT_DIR = 'hindclaw-docs/content/docs';

export function docsSourceUrl(pagePath: string): string {
  return `${SITE.repo}/blob/main/${DOCS_CONTENT_DIR}/${pagePath}`;
}

export function docsOgImage(slugs: readonly string[]): string {
  return slugs.length > 0 ? `/og/docs/${slugs.join('/')}/image.webp` : '/og/docs/image.webp';
}

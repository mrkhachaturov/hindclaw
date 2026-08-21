export interface LlmsPage {
  url: string;
  title: string;
  body: string;
}

export function buildLlmsFullText(pages: LlmsPage[], origin: string): string {
  return pages
    .map((page) => `# ${page.title} (${new URL(page.url, origin).href})\n\n${page.body}`)
    .join('\n\n');
}

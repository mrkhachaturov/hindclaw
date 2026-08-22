import { codeToHtml } from 'shiki';

export function highlight(code: string, lang: string) {
  return codeToHtml(code, { lang, theme: 'github-dark' });
}

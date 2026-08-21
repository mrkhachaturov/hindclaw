import defaultMdxComponents from 'fumadocs-ui/mdx';
import Accordion from '@/components/astro/Accordion.astro';
import Accordions from '@/components/astro/Accordions.astro';
import Mermaid from '@/components/astro/Mermaid.astro';
import Tab from '@/components/astro/Tab.astro';
import Tabs from '@/components/astro/Tabs.astro';

export const mdxComponents = {
  ...defaultMdxComponents,
  Accordion,
  Accordions,
  Mermaid,
  Tab,
  Tabs,
};

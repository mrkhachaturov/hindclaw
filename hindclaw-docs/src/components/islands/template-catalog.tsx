import { Braces, Check, Copy, Globe, Search, Terminal } from 'lucide-react';
import { type ReactNode, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

export interface Integration {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  integrations: string[];
  tags: string[];
}

export interface CodeSample {
  key: 'cli' | 'json' | 'curl';
  label: string;
  body: string;
  html: string;
}

export interface TemplateCode {
  install: CodeSample[];
  apply: CodeSample[];
  manifest: CodeSample;
}

function TabIcon({ kind }: { kind: CodeSample['key'] }) {
  if (kind === 'curl') return <Globe data-icon="inline-start" />;
  if (kind === 'json') return <Braces data-icon="inline-start" />;
  return <Terminal data-icon="inline-start" />;
}

function CopyButton({ body }: { body: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(body);
        setCopied(true);
        setTimeout(() => setCopied(false), COPIED_RESET_MS);
      }}
    >
      {copied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
      {copied ? 'Copied' : 'Copy'}
    </Button>
  );
}

function CodeSurface({ html, className }: { html: string; className?: string }) {
  return (
    <div
      className={cn('fd-code border-t p-3 text-xs', className)}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: Shiki output built at build time
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function CodeGroup({ samples }: { samples: CodeSample[] }) {
  return (
    <Tabs defaultValue={samples[0]!.key} className="overflow-hidden rounded-lg border">
      <div className="flex items-center justify-between gap-2 p-2">
        <TabsList>
          {samples.map((sample) => (
            <TabsTrigger key={sample.key} value={sample.key}>
              <TabIcon kind={sample.key} />
              {sample.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>

      {samples.map((sample) => (
        <TabsContent key={sample.key} value={sample.key} className="mt-0">
          <div className="flex items-center justify-end border-t px-2 py-1">
            <CopyButton body={sample.body} />
          </div>
          <CodeSurface html={sample.html} />
        </TabsContent>
      ))}
    </Tabs>
  );
}

const COPIED_RESET_MS = 1_500;

export function TemplateCatalog({
  templates,
  integrations,
  sourceName,
  code,
}: {
  templates: Template[];
  integrations: Integration[];
  sourceName: string;
  code: Record<string, TemplateCode>;
}): ReactNode {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Template | null>(null);

  const byId = useMemo(() => new Map(integrations.map((i) => [i.id, i])), [integrations]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter((t) =>
      [t.name, t.description, t.category, ...t.tags].join(' ').toLowerCase().includes(q),
    );
  }, [templates, query]);

  const active = selected ? code[selected.id] : undefined;

  return (
    <div>
      <div className="relative mt-8 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search templates…"
          className="pl-9"
        />
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {visible.map((template) => (
          <Card
            key={template.id}
            role="button"
            tabIndex={0}
            onClick={() => setSelected(template)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setSelected(template);
              }
            }}
            className="cursor-pointer"
          >
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <CardTitle>{template.name}</CardTitle>
                <Badge variant="outline">{template.category}</Badge>
              </div>
              <CardDescription>{template.description}</CardDescription>
            </CardHeader>

            <CardContent className="flex flex-col gap-4">
              {template.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {template.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}

              {template.integrations.length > 0 && (
                <div className="flex items-center gap-3 border-t pt-4">
                  {template.integrations.map((id) => {
                    const integration = byId.get(id);
                    return integration ? (
                      <span
                        key={id}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground"
                      >
                        <img src={integration.icon} alt="" className="size-4" />
                        {integration.name}
                      </span>
                    ) : null;
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {visible.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No templates match “{query}”.</p>
      )}

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          {selected && active && (
            <>
              <DialogHeader>
                <DialogTitle>{selected.name}</DialogTitle>
                <DialogDescription>{selected.description}</DialogDescription>
                <code className="mt-1 block text-xs text-muted-foreground">
                  {sourceName}/{selected.id}
                </code>
              </DialogHeader>

              <Tabs defaultValue="install" className="mt-2">
                <TabsList>
                  <TabsTrigger value="install">Install</TabsTrigger>
                  <TabsTrigger value="manifest">Manifest</TabsTrigger>
                </TabsList>

                <TabsContent value="install" className="flex flex-col gap-5 pt-4">
                  <div>
                    <h3 className="mb-2 text-sm font-medium">Install to your own scope</h3>
                    <CodeGroup samples={active.install} />
                  </div>
                  <div>
                    <h3 className="mb-2 text-sm font-medium">Apply as a new bank</h3>
                    <CodeGroup samples={active.apply} />
                  </div>
                </TabsContent>

                <TabsContent value="manifest" className="pt-4">
                  <div className="overflow-hidden rounded-lg border">
                    <div className="flex items-center justify-between px-3 py-1">
                      <span className="text-xs text-muted-foreground">manifest.json</span>
                      <CopyButton body={active.manifest.body} />
                    </div>
                    <CodeSurface
                      html={active.manifest.html}
                      className="max-h-[50vh] overflow-y-auto"
                    />
                  </div>
                </TabsContent>
              </Tabs>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

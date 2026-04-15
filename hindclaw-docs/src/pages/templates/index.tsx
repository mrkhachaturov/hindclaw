import React, {useMemo, useState, useCallback, useRef, useLayoutEffect} from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import Link from '@docusaurus/Link';
import CodeBlock from '@theme/CodeBlock';
import {LuSearch, LuX, LuCopy, LuCheck, LuTerminal, LuBraces, LuGlobe} from 'react-icons/lu';
import templatesData from '@site/src/data/templates.json';
import integrationsData from '@site/src/data/integrations.json';
import styles from './index.module.css';

const INTEGRATION_MAP = Object.fromEntries(
  integrationsData.integrations.map((i) => [i.id, {icon: i.icon, name: i.name}]),
);

const CATALOG_EDIT_URL =
  'https://github.com/mrkhachaturov/hindclaw/edit/main/hindclaw-templates/templates.json';
const SOURCE_NAME = templatesData.name;

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  integrations?: string[];
  tags?: string[];
  manifest: Record<string, unknown>;
}

const templates = templatesData.templates as Template[];

const CATEGORIES = ['all', ...Array.from(new Set(templates.map((t) => t.category)))] as const;

const CATEGORY_LABELS: Record<string, string> = {
  all: 'All',
  coding: 'Coding',
  assistant: 'Assistant',
  chat: 'Chat',
};

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Integration icons (mirrors upstream Templates Hub)                        */
/* ═══════════════════════════════════════════════════════════════════════════ */

function IntegrationIcons({ids}: {ids: string[]}) {
  return (
    <div className={styles.integrationIcons}>
      {ids.map((id) => {
        const info = INTEGRATION_MAP[id];
        if (!info?.icon) return null;
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const src = useBaseUrl(info.icon);
        return (
          <img
            key={id}
            src={src}
            alt={info.name}
            title={info.name}
            className={styles.integrationIcon}
          />
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Card grid                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */

function TemplateCard({template, onSelect}: {template: Template; onSelect: () => void}) {
  return (
    <button className={styles.card} onClick={onSelect}>
      <div className={styles.cardHeader}>
        <span className={styles.categoryBadge}>{template.category}</span>
        {template.integrations && template.integrations.length > 0 && (
          <IntegrationIcons ids={template.integrations} />
        )}
      </div>
      <div className={styles.cardBody}>
        <Heading as="h3" className={styles.cardTitle}>{template.name}</Heading>
        <p className={styles.cardDescription}>{template.description}</p>
      </div>
      {template.tags && template.tags.length > 0 && (
        <div className={styles.cardTags}>
          {template.tags.map((tag) => (
            <span key={tag} className={styles.tag}>#{tag}</span>
          ))}
        </div>
      )}
      <div className={styles.cardFooter}>
        <span className={styles.viewLabel}>View manifest &rarr;</span>
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Install tabs                                                              */
/* ═══════════════════════════════════════════════════════════════════════════ */

type TabKey = 'pretty' | 'json' | 'curl';

interface TabBlock {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
  lang: string;
  body: string;
}

function CodeTabs({tabs}: {tabs: TabBlock[]}) {
  const [active, setActive] = useState<TabKey>(tabs[0].key);
  const [copied, setCopied] = useState(false);
  const current = tabs.find((t) => t.key === active) ?? tabs[0];

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(current.body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [current.body]);

  return (
    <div className={styles.codeTabs}>
      <div className={styles.codeTabsHeader}>
        <div className={styles.codeTabsList}>
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`${styles.codeTab} ${active === t.key ? styles.codeTabActive : ''}`}
              onClick={() => setActive(t.key)}>
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
        <button className={styles.codeCopyButton} onClick={handleCopy} aria-label="Copy">
          {copied ? <LuCheck size={14} /> : <LuCopy size={14} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className={styles.codeBlock}>
        <code className={`language-${current.lang}`}>{current.body}</code>
      </pre>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Manifest modal                                                            */
/* ═══════════════════════════════════════════════════════════════════════════ */

type ModalTab = 'install' | 'manifest';

function ManifestModal({template, onClose}: {template: Template; onClose: () => void}) {
  const [tab, setTab] = useState<ModalTab>('install');
  const bodyRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = 0;
    }
  }, [tab]);
  const json = JSON.stringify(template.manifest, null, 2);
  const ref = `${SOURCE_NAME}/${template.id}`;
  const bankId = `${template.id}-bank`;

  const applyTabs: TabBlock[] = [
    {
      key: 'pretty',
      label: 'CLI',
      icon: <LuTerminal size={14} />,
      lang: 'bash',
      body: `hindclaw template apply ${ref} \\\n  --bank-id ${bankId} \\\n  --bank-name "${template.name}"`,
    },
    {
      key: 'json',
      label: 'JSON',
      icon: <LuBraces size={14} />,
      lang: 'bash',
      body: `hindclaw template apply ${ref} \\\n  --bank-id ${bankId} \\\n  --bank-name "${template.name}" \\\n  -o json`,
    },
    {
      key: 'curl',
      label: 'curl',
      icon: <LuGlobe size={14} />,
      lang: 'bash',
      body: `curl -X POST "$HINDCLAW_URL/ext/hindclaw/banks" \\\n  -H "Authorization: Bearer $HINDCLAW_TOKEN" \\\n  -H "Content-Type: application/json" \\\n  -d '{
    "bank_id": "${bankId}",
    "template": "${ref}",
    "name": "${template.name}"
  }'`,
    },
  ];

  const installTabs: TabBlock[] = [
    {
      key: 'pretty',
      label: 'CLI',
      icon: <LuTerminal size={14} />,
      lang: 'bash',
      body: `hindclaw template install ${ref} --scope personal`,
    },
    {
      key: 'json',
      label: 'JSON',
      icon: <LuBraces size={14} />,
      lang: 'bash',
      body: `hindclaw template install ${ref} --scope personal -o json`,
    },
  ];

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div>
            <span className={styles.modalCategory}>{template.category}</span>
            <Heading as="h2" className={styles.modalTitle}>{template.name}</Heading>
            <p className={styles.modalDescription}>{template.description}</p>
            <div className={styles.modalMeta}>
              <span className={styles.modalMetaItem}>
                <strong>Source:</strong> <code>{ref}</code>
              </span>
              {template.tags && template.tags.length > 0 && (
                <div className={styles.modalTags}>
                  {template.tags.map((tag) => (
                    <span key={tag} className={styles.tag}>#{tag}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button className={styles.modalClose} onClick={onClose} aria-label="Close">
            <LuX size={20} />
          </button>
        </div>

        <div className={styles.modalTabBar}>
          <button
            className={`${styles.modalTab} ${tab === 'install' ? styles.modalTabActive : ''}`}
            onClick={() => setTab('install')}>
            Install
          </button>
          <button
            className={`${styles.modalTab} ${tab === 'manifest' ? styles.modalTabActive : ''}`}
            onClick={() => setTab('manifest')}>
            Manifest JSON
          </button>
        </div>

        <div className={styles.modalBody} ref={bodyRef}>
          {tab === 'install' ? (
            <section className={styles.installSection}>
              <div className={styles.installStep}>
                <div className={styles.installStepHead}>
                  <span className={styles.installStepNum}>1</span>
                  <div>
                    <Heading as="h4" className={styles.installStepTitle}>
                      Create a bank from this template
                    </Heading>
                    <p className={styles.installStepHint}>
                      Registers the source template (if needed) and provisions a new bank in one call.
                    </p>
                  </div>
                </div>
                <CodeTabs tabs={applyTabs} />
              </div>

              <div className={styles.installStep}>
                <div className={styles.installStepHead}>
                  <span className={styles.installStepNum}>2</span>
                  <div>
                    <Heading as="h4" className={styles.installStepTitle}>
                      Or just add it to your library
                    </Heading>
                    <p className={styles.installStepHint}>
                      Register the template under your user scope without creating a bank yet.
                      Apply it later with <code>hindclaw template apply</code>.
                    </p>
                  </div>
                </div>
                <CodeTabs tabs={installTabs} />
              </div>

              <p className={styles.installFooterHint}>
                Prefer a local file? Switch to the <strong>Manifest JSON</strong> tab, copy it,
                save as <code>{template.id}.json</code>, then run{' '}
                <code>hindclaw template import {template.id}.json --scope personal</code>.
              </p>
            </section>
          ) : (
            <div className={styles.manifestCodeWrap}>
              <CodeBlock language="json">{json}</CodeBlock>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Page                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */

export default function TemplatesHub(): React.ReactElement {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return templates.filter((t) => {
      if (selectedCategory !== 'all' && t.category !== selectedCategory) return false;
      if (!q) return true;
      const haystack = [
        t.name,
        t.description,
        ...(t.tags ?? []),
        ...(t.integrations ?? []),
      ].join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }, [search, selectedCategory]);

  return (
    <Layout
      title="Bank Templates"
      description="Pre-built HindClaw bank templates — install with one CLI command or apply directly into a new bank.">
      <header className={styles.hero}>
        <div className={styles.heroInner}>
          <Heading as="h1" className={styles.heroTitle}>Bank Templates</Heading>
          <p className={styles.heroSubtitle}>
            Pre-built bank configurations — missions, entity labels, directives, and mental models
            tuned for common use cases. Apply in one command.
          </p>

          <div className={styles.searchWrapper}>
            <LuSearch size={18} className={styles.searchIcon} />
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search templates, tags, integrations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search templates"
              autoComplete="off"
            />
            {search && (
              <button
                className={styles.searchClear}
                onClick={() => setSearch('')}
                aria-label="Clear search">
                <LuX size={16} />
              </button>
            )}
          </div>

          <div className={styles.heroStats}>
            <span className={styles.stat}>
              <strong>{templates.length}</strong> templates
            </span>
            <span className={styles.statDivider}>·</span>
            <span className={styles.stat}>
              <strong>{new Set(templates.map((t) => t.category)).size}</strong> categories
            </span>
          </div>
        </div>
        <div className={styles.heroGlow} />
      </header>

      <main className={styles.page}>
        <div className="container">
          <div className={styles.toolbar}>
            <div className={styles.filterGroup}>
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={`${styles.filterPill} ${selectedCategory === c ? styles.filterPillActive : ''}`}
                  onClick={() => setSelectedCategory(c)}>
                  {CATEGORY_LABELS[c] ?? c}
                </button>
              ))}
            </div>
            <span className={styles.resultCount}>
              {filtered.length} template{filtered.length !== 1 ? 's' : ''}
            </span>
          </div>

          {filtered.length === 0 ? (
            <div className={styles.empty}>
              <p>No templates match your search.</p>
              <button
                className={styles.resetButton}
                onClick={() => {
                  setSearch('');
                  setSelectedCategory('all');
                }}>
                Reset filters
              </button>
            </div>
          ) : (
            <div className={styles.grid}>
              {filtered.map((t) => (
                <TemplateCard key={t.id} template={t} onSelect={() => setSelectedTemplate(t)} />
              ))}
            </div>
          )}

          <div className={styles.submitBanner}>
            <div className={styles.submitBannerContent}>
              <Heading as="h3" className={styles.submitBannerTitle}>
                Have a template to share?
              </Heading>
              <p className={styles.submitBannerText}>
                Contribute it to the community. Open a pull request and add your entry to the
                HindClaw bank templates.
              </p>
              <Link
                href={CATALOG_EDIT_URL}
                className={styles.submitButton}
                target="_blank"
                rel="noopener noreferrer">
                Submit a template &rarr;
              </Link>
            </div>
          </div>
        </div>
      </main>

      {selectedTemplate && (
        <ManifestModal template={selectedTemplate} onClose={() => setSelectedTemplate(null)} />
      )}
    </Layout>
  );
}

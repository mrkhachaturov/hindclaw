import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Hero                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */

function Hero() {
  return (
    <header className={styles.hero}>
      <div className={styles.heroInner}>
        <div className={styles.heroContent}>
          <img
            src="/img/hindclaw-hero.png"
            alt="HindClaw"
            className={styles.heroLogo}
          />
          <Heading as="h1" className={styles.heroTitle}>
            Production Memory Infrastructure for AI Agents
          </Heading>
          <p className={styles.heroSubtitle}>
            Server-side access control. Terraform-managed banks.
            Multi-agent memory with per-user permissions.
            Built on{' '}
            <a href="https://hindsight.vectorize.io" className={styles.heroLink}>
              Hindsight
            </a>
            {' '}by{' '}
            <a href="https://vectorize.io" className={styles.heroLink}>
              Vectorize
            </a>.
          </p>
          <div className={styles.heroButtons}>
            <Link
              className={clsx('button button--lg', styles.heroPrimary)}
              to="/docs/intro">
              Get Started
            </Link>
            <Link
              className={clsx('button button--lg', styles.heroSecondary)}
              href="https://github.com/mrkhachaturov/hindclaw">
              GitHub
            </Link>
          </div>
          <div className={styles.heroInstall}>
            <div className={styles.installPill}>
              <span className={styles.installLabel}>server extension</span>
              <code>pip install hindclaw-extension</code>
            </div>
            <div className={styles.installPill}>
              <span className={styles.installLabel}>terraform</span>
              <code>source = "mrkhachaturov/hindclaw"</code>
            </div>
          </div>
          <p className={styles.heroCloud}>
            Want managed infrastructure?{' '}
            <a href="https://ui.hindsight.vectorize.io/signup">
              Try Hindsight Cloud
            </a>
          </p>
        </div>
      </div>
      <div className={styles.heroGlow} />
    </header>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Packages                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */

function Packages() {
  return (
    <section className={styles.packages}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>Three Packages, One Platform</Heading>
        <p className={styles.sectionSubtitle}>
          Each layer is independent. Use what you need.
        </p>
        <div className={styles.packageGrid}>
          <div className={styles.packageCard}>
            <div className={styles.packageBadge}>
              <img src="https://img.shields.io/pypi/v/hindclaw-extension?style=flat-square&color=0f766e" alt="PyPI" />
            </div>
            <Heading as="h3" className={styles.packageName}>hindclaw-extension</Heading>
            <p className={styles.packageDesc}>
              Server-side Hindsight extensions. JWT auth, permission enforcement,
              tag injection, management REST API. Install on any Hindsight server.
            </p>
            <a href="https://pypi.org/project/hindclaw-extension/" className={styles.packageRegistry}>
              PyPI
            </a>
          </div>

          <div className={styles.packageCard}>
            <div className={styles.packageBadge}>
              <img src="https://img.shields.io/badge/terraform-registry-844FBA?style=flat-square" alt="Terraform" />
            </div>
            <Heading as="h3" className={styles.packageName}>terraform-provider-hindclaw</Heading>
            <p className={styles.packageDesc}>
              Manage users, groups, banks, permissions, directives, mental models,
              and entity labels as code. <code>terraform apply</code> and it's live.
            </p>
            <a href="https://registry.terraform.io/providers/mrkhachaturov/hindclaw/latest" className={styles.packageRegistry}>
              Terraform Registry
            </a>
          </div>

          <div className={styles.packageCard}>
            <div className={styles.packageBadge}>
              <img src="https://img.shields.io/npm/v/hindclaw-openclaw?style=flat-square&color=0f766e" alt="npm" />
            </div>
            <Heading as="h3" className={styles.packageName}>hindclaw-openclaw</Heading>
            <p className={styles.packageDesc}>
              OpenClaw gateway plugin. Thin adapter — signs JWTs, auto-starts
              embed daemon with extensions loaded. Zero manual setup.
            </p>
            <a href="https://www.npmjs.com/package/hindclaw-openclaw" className={styles.packageRegistry}>
              npm
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  How It Works                                                              */
/* ═══════════════════════════════════════════════════════════════════════════ */

function Flow() {
  return (
    <section className={styles.flow}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>How It Works</Heading>
        <div className={styles.flowGrid}>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>1</div>
            <Heading as="h3" className={styles.flowTitle}>Message Arrives</Heading>
            <p>
              User sends a message via Telegram, Slack, or any channel.
              The client routes it to the right agent.
            </p>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>2</div>
            <Heading as="h3" className={styles.flowTitle}>Client Signs JWT</Heading>
            <p>
              A JWT is generated with sender, agent, channel, and topic context.
              Sent with every API call. No user config needed.
            </p>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>3</div>
            <Heading as="h3" className={styles.flowTitle}>Server Resolves</Heading>
            <p>
              Extension resolves sender to user, checks group memberships,
              applies the 4-layer permission cascade.
            </p>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>4</div>
            <Heading as="h3" className={styles.flowTitle}>Memory Operates</Heading>
            <p>
              Recall returns filtered results with tag groups.
              Retain stores with injected tags and strategy.
              All server-side.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Features                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */

const features = [
  {
    title: 'Server-Side Access Control',
    description:
      'JWT auth, user/group permissions, tag-based recall filtering, and retain strategy enrichment — all enforced on the Hindsight server via three extensions.',
  },
  {
    title: 'Infrastructure as Code',
    description:
      'Terraform provider for the full stack. Banks, configs, permissions, directives, mental models, entity labels — version-controlled and reviewable.',
  },
  {
    title: 'Per-Agent Memory Banks',
    description:
      'Each agent gets its own bank with custom missions, entity labels, dispositions, and directives. 11 agents, 11 different memory behaviors.',
  },
  {
    title: 'Multi-Bank Recall',
    description:
      'Agents read from multiple banks in parallel. Permissions checked per-bank — no unauthorized cross-reads.',
  },
  {
    title: 'Named Retain Strategies',
    description:
      'Route conversation topics to different extraction profiles. Strategic conversations get deep analysis, daily chats get lightweight extraction.',
  },
  {
    title: 'Entity Labels',
    description:
      'Controlled vocabulary for consistent fact classification. Multilingual aliases, tag generation, and graph-traversable entities from a single definition.',
  },
];

function Features() {
  return (
    <section className={styles.features}>
      <div className="container">
        <Heading as="h2" className={styles.sectionTitle}>Features</Heading>
        <div className="row">
          {features.map((f, i) => (
            <div key={i} className="col col--4">
              <div className={styles.featureCard}>
                <Heading as="h3" className={styles.featureTitle}>{f.title}</Heading>
                <p className={styles.featureDescription}>{f.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Powered by Hindsight                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */

function PoweredBy() {
  return (
    <section className={styles.poweredBy}>
      <div className={styles.poweredByContent}>
        <Heading as="h2" className={styles.sectionTitle}>Powered by Hindsight</Heading>
        <p className={styles.poweredByText}>
          HindClaw is built on{' '}
          <a href="https://hindsight.vectorize.io">Hindsight</a> by{' '}
          <a href="https://vectorize.io">Vectorize</a> — the highest-scoring
          agent memory system on the{' '}
          <a href="https://vectorize.io/#:~:text=The%20New%20Leader%20in%20Agent%20Memory">
            LongMemEval benchmark
          </a>.
          We build the access control and infrastructure layer.
          They build the memory engine.
        </p>
        <div className={styles.poweredByButtons}>
          <Link
            className={clsx('button button--lg', styles.heroPrimary)}
            href="https://ui.hindsight.vectorize.io/signup">
            Try Hindsight Cloud
          </Link>
          <span className={styles.poweredBySeparator}>or</span>
          <Link
            className={clsx('button button--lg', styles.heroSecondary)}
            href="https://join.slack.com/t/hindsight-space/shared_invite/zt-3nhbm4w29-LeSJ5Ixi6j8PdiYOCPlOgg">
            Join the Slack Community
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Page                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */

export default function Home(): ReactNode {
  return (
    <Layout
      title="Production Memory Infrastructure for AI Agents"
      description="Server-side access control, Terraform-managed banks, and multi-agent memory with per-user permissions. Built on Hindsight by Vectorize.">
      <Hero />
      <main>
        <Packages />
        <Flow />
        <Features />
        <PoweredBy />
      </main>
    </Layout>
  );
}

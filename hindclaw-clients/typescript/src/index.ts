// HindClaw TypeScript client — public surface.
//
// HindClaw is built on top of Hindsight. Manifest types come from upstream's
// @vectorize-io/hindsight-client package — re-exported here so consumers
// see one canonical type, not a HindClaw-local duplicate.
//
// HindClaw-specific operations (template install, bank creation, user
// management, etc.) come from the generated SDK in ./generated/.

// TEMPORARY: upstream @vectorize-io/hindsight-client 0.5.1 does not re-export
// BankTemplateConfig / BankTemplateDirective / BankTemplateImportResponse /
// BankTemplateManifest / BankTemplateMentalModel / MentalModelTriggerInput /
// MentalModelTriggerOutput from the package root. The types exist in the
// shipped dist tree but must be imported via a deep subpath.
// Tracked: filed upstream PR — link when opened. See docs/rkstack/plans/
//          hindclaw/2026-04-15-client-generator-image-alignment-plan-D.md
//          Blocker 2 for full rationale.
// Replace with: `export type { ... } from '@vectorize-io/hindsight-client';`
//               once upstream publishes the fix (expected 0.5.2+).
export type {
  BankTemplateConfig,
  BankTemplateDirective,
  BankTemplateImportResponse,
  BankTemplateManifest,
  BankTemplateMentalModel,
  MentalModelTriggerInput,
  MentalModelTriggerOutput,
} from '@vectorize-io/hindsight-client/generated/types.gen';

// Re-export everything HindClaw-specific from the generated SDK.
// The generated code contains its own copies of the upstream types
// above — those copies remain internal to hindclaw-clients/typescript/
// generated/types.gen.ts and are not part of the public surface.
export * from '../generated';

// TEMPORARY: upstream @vectorize-io/hindsight-client 0.5.1 does not list
// a subpath export for its generated types module. The types we need
// (BankTemplateConfig, BankTemplateDirective, BankTemplateImportResponse,
// BankTemplateManifest, BankTemplateMentalModel, MentalModelTriggerInput,
// MentalModelTriggerOutput) are defined in the shipped dist bundle but
// are not re-exported from the package root, and the `exports` field
// restricts direct subpath imports under `moduleResolution: bundler`.
//
// This ambient module declaration lets HindClaw re-export those types via
// the deep subpath `@vectorize-io/hindsight-client/generated/types.gen`
// (the file physically exists under node_modules because the upstream
// package.json `files` array ships `generated/`).
//
// Tracked: filed upstream PR — link when opened. See docs/rkstack/plans/
//          hindclaw/2026-04-15-client-generator-image-alignment-plan-D.md
//          Blocker 2 for full rationale.
// Replace with: delete this file entirely and change src/index.ts to
//               `export type { ... } from '@vectorize-io/hindsight-client';`
//               once upstream publishes the fix (expected 0.5.2+).
declare module '@vectorize-io/hindsight-client/generated/types.gen' {
  export type {
    BankTemplateConfig,
    BankTemplateDirective,
    BankTemplateImportResponse,
    BankTemplateManifest,
    BankTemplateMentalModel,
    MentalModelTriggerInput,
    MentalModelTriggerOutput,
  } from '../node_modules/@vectorize-io/hindsight-client/generated/types.gen';
}

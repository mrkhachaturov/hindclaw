// HindClaw TypeScript client — public surface.
//
// HindClaw is built on top of Hindsight. Manifest types (BankTemplateManifest,
// BankTemplateConfig, BankTemplateMentalModel, BankTemplateDirective,
// MentalModelTrigger, BankTemplateImportResponse) come from upstream's
// @vectorize-io/hindsight-client package — re-exported here so consumers
// see one canonical type, not a HindClaw-local duplicate.
//
// HindClaw-specific operations (template install, bank creation, user
// management, etc.) come from the generated SDK in ./generated/.

export type {
  BankTemplateManifest,
  BankTemplateConfig,
  BankTemplateMentalModel,
  BankTemplateDirective,
  MentalModelTrigger,
  BankTemplateImportResponse,
} from '@vectorize-io/hindsight-client';

// Re-export everything HindClaw-specific from the generated SDK.
// The generated code contains its own copies of the upstream types
// above — those copies remain internal to hindclaw-clients/typescript/
// generated/types.gen.ts and are not part of the public surface.
export * from '../generated';

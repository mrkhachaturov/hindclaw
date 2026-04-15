// HindClaw TypeScript client — public surface.
//
// HindClaw is built on top of Hindsight. Manifest types come from upstream's
// @vectorize-io/hindsight-client package — re-exported here so consumers
// see one canonical type, not a HindClaw-local duplicate.
//
// HindClaw-specific operations (template install, bank creation, user
// management, etc.) come from the generated SDK in ./generated/.

// Re-export the BankTemplate types that upstream 0.5.2+ exposes from its
// package root. MentalModelTriggerInput / MentalModelTriggerOutput are not
// re-exported from upstream's root; consumers who need them can import
// from HindClaw's own generated SDK:
//
//   import type { MentalModelTriggerInput } from '@hindclaw/client/generated';
//
// HindClaw's generator ships its own copies of the trigger types in
// generated/types.gen.ts, so there is no coupling to whether upstream
// eventually re-exports them from their root.
export type {
  BankTemplateConfig,
  BankTemplateDirective,
  BankTemplateImportResponse,
  BankTemplateManifest,
  BankTemplateMentalModel,
} from "@vectorize-io/hindsight-client";

// Re-export everything HindClaw-specific from the generated SDK.
// The generated code contains its own copies of the upstream types
// above — those copies remain internal to hindclaw-clients/typescript/
// generated/types.gen.ts and are not part of the public surface.
export * from "../generated";

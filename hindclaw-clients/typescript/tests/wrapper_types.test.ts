// Compile-time test that the wrapper re-exports upstream hindsight-client
// types (BankTemplateManifest et al) and that the re-export surface is
// structurally assignable from the upstream package's declaration.
//
// TEMPORARY: upstream @vectorize-io/hindsight-client 0.5.1 does not re-export
// these types from the package root. The wrapper uses a deep subpath import
// backed by src/vendor-hindsight-client.d.ts. Test imports mirror the same
// subpath so this file compiles with the current package version.
// Tracked: filed upstream PR — link when opened. See docs/rkstack/plans/
//          hindclaw/2026-04-15-client-generator-image-alignment-plan-D.md
//          Blocker 2 for full rationale.
// Replace with: `import type { BankTemplateManifest as UpstreamManifest }
//                from '@vectorize-io/hindsight-client';`
//               once upstream publishes the fix (expected 0.5.2+).
import type { BankTemplateManifest as UpstreamManifest } from '@vectorize-io/hindsight-client/generated/types.gen';
import type { BankTemplateManifest } from '../src/index';

// Compile-time structural identity: if the wrapper's re-export drifts from
// the upstream shape in either direction, these lines fail to type-check.
const check: UpstreamManifest = {} as BankTemplateManifest;
const reverseCheck: BankTemplateManifest = {} as UpstreamManifest;

test('wrapper re-exports upstream BankTemplateManifest', () => {
  // The assertions above are compile-time. Reference them at runtime so
  // ts-jest does not eliminate the bindings as unused.
  expect(check).toBeDefined();
  expect(reverseCheck).toBeDefined();
});

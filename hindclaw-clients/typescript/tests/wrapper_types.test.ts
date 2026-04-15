// Compile-time test that the wrapper re-exports upstream hindsight-client
// types (BankTemplateManifest et al) and that the re-export surface is
// structurally assignable from the upstream package's declaration.
import type { BankTemplateManifest as UpstreamManifest } from '@vectorize-io/hindsight-client';
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

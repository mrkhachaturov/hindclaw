// Preload script for running Jest-style tests under Deno.
// Mirrors upstream Hindsight's hindsight-clients/typescript/tests/deno_setup.ts
// so the Jest `describe`/`test`/`expect` globals resolve to Deno's std BDD
// equivalents without rewriting the Jest-flavored test files.
//
// Usage:
//   deno test --no-check --allow-env --allow-net --unstable-sloppy-imports \
//             --preload=tests/deno_setup.ts tests/

import { afterAll, afterEach, beforeAll, beforeEach, describe, it } from "jsr:@std/testing/bdd";
import { expect } from "jsr:@std/expect";

Object.assign(globalThis, {
  describe,
  test: it,
  it,
  beforeAll,
  beforeEach,
  afterAll,
  afterEach,
  expect,
});

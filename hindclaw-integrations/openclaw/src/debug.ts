// ── Shared debug logging ─────────────────────────────────────────────
// Silent by default, enable with debug: true in plugin config.
// Extracted into a standalone module so hooks can import without
// circular dependencies back to index.ts.

let debugEnabled = false;

export const debug = (...args: unknown[]): void => {
  if (debugEnabled) console.log(...args);
};

export function setDebugEnabled(value: boolean): void {
  debugEnabled = value;
}

export function isDebugEnabled(): boolean {
  return debugEnabled;
}

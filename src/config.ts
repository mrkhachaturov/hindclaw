import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import JSON5 from 'json5';
import type {
  BankConfig,
  PluginConfig,
  ResolvedConfig,
  ServerConfig,
  AgentEntry,
} from './types.js';
import { debug } from './debug.js';

// ── Field classification sets ─────────────────────────────────────────

const SERVER_SIDE_FIELDS = new Set<string>([
  'retain_mission',
  'observations_mission',
  'reflect_mission',
  'retain_extraction_mode',
  'disposition_skepticism',
  'disposition_literalism',
  'disposition_empathy',
  'entity_labels',
  'directives',
]);

const EXTRACTED_FIELDS = new Set<string>([
  'recallFrom',
  'sessionStartModels',
  'reflectOnRecall',
  'reflectBudget',
  'reflectMaxTokens',
]);

// ── Public API ────────────────────────────────────────────────────────

/**
 * Parse a JSON5 bank config file content into a BankConfig object.
 */
export function parseBankConfigFile(content: string): BankConfig {
  return JSON5.parse(content) as BankConfig;
}

/**
 * Resolve per-agent config by merging plugin defaults with bank config overrides.
 *
 * Resolution order: pluginDefaults → bankFile (shallow merge, bank file wins).
 *
 * Server-side fields are extracted into _serverConfig.
 * Extracted behavioral fields (recallFrom, sessionStartModels, reflect*) are
 * hoisted to their underscore-prefixed counterparts.
 * Everything else is merged as behavioral/infrastructure overrides.
 */
export function resolveAgentConfig(
  agentId: string,
  pluginDefaults: Omit<PluginConfig, 'agents' | 'bootstrap'>,
  bankConfigs: Map<string, BankConfig>,
): ResolvedConfig {
  const bankConfig = bankConfigs.get(agentId);

  if (!bankConfig) {
    debug(`[Hindsight] No bank config for agent "${agentId}" — using plugin defaults`);
    return {
      ...pluginDefaults,
      _serverConfig: null,
    } as ResolvedConfig;
  }

  // Separate fields from bankConfig
  const serverConfig: Partial<ServerConfig> = {};
  const overrides: Partial<BankConfig> = {};
  let hasServerFields = false;

  for (const [key, value] of Object.entries(bankConfig)) {
    if (SERVER_SIDE_FIELDS.has(key)) {
      (serverConfig as Record<string, unknown>)[key] = value;
      hasServerFields = true;
    } else if (!EXTRACTED_FIELDS.has(key)) {
      (overrides as Record<string, unknown>)[key] = value;
    }
  }

  // Build the merged behavioral/infrastructure config
  const merged: ResolvedConfig = {
    ...pluginDefaults,
    ...overrides,
    _serverConfig: hasServerFields ? (serverConfig as ServerConfig) : null,
  };

  // Hoist extracted fields
  if (bankConfig.recallFrom !== undefined) {
    merged._recallFrom = bankConfig.recallFrom;
  }
  if (bankConfig.sessionStartModels !== undefined) {
    merged._sessionStartModels = bankConfig.sessionStartModels;
  }
  if (bankConfig.reflectOnRecall !== undefined) {
    merged._reflectOnRecall = bankConfig.reflectOnRecall;
  }
  if (bankConfig.reflectBudget !== undefined) {
    merged._reflectBudget = bankConfig.reflectBudget;
  }
  if (bankConfig.reflectMaxTokens !== undefined) {
    merged._reflectMaxTokens = bankConfig.reflectMaxTokens;
  }

  return merged;
}

/**
 * Load all bank config files for the given agents map.
 * Reads files synchronously — called at plugin init time, not in the hot path.
 *
 * @param agents  Record<agentId, AgentEntry> from PluginConfig.agents
 * @param basePath  Base directory to resolve relative bankConfig paths against
 * @returns Map<agentId, BankConfig>
 */
export function loadBankConfigFiles(
  agents: Record<string, AgentEntry>,
  basePath: string,
): Map<string, BankConfig> {
  const result = new Map<string, BankConfig>();

  for (const [agentId, entry] of Object.entries(agents)) {
    if (!entry?.bankConfig) {
      console.warn(`[Hindsight] Agent "${agentId}" has no bankConfig path — skipping`);
      continue;
    }

    const filePath = entry.bankConfig.startsWith('/')
      ? entry.bankConfig
      : join(basePath, entry.bankConfig);

    try {
      const content = readFileSync(filePath, 'utf-8');
      result.set(agentId, parseBankConfigFile(content));
      debug(`[Hindsight] Loaded bank config for agent "${agentId}" from ${filePath}`);
    } catch (error) {
      console.warn(`[Hindsight] Failed to load bank config for agent "${agentId}" from ${filePath}:`, error instanceof Error ? error.message : error);
    }
  }

  return result;
}

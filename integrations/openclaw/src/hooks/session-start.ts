import type { HindsightClient } from '../client.js';
import type { ResolvedConfig, SessionStartModelConfig } from '../types.js';
import { debug } from '../debug.js';

const MODEL_TIMEOUT_MS = 2000;

export async function handleSessionStart(
  agentConfig: ResolvedConfig,
  client: HindsightClient,
): Promise<string | undefined> {
  const models = agentConfig._sessionStartModels;
  if (!models?.length) {
    debug('[Hindsight] session_start: no models configured, skipping');
    return undefined;
  }

  debug(`[Hindsight] session_start: loading ${models.length} model(s): ${models.map(m => `${m.type}:${m.label}`).join(', ')}`);

  const contextParts: string[] = [];

  const results = await Promise.allSettled(
    models.map(model => loadModel(model, client))
  );

  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    if (result.status === 'fulfilled' && result.value) {
      debug(`[Hindsight] session_start: loaded ${models[i].type} "${models[i].label}" (${result.value.length} chars)`);
      contextParts.push(`## ${models[i].label}\n${result.value}`);
    } else if (result.status === 'rejected') {
      debug(`[Hindsight] session_start: failed to load ${models[i].type} "${models[i].label}": ${result.reason instanceof Error ? result.reason.message : result.reason}`);
    } else {
      debug(`[Hindsight] session_start: ${models[i].type} "${models[i].label}" returned empty`);
    }
  }

  if (contextParts.length === 0) {
    debug('[Hindsight] session_start: no context loaded from any model');
    return undefined;
  }

  debug(`[Hindsight] session_start: injecting ${contextParts.length} context section(s)`);
  return `<hindsight_context>\n${contextParts.join('\n\n')}\n</hindsight_context>`;
}

async function loadModel(
  model: SessionStartModelConfig,
  client: HindsightClient,
): Promise<string | undefined> {
  try {
    if (model.type === 'mental_model') {
      debug(`[Hindsight] session_start: fetching mental_model "${model.modelId}" from bank ${model.bankId}`);
      const result = await client.getMentalModel(model.bankId, model.modelId, MODEL_TIMEOUT_MS);
      return result?.content || undefined;
    } else if (model.type === 'recall') {
      debug(`[Hindsight] session_start: recalling from bank ${model.bankId} with query "${model.query}"`);
      const result = await client.recall(model.bankId, {
        query: model.query,
        max_tokens: model.maxTokens ?? 256,
        budget: 'low',
      }, MODEL_TIMEOUT_MS);
      if (!result.results?.length) return undefined;
      return result.results.map(r => `- ${r.text}`).join('\n');
    }
    return undefined;
  } finally {
  }
}

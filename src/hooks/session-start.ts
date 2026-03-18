import type { HindsightClient } from '../client.js';
import type { ResolvedConfig, SessionStartModelConfig } from '../types.js';

const MODEL_TIMEOUT_MS = 2000;

export async function handleSessionStart(
  agentConfig: ResolvedConfig,
  client: HindsightClient,
): Promise<string | undefined> {
  const models = agentConfig._sessionStartModels;
  if (!models?.length) return undefined;

  const contextParts: string[] = [];

  const results = await Promise.allSettled(
    models.map(model => loadModel(model, client))
  );

  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    if (result.status === 'fulfilled' && result.value) {
      contextParts.push(`## ${models[i].label}\n${result.value}`);
    }
    // rejected or empty — skip silently (graceful degradation)
  }

  if (contextParts.length === 0) return undefined;

  return `<hindsight_context>\n${contextParts.join('\n\n')}\n</hindsight_context>`;
}

async function loadModel(
  model: SessionStartModelConfig,
  client: HindsightClient,
): Promise<string | undefined> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), MODEL_TIMEOUT_MS);

  try {
    if (model.type === 'mental_model') {
      const result = await client.getMentalModel(model.bankId, model.modelId);
      return result?.content || undefined;
    } else if (model.type === 'recall') {
      const result = await client.recall(model.bankId, {
        query: model.query,
        max_tokens: model.maxTokens ?? 256,
        budget: 'low',
      });
      if (!result.results?.length) return undefined;
      return result.results.map(r => `- ${r.text}`).join('\n');
    }
    return undefined;
  } finally {
    clearTimeout(timeout);
  }
}

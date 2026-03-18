import type { HindsightClient } from '../client.js';
import type { ResolvedConfig, PluginConfig, PluginHookAgentContext } from '../types.js';
import { deriveBankId } from '../derive-bank-id.js';

// Regex to strip <hindsight_memories>...</hindsight_memories> blocks
const MEMORY_TAG_RE = /<hindsight_memories>[\s\S]*?<\/hindsight_memories>/g;
// Regex to strip <hindsight_context>...</hindsight_context> blocks
const CONTEXT_TAG_RE = /<hindsight_context>[\s\S]*?<\/hindsight_context>/g;

export function stripMemoryTags(text: string): string {
  return text.replace(MEMORY_TAG_RE, '').replace(CONTEXT_TAG_RE, '').trim();
}

export function prepareRetentionTranscript(
  messages: Array<{ role: string; content: string }>,
  retainRoles: string[],
): string {
  return messages
    .filter(m => retainRoles.includes(m.role) && m.content?.trim())
    .map(m => `${m.role}: ${stripMemoryTags(m.content)}`)
    .filter(line => {
      // Skip lines where content was entirely stripped tags (only "role: " prefix remains)
      const colonIdx = line.indexOf(': ');
      return colonIdx !== -1 && line.slice(colonIdx + 2).trim().length > 0;
    })
    .join('\n');
}

export async function handleRetain(
  event: any,
  ctx: PluginHookAgentContext | undefined,
  agentConfig: ResolvedConfig,
  client: HindsightClient,
  pluginConfig: PluginConfig,
): Promise<void> {
  if (agentConfig.autoRetain === false) return;

  const messages = event?.messages ?? event?.context?.sessionEntry?.messages ?? [];
  if (!messages.length) return;

  const retainRoles = agentConfig.retainRoles ?? ['user', 'assistant'];
  const transcript = prepareRetentionTranscript(messages, retainRoles);
  if (!transcript.trim()) return;

  const bankId = deriveBankId(ctx, pluginConfig);
  const documentId = `session-${ctx?.sessionKey ?? 'unknown'}-${Date.now()}`;

  await client.retain(bankId, {
    items: [{
      content: transcript,
      document_id: documentId,
      metadata: {
        retained_at: new Date().toISOString(),
        message_count: String(messages.length),
        channel_type: ctx?.messageProvider ?? '',
        channel_id: ctx?.channelId ?? '',
        sender_id: ctx?.senderId ?? '',
      },
      tags: agentConfig.retainTags,
      context: agentConfig.retainContext,
      observation_scopes: agentConfig.retainObservationScopes,
    }],
    async: true,
  });
}

import type { ChatModelAdapter } from '@assistant-ui/react';

// TEMPORARY: scripted responder until the LangGraph agent is wired.
// Replace with: useLangGraphRuntime against a proxy holding LANGSMITH_API_KEY.

const CANNED_ANSWER = `HindClaw enforces access control in **three** extensions that load into the
Hindsight server:

| Extension | Responsibility |
|---|---|
| \`HindclawTenant\` | JWT / API key auth and sender-to-user resolution |
| \`HindclawValidator\` | recall, retain and reflect enforcement |
| \`HindclawHttp\` | the REST API under \`/ext/hindclaw/\` |

To grant a group read access to a bank, create a policy:

\`\`\`bash
hindclaw policy create \\
  --group engineering \\
  --bank shared-notes \\
  --permission recall
\`\`\`

Permissions are additive: a user gets the union of every policy that matches
their groups, so denying access means removing the policy, not adding a deny.`;

const SOURCES = [
  { title: 'Access control', url: '/docs/guides/access-control' },
  { title: 'Configuration reference', url: '/docs/reference/configuration' },
];

const TOOL_CALL_ID = 'preview-search-docs';

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true },
    );
  });

export const previewChatModelAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const question =
      messages
        .at(-1)
        ?.content.map((part) => (part.type === 'text' ? part.text : ''))
        .join('') ?? '';

    // 1. the model "searches the docs" — exercises the tool-call UI
    yield {
      content: [
        {
          type: 'tool-call',
          toolCallId: TOOL_CALL_ID,
          toolName: 'search_docs',
          argsText: JSON.stringify({ query: question }),
          args: { query: question },
        },
      ],
    };

    await sleep(700, abortSignal);

    yield {
      content: [
        {
          type: 'tool-call',
          toolCallId: TOOL_CALL_ID,
          toolName: 'search_docs',
          argsText: JSON.stringify({ query: question }),
          args: { query: question },
          result: { hits: SOURCES },
        },
      ],
    };

    // 2. then streams the answer a word at a time
    const words = CANNED_ANSWER.split(/(\s+)/);
    let text = '';
    for (const word of words) {
      text += word;
      yield {
        content: [
          {
            type: 'tool-call',
            toolCallId: TOOL_CALL_ID,
            toolName: 'search_docs',
            argsText: JSON.stringify({ query: question }),
            args: { query: question },
            result: { hits: SOURCES },
          },
          { type: 'text', text },
        ],
      };
      await sleep(12, abortSignal);
    }

    // 3. and cites what it found
    yield {
      content: [
        {
          type: 'tool-call',
          toolCallId: TOOL_CALL_ID,
          toolName: 'search_docs',
          argsText: JSON.stringify({ query: question }),
          args: { query: question },
          result: { hits: SOURCES },
        },
        { type: 'text', text },
        ...SOURCES.map((source) => ({
          type: 'source' as const,
          sourceType: 'url' as const,
          id: source.url,
          url: source.url,
          title: source.title,
        })),
      ],
      status: { type: 'complete', reason: 'stop' },
    };
  },
};

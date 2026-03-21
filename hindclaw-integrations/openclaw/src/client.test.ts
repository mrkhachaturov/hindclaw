import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { HindsightClient, HindsightHttpError, generateJwt, type HindsightClientOptions } from './client.js';
import type { PluginHookAgentContext } from './types.js';
import type {
  RetainRequest,
  RecallRequest,
  ReflectRequest,
} from './types.js';

const API_URL = 'https://hindsight.example.com';
const BANK_ID = 'yoda-main';

function makeClient(opts?: Partial<HindsightClientOptions>) {
  return new HindsightClient({
    apiUrl: opts?.apiUrl ?? API_URL,
    ...opts,
  });
}

describe('generateJwt', () => {
  const ctx: PluginHookAgentContext = {
    agentId: 'agent-alpha',
    messageProvider: 'telegram',
    channelId: '500001',
    senderId: '789012',
  };
  const secret = 'test-secret-key';
  const clientId = 'test-client';

  it('produces a valid 3-part JWT', () => {
    const jwt = generateJwt(ctx, secret, clientId);
    const parts = jwt.split('.');
    expect(parts).toHaveLength(3);
  });

  it('contains correct claims', () => {
    const jwt = generateJwt(ctx, secret, clientId);
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString());
    expect(payload.client_id).toBe('test-client');
    expect(payload.sender).toBe('telegram:789012');
    expect(payload.agent).toBe('agent-alpha');
    expect(payload.channel).toBe('telegram');
    expect(payload.topic).toBe('500001');
    expect(payload.exp - payload.iat).toBe(300);
  });

  it('omits sender when senderId is missing', () => {
    const noSender: PluginHookAgentContext = { agentId: 'agent-alpha', messageProvider: 'telegram' };
    const jwt = generateJwt(noSender, secret, clientId);
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString());
    expect(payload.sender).toBeUndefined();
  });

  it('omits topic when channelId is missing', () => {
    const noTopic: PluginHookAgentContext = { agentId: 'agent-alpha', messageProvider: 'telegram', senderId: '789012' };
    const jwt = generateJwt(noTopic, secret, clientId);
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString());
    expect(payload.topic).toBeUndefined();
  });
});

describe('HindsightClient', () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── HindsightHttpError ─────────────────────────────────────────────

  describe('HindsightHttpError', () => {
    it('has status, message, and name', () => {
      const err = new HindsightHttpError(403, 'Forbidden');
      expect(err).toBeInstanceOf(Error);
      expect(err).toBeInstanceOf(HindsightHttpError);
      expect(err.status).toBe(403);
      expect(err.message).toBe('Forbidden');
      expect(err.name).toBe('HindsightHttpError');
    });
  });

  describe('httpRequestRaw error handling', () => {
    it('throws HindsightHttpError with status on non-ok response', async () => {
      fetchSpy.mockResolvedValueOnce(new Response('access denied', { status: 403 }));
      const client = makeClient();
      const err = await client.retain(BANK_ID, { items: [{ content: 'x' }] }).catch(e => e);
      expect(err).toBeInstanceOf(HindsightHttpError);
      expect(err.status).toBe(403);
    });
  });

  // ── Constructor ────────────────────────────────────────────────────

  describe('constructor', () => {
    it('creates instance with apiUrl', () => {
      const client = makeClient();
      expect(client).toBeInstanceOf(HindsightClient);
      expect(client.httpMode).toBe(true);
    });

    it('creates instance without apiUrl (subprocess mode)', () => {
      const client = new HindsightClient({ llmModel: 'gpt-4' });
      expect(client.httpMode).toBe(false);
    });

    it('strips trailing slash from apiUrl', () => {
      const client = new HindsightClient({ apiUrl: 'https://api.test.com/' });
      // Verify via a call
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ items: [] })));
      client.listMentalModels('b');
      expect(fetchSpy).toHaveBeenCalledWith(
        'https://api.test.com/v1/default/banks/b/mental-models',
        expect.anything(),
      );
    });
  });

  // ── retain ─────────────────────────────────────────────────────────

  describe('retain', () => {
    it('POSTs items to /memories with async: true', async () => {
      const retainResp = { message: 'ok', document_id: 'doc1', memory_unit_ids: ['m1'] };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(retainResp)));

      const request: RetainRequest = {
        items: [{ content: 'hello world', tags: ['test'] }],
        async: true,
      };

      const result = await makeClient().retain(BANK_ID, request);

      expect(fetchSpy).toHaveBeenCalledOnce();
      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/memories`);
      expect(opts.method).toBe('POST');
      expect(opts.headers['Content-Type']).toBe('application/json');
      expect(JSON.parse(opts.body)).toEqual({ items: request.items, async: true });
      expect(result).toEqual(retainResp);
    });
  });

  // ── recall ─────────────────────────────────────────────────────────

  describe('recall', () => {
    it('POSTs to /memories/recall with full body', async () => {
      const recallResp = { results: [], entities: null, trace: null, chunks: null };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(recallResp)));

      const request: RecallRequest = {
        query: 'what happened yesterday',
        budget: 'mid',
        max_tokens: 2048,
        types: ['world', 'experience'],
        tag_groups: [{ tags: ['important'], match: 'any' }],
      };

      const result = await makeClient().recall(BANK_ID, request);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/memories/recall`);
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual(request);
      expect(result).toEqual(recallResp);
    });

    it('uses custom timeout when provided', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ results: [], entities: null, trace: null, chunks: null })));

      await makeClient().recall(BANK_ID, { query: 'test' }, 5000);

      const [, opts] = fetchSpy.mock.calls[0];
      expect(opts.signal).toBeDefined();
    });
  });

  // ── reflect ────────────────────────────────────────────────────────

  describe('reflect', () => {
    it('POSTs to /reflect with full body', async () => {
      const reflectResp = { text: 'analysis', based_on: ['m1'], usage: { prompt_tokens: 100, completion_tokens: 50 } };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(reflectResp)));

      const request: ReflectRequest = {
        query: 'summarize interactions',
        budget: 'high',
        max_tokens: 4096,
        tag_groups: [{ tags: ['user-facing'], match: 'all' }],
      };

      const result = await makeClient().reflect(BANK_ID, request);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/reflect`);
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual(request);
      expect(result).toEqual(reflectResp);
    });
  });

  // ── getMentalModel ─────────────────────────────────────────────────

  describe('getMentalModel', () => {
    it('GETs /mental-models/{id}', async () => {
      const model = { id: 'mm1', bank_id: BANK_ID, name: 'personality', source_query: 'q', content: 'c', trigger: 't', created_at: '', updated_at: '' };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(model)));

      const result = await makeClient().getMentalModel(BANK_ID, 'mm1');

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/mental-models/mm1`);
      expect(opts.method).toBe('GET');
      expect(result).toEqual(model);
    });
  });

  // ── listMentalModels ──────────────────────────────────────────────

  describe('listMentalModels', () => {
    it('GETs /mental-models and unwraps items', async () => {
      const models = [
        { id: 'mm1', bank_id: BANK_ID, name: 'personality', source_query: 'q', content: 'c', trigger: 't', created_at: '', updated_at: '' },
      ];
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ items: models })));

      const result = await makeClient().listMentalModels(BANK_ID);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/mental-models`);
      expect(opts.method).toBe('GET');
      expect(result).toEqual(models);
    });
  });

  // ── Error handling ─────────────────────────────────────────────────

  describe('error handling', () => {
    it('throws on non-2xx response with status and body', async () => {
      fetchSpy.mockResolvedValueOnce(new Response('{"error":"not found"}', { status: 404 }));

      await expect(makeClient().recall(BANK_ID, { query: 'test' })).rejects.toThrow(/HTTP 404.*not found/);
    });

    it('throws on 500 with body text', async () => {
      fetchSpy.mockResolvedValueOnce(new Response('internal server error', { status: 500 }));

      await expect(makeClient().retain(BANK_ID, { items: [{ content: 'x' }] })).rejects.toThrow('HTTP 500');
    });

    it('requires httpMode for API-only methods', async () => {
      const client = new HindsightClient({ llmModel: 'gpt-4' });

      await expect(client.listMentalModels('b')).rejects.toThrow('requires HTTP mode');
      await expect(client.reflect('b', { query: 'q' })).rejects.toThrow('requires HTTP mode');
    });
  });

  // ── URL encoding ───────────────────────────────────────────────────

  describe('URL encoding', () => {
    it('encodes bankId with special characters', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ items: [] })));

      await makeClient().listMentalModels('bank/with spaces&special');

      const [url] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/bank%2Fwith%20spaces%26special/mental-models`);
    });
  });

  // ── JWT auth ─────────────────────────────────────────────────────────

  describe('JWT auth', () => {
    it('sends JWT in Authorization header when ctx is provided', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ results: [], entities: null, trace: null, chunks: null })));
      const client = new HindsightClient({
        apiUrl: API_URL,
        jwtSecret: 'test-secret',
        clientId: 'test-client',
      });
      const ctx: PluginHookAgentContext = {
        agentId: 'agent-alpha',
        messageProvider: 'telegram',
        senderId: '789012',
      };
      await client.recall(BANK_ID, { query: 'test' }, undefined, ctx);

      const [, opts] = fetchSpy.mock.calls[0];
      expect(opts.headers['Authorization']).toMatch(/^Bearer eyJ/);
    });

    it('sends no auth when jwtSecret is not set', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ results: [], entities: null, trace: null, chunks: null })));
      const client = new HindsightClient({ apiUrl: API_URL });
      await client.recall(BANK_ID, { query: 'test' });

      const [, opts] = fetchSpy.mock.calls[0];
      expect(opts.headers['Authorization']).toBeUndefined();
    });
  });
});

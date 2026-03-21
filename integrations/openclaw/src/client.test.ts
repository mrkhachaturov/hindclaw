import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { HindsightClient } from './client.js';
import type {
  RetainRequest,
  RecallRequest,
  ReflectRequest,
  CreateDirectiveRequest,
} from './types.js';

const API_URL = 'https://hindsight.example.com';
const API_TOKEN = 'test-token-123';
const BANK_ID = 'yoda-main';

function makeClient(opts?: Partial<{ apiUrl: string; apiToken: string }>) {
  return new HindsightClient({
    apiUrl: opts?.apiUrl ?? API_URL,
    apiToken: opts?.apiToken ?? API_TOKEN,
  });
}

describe('HindsightClient', () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Constructor ────────────────────────────────────────────────────

  describe('constructor', () => {
    it('creates instance with apiUrl and apiToken', () => {
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
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ config: {}, overrides: {} })));
      client.getBankConfig('b');
      expect(fetchSpy).toHaveBeenCalledWith(
        'https://api.test.com/v1/default/banks/b/config',
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
      expect(opts.headers['Authorization']).toBe(`Bearer ${API_TOKEN}`);
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

  // ── getBankConfig ──────────────────────────────────────────────────

  describe('getBankConfig', () => {
    it('GETs /config', async () => {
      const configResp = { config: { retain_mission: 'test' }, overrides: {} };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(configResp)));

      const result = await makeClient().getBankConfig(BANK_ID);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/config`);
      expect(opts.method).toBe('GET');
      expect(opts.body).toBeUndefined();
      expect(result).toEqual(configResp);
    });
  });

  // ── updateBankConfig ───────────────────────────────────────────────

  describe('updateBankConfig', () => {
    it('PATCHes /config with updates wrapper', async () => {
      const configResp = { config: { retain_mission: 'new' }, overrides: { retain_mission: 'new' } };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(configResp)));

      const updates = { retain_mission: 'new mission' };
      const result = await makeClient().updateBankConfig(BANK_ID, updates);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/config`);
      expect(opts.method).toBe('PATCH');
      expect(JSON.parse(opts.body)).toEqual({ updates });
      expect(result).toEqual(configResp);
    });
  });

  // ── resetBankConfig ────────────────────────────────────────────────

  describe('resetBankConfig', () => {
    it('DELETEs /config', async () => {
      const configResp = { config: {}, overrides: {} };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(configResp)));

      const result = await makeClient().resetBankConfig(BANK_ID);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/config`);
      expect(opts.method).toBe('DELETE');
      expect(opts.body).toBeUndefined();
      expect(result).toEqual(configResp);
    });
  });

  // ── listDirectives ─────────────────────────────────────────────────

  describe('listDirectives', () => {
    it('GETs /directives and unwraps items', async () => {
      const directives = [
        { id: 'd1', bank_id: BANK_ID, name: 'dir1', content: 'c', priority: 1, is_active: true, tags: [], created_at: '', updated_at: '' },
      ];
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ items: directives })));

      const result = await makeClient().listDirectives(BANK_ID);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/directives`);
      expect(opts.method).toBe('GET');
      expect(result).toEqual(directives);
    });
  });

  // ── createDirective ────────────────────────────────────────────────

  describe('createDirective', () => {
    it('POSTs to /directives', async () => {
      const directive = { id: 'd1', bank_id: BANK_ID, name: 'test', content: 'do this', priority: 1, is_active: true, tags: [], created_at: '', updated_at: '' };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(directive)));

      const req: CreateDirectiveRequest = { name: 'test', content: 'do this' };
      const result = await makeClient().createDirective(BANK_ID, req);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/directives`);
      expect(opts.method).toBe('POST');
      expect(JSON.parse(opts.body)).toEqual(req);
      expect(result).toEqual(directive);
    });
  });

  // ── updateDirective ────────────────────────────────────────────────

  describe('updateDirective', () => {
    it('PATCHes /directives/{id}', async () => {
      const directive = { id: 'd1', bank_id: BANK_ID, name: 'updated', content: 'new', priority: 1, is_active: true, tags: [], created_at: '', updated_at: '' };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(directive)));

      const result = await makeClient().updateDirective(BANK_ID, 'd1', { name: 'updated' });

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/directives/d1`);
      expect(opts.method).toBe('PATCH');
      expect(JSON.parse(opts.body)).toEqual({ name: 'updated' });
      expect(result).toEqual(directive);
    });
  });

  // ── deleteDirective ────────────────────────────────────────────────

  describe('deleteDirective', () => {
    it('DELETEs /directives/{id}', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));

      await makeClient().deleteDirective(BANK_ID, 'd1');

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/directives/d1`);
      expect(opts.method).toBe('DELETE');
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

  // ── listTags ───────────────────────────────────────────────────────

  describe('listTags', () => {
    it('GETs /tags', async () => {
      const tags = { important: 5, daily: 12 };
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(tags)));

      const result = await makeClient().listTags(BANK_ID);

      const [url, opts] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/${BANK_ID}/tags`);
      expect(opts.method).toBe('GET');
      expect(result).toEqual(tags);
    });
  });

  // ── Error handling ─────────────────────────────────────────────────

  describe('error handling', () => {
    it('throws on non-2xx response with status and body', async () => {
      fetchSpy.mockResolvedValueOnce(new Response('{"error":"not found"}', { status: 404 }));

      await expect(makeClient().getBankConfig(BANK_ID)).rejects.toThrow(/HTTP 404.*not found/);
    });

    it('throws on 500 with body text', async () => {
      fetchSpy.mockResolvedValueOnce(new Response('internal server error', { status: 500 }));

      await expect(makeClient().listTags(BANK_ID)).rejects.toThrow('HTTP 500');
    });

    it('requires httpMode for API-only methods', async () => {
      const client = new HindsightClient({ llmModel: 'gpt-4' });

      await expect(client.getBankConfig('b')).rejects.toThrow('requires HTTP mode');
      await expect(client.listDirectives('b')).rejects.toThrow('requires HTTP mode');
      await expect(client.listMentalModels('b')).rejects.toThrow('requires HTTP mode');
      await expect(client.reflect('b', { query: 'q' })).rejects.toThrow('requires HTTP mode');
    });
  });

  // ── URL encoding ───────────────────────────────────────────────────

  describe('URL encoding', () => {
    it('encodes bankId with special characters', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ config: {}, overrides: {} })));

      await makeClient().getBankConfig('bank/with spaces&special');

      const [url] = fetchSpy.mock.calls[0];
      expect(url).toBe(`${API_URL}/v1/default/banks/bank%2Fwith%20spaces%26special/config`);
    });
  });

  // ── Authorization header ───────────────────────────────────────────

  describe('authorization', () => {
    it('omits Authorization header when no apiToken', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ config: {}, overrides: {} })));

      await new HindsightClient({ apiUrl: API_URL }).getBankConfig(BANK_ID);

      const [, opts] = fetchSpy.mock.calls[0];
      expect(opts.headers['Authorization']).toBeUndefined();
    });

    it('includes Authorization header when apiToken provided', async () => {
      fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ config: {}, overrides: {} })));

      await makeClient().getBankConfig(BANK_ID);

      const [, opts] = fetchSpy.mock.calls[0];
      expect(opts.headers['Authorization']).toBe(`Bearer ${API_TOKEN}`);
    });
  });
});

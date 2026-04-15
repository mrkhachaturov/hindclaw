// Smoke tests for the generated SDK surface exercised against a
// node http.createServer stub. Covers request serialization for
// createMyTemplate and response parsing for createBankFromTemplate.
//
// The manifest literal uses the 12 pre-#1044 configurable fields so the
// test stays stable regardless of which @vectorize-io/hindsight-client
// version is installed (currently pinned at 0.5.1, which predates the
// 10 new fields added upstream). Mental models and directives are empty
// so the test does not need to pick a MentalModelTriggerInput/Output
// variant on the request side.
import * as http from 'node:http';
import type { AddressInfo } from 'node:net';

import { createClient, createConfig } from '../generated/client';
import {
  createMyTemplate,
  createBankFromTemplate,
} from '../generated';

type StubCapture = {
  method?: string;
  url?: string;
  body?: unknown;
};

function buildStubServer(
  capture: StubCapture,
): Promise<{ server: http.Server; url: string }> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let raw = '';
      req.on('data', (chunk) => {
        raw += chunk.toString();
      });
      req.on('end', () => {
        capture.method = req.method;
        capture.url = req.url;
        capture.body = raw ? JSON.parse(raw) : undefined;

        res.setHeader('Content-Type', 'application/json');

        if (req.method === 'POST' && req.url === '/ext/hindclaw/me/templates') {
          const body = capture.body as { id: string; name: string };
          res.statusCode = 200;
          res.end(
            JSON.stringify({
              id: body.id,
              name: body.name,
              description: null,
              category: null,
              integrations: [],
              tags: [],
              scope: 'personal',
              owner: 'user-1',
              source_name: null,
              source_scope: null,
              source_owner: null,
              source_revision: null,
              installed_at: '2026-04-15T00:00:00Z',
              updated_at: '2026-04-15T00:00:00Z',
              manifest: { version: '1' },
            }),
          );
          return;
        }

        if (req.method === 'POST' && req.url === '/ext/hindclaw/banks') {
          const body = capture.body as { bank_id: string; template: string };
          res.statusCode = 200;
          res.end(
            JSON.stringify({
              bank_id: body.bank_id,
              template: body.template,
              bank_created: true,
              import_result: {
                bank_id: body.bank_id,
                config_applied: false,
                mental_models_created: [],
                mental_models_updated: [],
                directives_created: [],
                directives_updated: [],
              },
            }),
          );
          return;
        }

        res.statusCode = 404;
        res.end('{}');
      });
    });
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as AddressInfo;
      resolve({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

function closeServer(server: http.Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
}

describe('generated SDK smoke tests', () => {
  test('createMyTemplate POSTs a serialized CreateTemplateRequest', async () => {
    const capture: StubCapture = {};
    const { server, url } = await buildStubServer(capture);
    try {
      const localClient = createClient(createConfig({ baseUrl: url }));
      const result = await createMyTemplate({
        client: localClient,
        body: {
          id: 'tmpl-smoke',
          name: 'Smoke Template',
          manifest: {
            version: '1',
            mental_models: [],
            directives: [],
          },
        },
      });

      expect(capture.method).toBe('POST');
      expect(capture.url).toBe('/ext/hindclaw/me/templates');
      expect(capture.body).toMatchObject({
        id: 'tmpl-smoke',
        name: 'Smoke Template',
        manifest: {
          version: '1',
          mental_models: [],
          directives: [],
        },
      });
      expect(result.data?.id).toBe('tmpl-smoke');
      expect(result.data?.name).toBe('Smoke Template');
    } finally {
      await closeServer(server);
    }
  });

  test('createBankFromTemplate parses BankCreationResponse with import_result', async () => {
    const capture: StubCapture = {};
    const { server, url } = await buildStubServer(capture);
    try {
      const localClient = createClient(createConfig({ baseUrl: url }));
      const result = await createBankFromTemplate({
        client: localClient,
        body: {
          bank_id: 'bank-smoke',
          template: 'tmpl-smoke',
          name: 'Smoke Bank',
        },
      });

      expect(capture.method).toBe('POST');
      expect(capture.url).toBe('/ext/hindclaw/banks');
      expect(capture.body).toMatchObject({
        bank_id: 'bank-smoke',
        template: 'tmpl-smoke',
        name: 'Smoke Bank',
      });
      expect(result.data?.bank_id).toBe('bank-smoke');
      expect(result.data?.template).toBe('tmpl-smoke');
      expect(result.data?.bank_created).toBe(true);
      expect(result.data?.import_result).toBeDefined();
      expect(result.data?.import_result.bank_id).toBe('bank-smoke');
      expect(result.data?.import_result.config_applied).toBe(false);
    } finally {
      await closeServer(server);
    }
  });
});

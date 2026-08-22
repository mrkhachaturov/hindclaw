import * as path from 'node:path';
import { createOpenAPI } from 'fumadocs-openapi/server';

export const openapi = createOpenAPI({
  input: [path.resolve('./public/openapi.json')],
});

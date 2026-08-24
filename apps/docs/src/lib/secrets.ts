import { readFile } from 'node:fs/promises';
import { InfisicalSDK } from '@infisical/sdk';

const SERVICE_ACCOUNT_TOKEN_PATH = '/var/run/secrets/kubernetes.io/serviceaccount/token';
const SESSION_TTL_MS = 30 * 60 * 1000;
const VALUE_TTL_MS = 5 * 60 * 1000;

type Session = { client: InfisicalSDK; expires: number };
type Entry = { value: string | undefined; expires: number };

let session: Session | undefined;
const values = new Map<string, Entry>();

function config() {
  const { INFISICAL_DOMAIN, INFISICAL_IDENTITY_ID, INFISICAL_PROJECT_ID, INFISICAL_ENV } =
    process.env;

  if (!INFISICAL_DOMAIN || !INFISICAL_IDENTITY_ID || !INFISICAL_PROJECT_ID || !INFISICAL_ENV) {
    return undefined;
  }

  return {
    siteUrl: INFISICAL_DOMAIN,
    identityId: INFISICAL_IDENTITY_ID,
    projectId: INFISICAL_PROJECT_ID,
    environment: INFISICAL_ENV,
    secretPath: process.env.INFISICAL_PATH ?? '/',
  };
}

async function login(siteUrl: string, identityId: string): Promise<InfisicalSDK> {
  const jwt = await readFile(SERVICE_ACCOUNT_TOKEN_PATH, 'utf8');

  const response = await fetch(new URL('/api/v1/auth/kubernetes-auth/login', siteUrl), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ identityId, jwt: jwt.trim() }),
  });

  if (!response.ok) {
    throw new Error(`kubernetes auth login failed: ${response.status}`);
  }

  const { accessToken } = (await response.json()) as { accessToken: string };
  const client = new InfisicalSDK({ siteUrl });
  client.auth().accessToken(accessToken);
  return client;
}

async function connect(siteUrl: string, identityId: string, now: number): Promise<InfisicalSDK> {
  if (session && session.expires > now) return session.client;

  const client = await login(siteUrl, identityId);
  session = { client, expires: now + SESSION_TTL_MS };
  return client;
}

export async function secret(name: string): Promise<string | undefined> {
  const settings = config();
  if (!settings) return process.env[name];

  const now = Date.now();
  const cached = values.get(name);
  if (cached && cached.expires > now) return cached.value;

  try {
    const client = await connect(settings.siteUrl, settings.identityId, now);
    const result = await client.secrets().getSecret({
      secretName: name,
      projectId: settings.projectId,
      environment: settings.environment,
      secretPath: settings.secretPath,
      expandSecretReferences: true,
      includeImports: true,
    });

    const value = result.secretValue;
    values.set(name, { value, expires: now + VALUE_TTL_MS });
    return value;
  } catch (error) {
    session = undefined;
    if (cached) return cached.value;
    throw error;
  }
}

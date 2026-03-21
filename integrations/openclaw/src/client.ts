import { execFile } from 'child_process';
import { promisify } from 'util';
import { writeFile, mkdir, rm } from 'fs/promises';
import { tmpdir } from 'os';
import { join } from 'path';
import { randomBytes } from 'crypto';
import type {
  RetainRequest,
  RetainResponse,
  RecallRequest,
  RecallResponse,
  ReflectRequest,
  ReflectResponse,
  Directive,
  CreateDirectiveRequest,
  MentalModel,
  BankConfigResponse,
} from './types.js';

const execFileAsync = promisify(execFile);

const MAX_BUFFER = 5 * 1024 * 1024; // 5 MB — large transcripts can exceed default 1 MB
const DEFAULT_TIMEOUT_MS = 15_000;

/** Strip null bytes from strings — Node 22 rejects them in execFile() args */
const sanitize = (s: string) => s.replace(/\0/g, '');

/**
 * Sanitize a string for use as a cross-platform filename.
 * Replaces characters illegal on Windows or Unix with underscores.
 */
function sanitizeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|\x00-\x1f]/g, '_').slice(0, 200) || 'content';
}

export interface HindsightClientOptions {
  llmModel?: string;
  embedVersion?: string;
  embedPackagePath?: string;
  apiUrl?: string;
  apiToken?: string;
}

export class HindsightClient {
  private apiUrl?: string;
  private apiToken?: string;
  private llmModel?: string;
  private embedVersion: string;
  private embedPackagePath?: string;

  constructor(opts: HindsightClientOptions) {
    this.llmModel = opts.llmModel;
    this.embedVersion = opts.embedVersion || 'latest';
    this.embedPackagePath = opts.embedPackagePath;
    this.apiUrl = opts.apiUrl?.replace(/\/$/, '');
    this.apiToken = opts.apiToken;
  }

  get httpMode(): boolean {
    return !!this.apiUrl;
  }

  // ── Core memory operations ───────────────────────────────────────

  async retain(bankId: string, request: RetainRequest): Promise<RetainResponse> {
    if (this.httpMode) {
      return this.httpRequest<RetainResponse>('POST', `${this.bankUrl(bankId)}/memories`, {
        items: request.items,
        async: request.async ?? true,
      });
    }
    return this.retainSubprocess(bankId, request);
  }

  async recall(bankId: string, request: RecallRequest, timeoutMs?: number): Promise<RecallResponse> {
    if (this.httpMode) {
      // Defense-in-depth: truncate query to stay under API's 500-token limit
      const MAX_QUERY_CHARS = 800;
      const query = request.query.length > MAX_QUERY_CHARS
        ? (console.warn(`[Hindsight] Truncating recall query from ${request.query.length} to ${MAX_QUERY_CHARS} chars`),
           request.query.substring(0, MAX_QUERY_CHARS))
        : request.query;
      const body: Record<string, unknown> = {
        query,
        max_tokens: request.max_tokens || 1024,
      };
      if (request.budget) {
        body.budget = request.budget;
      }
      if (request.types) {
        body.types = request.types;
      }
      if (request.tag_groups) {
        body.tag_groups = request.tag_groups;
      }
      return this.httpRequest<RecallResponse>(
        'POST',
        `${this.bankUrl(bankId)}/memories/recall`,
        body,
        timeoutMs ?? DEFAULT_TIMEOUT_MS,
      );
    }
    return this.recallSubprocess(bankId, request, timeoutMs);
  }

  async reflect(bankId: string, request: ReflectRequest): Promise<ReflectResponse> {
    this.requireHttpMode('reflect');
    return this.httpRequest<ReflectResponse>('POST', `${this.bankUrl(bankId)}/reflect`, request);
  }

  // ── Bank config ──────────────────────────────────────────────────

  async getBankConfig(bankId: string): Promise<BankConfigResponse> {
    this.requireHttpMode('getBankConfig');
    return this.httpRequest<BankConfigResponse>('GET', `${this.bankUrl(bankId)}/config`);
  }

  async updateBankConfig(bankId: string, updates: Record<string, unknown>): Promise<BankConfigResponse> {
    this.requireHttpMode('updateBankConfig');
    return this.httpRequest<BankConfigResponse>('PATCH', `${this.bankUrl(bankId)}/config`, { updates });
  }

  async resetBankConfig(bankId: string): Promise<BankConfigResponse> {
    this.requireHttpMode('resetBankConfig');
    return this.httpRequest<BankConfigResponse>('DELETE', `${this.bankUrl(bankId)}/config`);
  }

  async ensureBank(bankId: string): Promise<void> {
    this.requireHttpMode('ensureBank');
    await this.httpRequest('PUT', `${this.bankUrl(bankId)}`, {});
  }

  // ── Directives ───────────────────────────────────────────────────

  async listDirectives(bankId: string): Promise<Directive[]> {
    this.requireHttpMode('listDirectives');
    const resp = await this.httpRequest<{ items: Directive[] }>('GET', `${this.bankUrl(bankId)}/directives`);
    return resp.items;
  }

  async createDirective(bankId: string, directive: CreateDirectiveRequest): Promise<Directive> {
    this.requireHttpMode('createDirective');
    return this.httpRequest<Directive>('POST', `${this.bankUrl(bankId)}/directives`, directive);
  }

  async updateDirective(bankId: string, directiveId: string, update: Partial<CreateDirectiveRequest>): Promise<Directive> {
    this.requireHttpMode('updateDirective');
    return this.httpRequest<Directive>('PATCH', `${this.bankUrl(bankId)}/directives/${encodeURIComponent(directiveId)}`, update);
  }

  async deleteDirective(bankId: string, directiveId: string): Promise<void> {
    this.requireHttpMode('deleteDirective');
    await this.httpRequestRaw('DELETE', `${this.bankUrl(bankId)}/directives/${encodeURIComponent(directiveId)}`);
  }

  // ── Mental models ────────────────────────────────────────────────

  async getMentalModel(bankId: string, modelId: string, timeoutMs?: number): Promise<MentalModel> {
    this.requireHttpMode('getMentalModel');
    return this.httpRequest<MentalModel>('GET', `${this.bankUrl(bankId)}/mental-models/${encodeURIComponent(modelId)}`, undefined, timeoutMs);
  }

  async listMentalModels(bankId: string): Promise<MentalModel[]> {
    this.requireHttpMode('listMentalModels');
    const resp = await this.httpRequest<{ items: MentalModel[] }>('GET', `${this.bankUrl(bankId)}/mental-models`);
    return resp.items;
  }

  // ── Tags ─────────────────────────────────────────────────────────

  async listTags(bankId: string): Promise<Record<string, number>> {
    this.requireHttpMode('listTags');
    return this.httpRequest<Record<string, number>>('GET', `${this.bankUrl(bankId)}/tags`);
  }

  // ── Internal: URL + HTTP helpers ─────────────────────────────────

  private bankUrl(bankId: string): string {
    return `${this.apiUrl}/v1/default/banks/${encodeURIComponent(bankId)}`;
  }

  private httpHeaders(): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.apiToken) {
      headers['Authorization'] = `Bearer ${this.apiToken}`;
    }
    return headers;
  }

  private requireHttpMode(method: string): void {
    if (!this.httpMode) {
      throw new Error(`${method} requires HTTP mode (apiUrl must be set)`);
    }
  }

  private async httpRequest<T>(method: string, url: string, body?: unknown, timeoutMs?: number): Promise<T> {
    const res = await this.httpRequestRaw(method, url, body, timeoutMs);

    // For 204 No Content, return undefined cast as T
    if (res.status === 204) {
      return undefined as T;
    }

    return res.json() as Promise<T>;
  }

  private async httpRequestRaw(method: string, url: string, body?: unknown, timeoutMs?: number): Promise<Response> {
    const opts: RequestInit = {
      method,
      headers: this.httpHeaders(),
      signal: AbortSignal.timeout(timeoutMs ?? DEFAULT_TIMEOUT_MS),
    };

    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }

    const res = await fetch(url, opts);

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}: ${text}`);
    }

    return res;
  }

  // ── Internal: subprocess mode (retain/recall only) ───────────────

  /**
   * Get the command and base args to run hindsight-embed.
   * Returns [command, ...baseArgs] for use with execFile/spawn (no shell).
   */
  private getEmbedCommand(): string[] {
    if (this.embedPackagePath) {
      return ['uv', 'run', '--directory', this.embedPackagePath, 'hindsight-embed'];
    }
    const embedPackage = this.embedVersion ? `hindsight-embed@${this.embedVersion}` : 'hindsight-embed@latest';
    // Inject claude-agent-sdk when using claude-code provider (uvx runs in isolated venv)
    const provider = process.env.HINDSIGHT_API_LLM_PROVIDER;
    if (provider === 'claude-code') {
      return ['uvx', '--with', 'claude-agent-sdk', embedPackage];
    }
    return ['uvx', embedPackage];
  }

  private async retainSubprocess(bankId: string, request: RetainRequest): Promise<RetainResponse> {
    // Subprocess mode: use first item's content, write to temp file
    const content = request.items.map(i => i.content).join('\n\n');
    const docId = request.items[0]?.document_id || 'conversation';

    const tempDir = join(tmpdir(), `hindsight_${randomBytes(8).toString('hex')}`);
    const safeFilename = sanitizeFilename(docId);
    const tempFile = join(tempDir, `${safeFilename}.txt`);

    try {
      await mkdir(tempDir, { recursive: true });
      await writeFile(tempFile, sanitize(content), 'utf8');

      const [cmd, ...baseArgs] = this.getEmbedCommand();
      const args = [...baseArgs, '--profile', 'openclaw', 'memory', 'retain-files', bankId, tempFile, '--async'];

      const { stdout } = await execFileAsync(cmd, args, { maxBuffer: MAX_BUFFER });
      console.log(`[Hindsight] Retained (async): ${stdout.trim()}`);

      return {
        message: 'Memory queued for background processing',
        document_id: docId,
        memory_unit_ids: [],
      };
    } catch (error) {
      throw new Error(`Failed to retain memory: ${error}`, { cause: error });
    } finally {
      await rm(tempDir, { recursive: true, force: true }).catch(() => {});
    }
  }

  private async recallSubprocess(bankId: string, request: RecallRequest, timeoutMs?: number): Promise<RecallResponse> {
    const query = sanitize(request.query);
    const maxTokens = request.max_tokens || 1024;
    const [cmd, ...baseArgs] = this.getEmbedCommand();
    const args = [...baseArgs, '--profile', 'openclaw', 'memory', 'recall', bankId, query, '--output', 'json', '--max-tokens', String(maxTokens)];

    try {
      const { stdout } = await execFileAsync(cmd, args, {
        maxBuffer: MAX_BUFFER,
        timeout: timeoutMs ?? 30_000,
      });

      return JSON.parse(stdout) as RecallResponse;
    } catch (error) {
      throw new Error(`Failed to recall memories: ${error}`, { cause: error });
    }
  }
}

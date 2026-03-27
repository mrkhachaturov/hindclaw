"""Hindclaw database layer — connection pool, DDL, and queries.

Connection pool is lazily initialized on first use via get_pool().
Reads HINDCLAW_DATABASE_URL (preferred) or HINDSIGHT_API_DATABASE_URL from os.environ.
DDL is executed on first pool creation via CREATE TABLE IF NOT EXISTS.

See spec Section 3 (Shared State) and Section 4 (Database Schema).
"""

import asyncio
import json
import logging
import os

import asyncpg

from hindclaw_ext.models import (
    ApiKeyRecord,
    AttachedPolicyRecord,
    BankPolicyRecord,
    GroupRecord,
    PolicyAttachmentRecord,
    PolicyRecord,
    ServiceAccountKeyRecord,
    ServiceAccountRecord,
    TemplateRecord,
    TemplateSourceRecord,
    UserRecord,
)

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()

# DDL for hindclaw tables — executed on first get_pool() call
_DDL = """\
CREATE TABLE IF NOT EXISTS hindclaw_users (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email        TEXT UNIQUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_api_keys (
    id          TEXT PRIMARY KEY,
    api_key     TEXT UNIQUE NOT NULL,
    user_id     TEXT NOT NULL REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_user_channels (
    user_id    TEXT NOT NULL REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    provider   TEXT NOT NULL,
    sender_id  TEXT NOT NULL,
    PRIMARY KEY (provider, sender_id)
);

CREATE TABLE IF NOT EXISTS hindclaw_groups (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_group_members (
    group_id TEXT NOT NULL REFERENCES hindclaw_groups(id) ON DELETE CASCADE,
    user_id  TEXT NOT NULL REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS hindclaw_policies (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    document_json JSONB NOT NULL,
    is_builtin   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_policy_attachments (
    policy_id      TEXT NOT NULL REFERENCES hindclaw_policies(id) ON DELETE CASCADE,
    principal_type TEXT NOT NULL CHECK (principal_type IN ('user', 'group')),
    principal_id   TEXT NOT NULL,
    priority       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (policy_id, principal_type, principal_id)
);

CREATE TABLE IF NOT EXISTS hindclaw_service_accounts (
    id                TEXT PRIMARY KEY,
    owner_user_id     TEXT NOT NULL REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    scoping_policy_id TEXT REFERENCES hindclaw_policies(id) ON DELETE SET NULL,
    display_name      TEXT NOT NULL,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_service_account_keys (
    id                 TEXT PRIMARY KEY,
    service_account_id TEXT NOT NULL REFERENCES hindclaw_service_accounts(id) ON DELETE CASCADE,
    api_key            TEXT UNIQUE NOT NULL,
    description        TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    last_used_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS hindclaw_bank_policies (
    bank_id       TEXT PRIMARY KEY,
    document_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bank_templates (
    id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('server', 'personal')),
    owner TEXT REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    source_name TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1,
    min_hindclaw_version TEXT NOT NULL,
    min_hindsight_version TEXT,
    version TEXT,
    source_url TEXT,
    source_revision TEXT,
    description TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    tags JSONB NOT NULL DEFAULT '[]',
    retain_mission TEXT NOT NULL DEFAULT '',
    reflect_mission TEXT NOT NULL DEFAULT '',
    observations_mission TEXT,
    retain_extraction_mode TEXT NOT NULL DEFAULT 'concise'
        CHECK (retain_extraction_mode IN ('concise', 'verbose', 'custom', 'verbatim', 'chunks')),
    retain_custom_instructions TEXT,
    retain_chunk_size INTEGER,
    retain_default_strategy TEXT,
    retain_strategies JSONB NOT NULL DEFAULT '{}',
    entity_labels JSONB NOT NULL DEFAULT '[]',
    entities_allow_free_form BOOLEAN NOT NULL DEFAULT true,
    enable_observations BOOLEAN NOT NULL DEFAULT true,
    consolidation_llm_batch_size INTEGER,
    consolidation_source_facts_max_tokens INTEGER,
    consolidation_source_facts_max_tokens_per_observation INTEGER,
    disposition_skepticism INTEGER NOT NULL DEFAULT 3 CHECK (disposition_skepticism BETWEEN 1 AND 5),
    disposition_literalism INTEGER NOT NULL DEFAULT 3 CHECK (disposition_literalism BETWEEN 1 AND 5),
    disposition_empathy INTEGER NOT NULL DEFAULT 3 CHECK (disposition_empathy BETWEEN 1 AND 5),
    directive_seeds JSONB NOT NULL DEFAULT '[]',
    mental_model_seeds JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (scope = 'server' AND owner IS NULL) OR
        (scope = 'personal' AND owner IS NOT NULL)
    )
);
-- Sourced templates: unique by (id, scope, source_name, owner)
CREATE UNIQUE INDEX IF NOT EXISTS bank_templates_sourced_uniq
    ON bank_templates (id, scope, source_name, COALESCE(owner, ''))
    WHERE source_name IS NOT NULL;
-- Custom templates (no source): unique by (id, scope, owner)
CREATE UNIQUE INDEX IF NOT EXISTS bank_templates_custom_uniq
    ON bank_templates (id, scope, COALESCE(owner, ''))
    WHERE source_name IS NULL;

CREATE TABLE IF NOT EXISTS template_sources (
    name       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    auth_token TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add is_active to existing users table (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hindclaw_users' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE hindclaw_users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;
END $$;

-- Seed built-in policies (idempotent)
INSERT INTO hindclaw_policies (id, display_name, document_json, is_builtin) VALUES
    ('bank:readwrite', 'Bank Read/Write', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:recall","bank:reflect","bank:retain"],"banks":["*"]}]}', TRUE),
    ('bank:readonly', 'Bank Read-Only', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:recall","bank:reflect"],"banks":["*"]}]}', TRUE),
    ('bank:retain-only', 'Bank Retain-Only', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:retain"],"banks":["*"]}]}', TRUE),
    ('bank:admin', 'Bank Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:*"],"banks":["*"]}]}', TRUE),
    ('iam:admin', 'IAM Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["iam:*"],"banks":["*"]}]}', TRUE),
    ('template:admin', 'Template Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["template:list","template:create","template:install","template:manage","template:source","bank:create"],"banks":["*"]}]}', TRUE)
ON CONFLICT (id) DO NOTHING;
"""

# Migration: drop old tables replaced by policies + bank policies
_MIGRATION_V2 = """\
DROP TABLE IF EXISTS hindclaw_bank_permissions;
DROP TABLE IF EXISTS hindclaw_strategy_scopes;

-- Strip permission columns from groups (idempotent)
DO $$
BEGIN
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS recall;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS retain;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS retain_roles;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS retain_tags;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS retain_every_n_turns;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS recall_budget;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS recall_max_tokens;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS recall_tag_groups;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS llm_model;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS llm_provider;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS exclude_providers;
    ALTER TABLE hindclaw_groups DROP COLUMN IF EXISTS retain_strategy;
END $$;

DELETE FROM hindclaw_groups WHERE id = '_default';
"""

_MIGRATION_V3 = """\
-- V3: bank_templates table is created in DDL (IF NOT EXISTS).
SELECT 1;
"""

_MIGRATION_V4 = """\
-- Add template:source action to template:admin builtin policy
UPDATE hindclaw_policies
SET document_json = '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["template:list","template:create","template:install","template:manage","template:source","bank:create"],"banks":["*"]}]}'
WHERE id = 'template:admin' AND is_builtin = TRUE;
"""


async def get_pool() -> asyncpg.Pool:
    """Get or create the shared asyncpg connection pool.

    Lazily initializes the pool on first call. Runs DDL to ensure hindclaw
    tables exist. Thread-safe via asyncio.Lock.

    Returns:
        The shared asyncpg connection pool.

    Raises:
        RuntimeError: If HINDSIGHT_API_DATABASE_URL is not set.
    """
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        url = os.environ.get("HINDCLAW_DATABASE_URL") or os.environ.get("HINDSIGHT_API_DATABASE_URL")
        if not url:
            raise RuntimeError("HINDCLAW_DATABASE_URL or HINDSIGHT_API_DATABASE_URL environment variable must be set")
        _pool = await asyncpg.create_pool(url, min_size=2, max_size=10)
        # Run DDL in a transaction — all-or-nothing table creation
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(_DDL)
            async with conn.transaction():
                await conn.execute(_MIGRATION_V2)
            async with conn.transaction():
                await conn.execute(_MIGRATION_V3)
            async with conn.transaction():
                await conn.execute(_MIGRATION_V4)
            # Seed root user if env vars are set (outside DDL transaction)
            root_user = os.environ.get("HINDCLAW_ROOT_USER")
            root_key = os.environ.get("HINDCLAW_ROOT_API_KEY")
            if root_user and root_key:
                await conn.execute(
                    "INSERT INTO hindclaw_users (id, display_name) VALUES ($1, $1) ON CONFLICT (id) DO NOTHING",
                    root_user,
                )
                await conn.execute(
                    "INSERT INTO hindclaw_api_keys (id, api_key, user_id, description) VALUES ($1 || '-root-key', $2, $1, 'Root API key (bootstrap)') ON CONFLICT (id) DO NOTHING",
                    root_user,
                    root_key,
                )
                await conn.execute(
                    "INSERT INTO hindclaw_policy_attachments (policy_id, principal_type, principal_id, priority) VALUES ('iam:admin', 'user', $1, 0) ON CONFLICT DO NOTHING",
                    root_user,
                )
                await conn.execute(
                    "INSERT INTO hindclaw_policy_attachments (policy_id, principal_type, principal_id, priority) VALUES ('bank:admin', 'user', $1, 0) ON CONFLICT DO NOTHING",
                    root_user,
                )
                logger.info("Root user '%s' ensured with admin policies", root_user)
        logger.info("Hindclaw DB pool initialized, tables ensured")
        return _pool


def _parse_json(val: str | list | dict | None) -> list | dict | None:
    """Parse JSONB value from asyncpg row.

    asyncpg may return JSONB columns as strings depending on driver version.

    Args:
        val: Raw value from asyncpg — may be None, str, list, or dict.

    Returns:
        Parsed Python object, or None if input is None.
    """
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    return json.loads(val)


# --- Query functions ---


async def get_user_by_channel(provider: str, sender_id: str) -> UserRecord | None:
    """Resolve a channel sender ID to a user.

    Args:
        provider: Channel provider name (e.g., "telegram", "slack").
        sender_id: Provider-specific sender identifier.

    Returns:
        UserRecord if found, None if the sender is not mapped to any user.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT u.id, u.display_name, u.email, u.is_active
        FROM hindclaw_users u
        JOIN hindclaw_user_channels c ON c.user_id = u.id
        WHERE c.provider = $1 AND c.sender_id = $2
        """,
        provider,
        sender_id,
    )
    if row is None:
        return None
    return UserRecord(id=row["id"], display_name=row["display_name"], email=row["email"], is_active=row["is_active"])


async def get_api_key(api_key: str) -> ApiKeyRecord | None:
    """Look up an API key by its value.

    Args:
        api_key: The full API key string (e.g., "hc_alice_xxxxxxxxxxxx").

    Returns:
        ApiKeyRecord if found, None if the key does not exist.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, api_key, user_id, description FROM hindclaw_api_keys WHERE api_key = $1",
        api_key,
    )
    if row is None:
        return None
    return ApiKeyRecord(id=row["id"], api_key=row["api_key"], user_id=row["user_id"], description=row["description"])


async def get_user_groups(user_id: str) -> list[GroupRecord]:
    """Get all groups a user belongs to, ordered alphabetically.

    Args:
        user_id: Canonical user identifier.

    Returns:
        List of GroupRecord for each group the user is a member of.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT g.id, g.display_name
        FROM hindclaw_groups g
        JOIN hindclaw_group_members m ON m.group_id = g.id
        WHERE m.user_id = $1
        ORDER BY g.id
        """,
        user_id,
    )
    return [GroupRecord(id=r["id"], display_name=r["display_name"]) for r in rows]






# --- Policy query functions (MinIO-style access model) ---


async def get_policy(policy_id: str) -> PolicyRecord | None:
    """Fetch a single access policy by ID.

    Args:
        policy_id: Policy identifier.

    Returns:
        PolicyRecord if found, None otherwise.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, display_name, document_json, is_builtin FROM hindclaw_policies WHERE id = $1",
        policy_id,
    )
    if row is None:
        return None
    return PolicyRecord(
        id=row["id"], display_name=row["display_name"],
        document_json=_parse_json(row["document_json"]),
        is_builtin=row["is_builtin"],
    )


async def get_policies_for_user(
    user_id: str, group_ids: list[str]
) -> list[AttachedPolicyRecord]:
    """Fetch all access policies for a user: direct attachments + group attachments.

    Returns AttachedPolicyRecord instances with policy fields + attachment
    metadata (principal_type, principal_id, priority) for the policy engine
    to process.

    Args:
        user_id: Canonical user identifier.
        group_ids: List of group IDs the user belongs to.

    Returns:
        List of AttachedPolicyRecord, ordered by priority.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT p.id, p.display_name, p.document_json, p.is_builtin,
               a.principal_type, a.principal_id, a.priority
        FROM hindclaw_policies p
        JOIN hindclaw_policy_attachments a ON a.policy_id = p.id
        WHERE (a.principal_type = 'user' AND a.principal_id = $1)
           OR (a.principal_type = 'group' AND a.principal_id = ANY($2))
        ORDER BY a.priority DESC, p.id ASC
        """,
        user_id,
        group_ids,
    )
    return [
        AttachedPolicyRecord(
            id=r["id"],
            display_name=r["display_name"],
            document_json=_parse_json(r["document_json"]),
            is_builtin=r["is_builtin"],
            principal_type=r["principal_type"],
            principal_id=r["principal_id"],
            priority=r["priority"],
        )
        for r in rows
    ]


async def get_service_account_by_api_key(api_key: str) -> ServiceAccountRecord | None:
    """Look up a service account by its API key.

    Args:
        api_key: The full API key string (prefix hc_sa_).

    Returns:
        ServiceAccountRecord if found, None otherwise. Caller must check is_active.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT sa.id, sa.owner_user_id, sa.scoping_policy_id,
               sa.display_name, sa.is_active
        FROM hindclaw_service_accounts sa
        JOIN hindclaw_service_account_keys k ON k.service_account_id = sa.id
        WHERE k.api_key = $1
        """,
        api_key,
    )
    if row is None:
        return None
    return ServiceAccountRecord(
        id=row["id"], owner_user_id=row["owner_user_id"],
        scoping_policy_id=row["scoping_policy_id"],
        display_name=row["display_name"], is_active=row["is_active"],
    )


async def get_bank_policy(bank_id: str) -> BankPolicyRecord | None:
    """Fetch the bank policy document for a bank.

    Args:
        bank_id: Hindsight bank identifier.

    Returns:
        BankPolicyRecord if found, None otherwise.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT bank_id, document_json FROM hindclaw_bank_policies WHERE bank_id = $1",
        bank_id,
    )
    if row is None:
        return None
    return BankPolicyRecord(
        bank_id=row["bank_id"],
        document_json=_parse_json(row["document_json"]),
    )


async def get_user(user_id: str) -> UserRecord | None:
    """Fetch a user by ID.

    Args:
        user_id: User identifier.

    Returns:
        UserRecord if found, None otherwise.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, display_name, email, is_active FROM hindclaw_users WHERE id = $1",
        user_id,
    )
    if row is None:
        return None
    return UserRecord(
        id=row["id"], display_name=row["display_name"],
        email=row.get("email"), is_active=row["is_active"],
    )


async def get_service_account(sa_id: str) -> ServiceAccountRecord | None:
    """Fetch a service account by ID.

    Args:
        sa_id: Service account identifier.

    Returns:
        ServiceAccountRecord if found, None otherwise.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, owner_user_id, display_name, is_active, scoping_policy_id"
        " FROM hindclaw_service_accounts WHERE id = $1",
        sa_id,
    )
    if row is None:
        return None
    return ServiceAccountRecord(
        id=row["id"], owner_user_id=row["owner_user_id"],
        display_name=row["display_name"], is_active=row["is_active"],
        scoping_policy_id=row.get("scoping_policy_id"),
    )


# --- CRUD functions (policies, attachments, service accounts, bank policies) ---


async def create_policy(policy_id: str, display_name: str, document_json: dict) -> None:
    """Create an access policy."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_policies (id, display_name, document_json) VALUES ($1, $2, $3::jsonb)",
        policy_id, display_name, json.dumps(document_json),
    )

async def update_policy(policy_id: str, display_name: str | None, document_json: dict | None) -> bool:
    """Update an access policy. Returns True if found."""
    pool = await get_pool()
    parts, params = [], [policy_id]
    idx = 2
    if display_name is not None:
        parts.append(f"display_name = ${idx}")
        params.append(display_name)
        idx += 1
    if document_json is not None:
        parts.append(f"document_json = ${idx}::jsonb")
        params.append(json.dumps(document_json))
        idx += 1
    if not parts:
        return True
    parts.append("updated_at = NOW()")
    result = await pool.execute(
        f"UPDATE hindclaw_policies SET {', '.join(parts)} WHERE id = $1 AND is_builtin = FALSE",
        *params,
    )
    return result != "UPDATE 0"

async def delete_policy(policy_id: str) -> None:
    """Delete an access policy (not built-in)."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_policies WHERE id = $1 AND is_builtin = FALSE", policy_id)

async def list_policies() -> list[PolicyRecord]:
    """List all access policies."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, display_name, document_json, is_builtin FROM hindclaw_policies ORDER BY id")
    return [PolicyRecord(id=r["id"], display_name=r["display_name"], document_json=_parse_json(r["document_json"]), is_builtin=r["is_builtin"]) for r in rows]

async def create_policy_attachment(policy_id: str, principal_type: str, principal_id: str, priority: int = 0) -> None:
    """Attach a policy to a principal."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO hindclaw_policy_attachments (policy_id, principal_type, principal_id, priority)
           VALUES ($1, $2, $3, $4) ON CONFLICT (policy_id, principal_type, principal_id) DO UPDATE SET priority = $4""",
        policy_id, principal_type, principal_id, priority,
    )

async def delete_policy_attachment(policy_id: str, principal_type: str, principal_id: str) -> None:
    """Remove a policy attachment."""
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM hindclaw_policy_attachments WHERE policy_id = $1 AND principal_type = $2 AND principal_id = $3",
        policy_id, principal_type, principal_id,
    )

async def list_policy_attachments(policy_id: str) -> list[PolicyAttachmentRecord]:
    """List all attachments for a policy."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT policy_id, principal_type, principal_id, priority FROM hindclaw_policy_attachments WHERE policy_id = $1 ORDER BY principal_type, principal_id",
        policy_id,
    )
    return [PolicyAttachmentRecord(policy_id=r["policy_id"], principal_type=r["principal_type"], principal_id=r["principal_id"], priority=r["priority"]) for r in rows]

async def get_policy_attachment(policy_id: str, principal_type: str, principal_id: str) -> PolicyAttachmentRecord | None:
    """Fetch a single policy attachment."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT policy_id, principal_type, principal_id, priority FROM hindclaw_policy_attachments WHERE policy_id = $1 AND principal_type = $2 AND principal_id = $3",
        policy_id, principal_type, principal_id,
    )
    if row is None:
        return None
    return PolicyAttachmentRecord(policy_id=row["policy_id"], principal_type=row["principal_type"], principal_id=row["principal_id"], priority=row["priority"])

async def create_service_account(sa_id: str, owner_user_id: str, display_name: str, scoping_policy_id: str | None = None) -> None:
    """Create a service account."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_service_accounts (id, owner_user_id, display_name, scoping_policy_id) VALUES ($1, $2, $3, $4)",
        sa_id, owner_user_id, display_name, scoping_policy_id,
    )

async def update_service_account(sa_id: str, *, display_name: str | None = None, scoping_policy_id: str | None = None, is_active: bool | None = None) -> bool:
    """Update a service account. Returns True if found."""
    pool = await get_pool()
    parts, params = [], [sa_id]
    idx = 2
    if display_name is not None:
        parts.append(f"display_name = ${idx}")
        params.append(display_name)
        idx += 1
    if scoping_policy_id is not None:
        parts.append(f"scoping_policy_id = ${idx}")
        params.append(scoping_policy_id)
        idx += 1
    if is_active is not None:
        parts.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1
    if not parts:
        return True
    result = await pool.execute(f"UPDATE hindclaw_service_accounts SET {', '.join(parts)} WHERE id = $1", *params)
    return result != "UPDATE 0"

async def delete_service_account(sa_id: str) -> None:
    """Delete a service account (cascades to keys)."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_service_accounts WHERE id = $1", sa_id)

async def list_service_accounts() -> list[ServiceAccountRecord]:
    """List all service accounts."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, owner_user_id, display_name, is_active, scoping_policy_id FROM hindclaw_service_accounts ORDER BY id")
    return [ServiceAccountRecord(id=r["id"], owner_user_id=r["owner_user_id"], display_name=r["display_name"], is_active=r["is_active"], scoping_policy_id=r["scoping_policy_id"]) for r in rows]

async def create_sa_key(key_id: str, sa_id: str, api_key: str, description: str | None = None) -> None:
    """Create an API key for a service account."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_service_account_keys (id, service_account_id, api_key, description) VALUES ($1, $2, $3, $4)",
        key_id, sa_id, api_key, description,
    )

async def delete_sa_key(key_id: str, sa_id: str) -> None:
    """Delete an SA API key."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_service_account_keys WHERE id = $1 AND service_account_id = $2", key_id, sa_id)

async def list_sa_keys(sa_id: str) -> list[ServiceAccountKeyRecord]:
    """List API keys for a service account."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, api_key, description FROM hindclaw_service_account_keys WHERE service_account_id = $1 ORDER BY id", sa_id)
    return [ServiceAccountKeyRecord(id=r["id"], service_account_id=sa_id, api_key=r["api_key"], description=r["description"]) for r in rows]

async def get_sa_key(key_id: str, sa_id: str) -> ServiceAccountKeyRecord | None:
    """Fetch a single SA key."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT id, api_key, description FROM hindclaw_service_account_keys WHERE id = $1 AND service_account_id = $2", key_id, sa_id)
    if row is None:
        return None
    return ServiceAccountKeyRecord(id=row["id"], service_account_id=sa_id, api_key=row["api_key"], description=row["description"])

async def upsert_bank_policy(bank_id: str, document_json: dict) -> None:
    """Create or update a bank policy."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO hindclaw_bank_policies (bank_id, document_json) VALUES ($1, $2::jsonb)
           ON CONFLICT (bank_id) DO UPDATE SET document_json = $2::jsonb, updated_at = NOW()""",
        bank_id, json.dumps(document_json),
    )

async def delete_bank_policy(bank_id: str) -> None:
    """Delete a bank policy."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_bank_policies WHERE bank_id = $1", bank_id)


# --- Template queries ---


def _row_to_template(row) -> TemplateRecord:
    """Convert an asyncpg Record to a TemplateRecord.

    Args:
        row: asyncpg Record from bank_templates table.

    Returns:
        TemplateRecord with JSONB fields parsed.
    """
    d = dict(row)
    return TemplateRecord(
        id=d["id"],
        scope=d["scope"],
        owner=d.get("owner"),
        source_name=d.get("source_name"),
        schema_version=d["schema_version"],
        min_hindclaw_version=d["min_hindclaw_version"],
        min_hindsight_version=d.get("min_hindsight_version"),
        version=d.get("version"),
        source_url=d.get("source_url"),
        source_revision=d.get("source_revision"),
        description=d["description"],
        author=d.get("author", ""),
        tags=_parse_json(d["tags"]),
        retain_mission=d["retain_mission"],
        reflect_mission=d["reflect_mission"],
        observations_mission=d.get("observations_mission"),
        retain_extraction_mode=d["retain_extraction_mode"],
        retain_custom_instructions=d.get("retain_custom_instructions"),
        retain_chunk_size=d.get("retain_chunk_size"),
        retain_default_strategy=d.get("retain_default_strategy"),
        retain_strategies=_parse_json(d["retain_strategies"]),
        entity_labels=_parse_json(d["entity_labels"]),
        entities_allow_free_form=d["entities_allow_free_form"],
        enable_observations=d["enable_observations"],
        consolidation_llm_batch_size=d.get("consolidation_llm_batch_size"),
        consolidation_source_facts_max_tokens=d.get("consolidation_source_facts_max_tokens"),
        consolidation_source_facts_max_tokens_per_observation=d.get("consolidation_source_facts_max_tokens_per_observation"),
        disposition_skepticism=d["disposition_skepticism"],
        disposition_literalism=d["disposition_literalism"],
        disposition_empathy=d["disposition_empathy"],
        directive_seeds=_parse_json(d["directive_seeds"]),
        mental_model_seeds=_parse_json(d["mental_model_seeds"]),
        created_at=str(d["created_at"]),
        updated_at=str(d["updated_at"]),
    )


async def create_template(
    *,
    id: str,
    scope: str,
    owner: str | None,
    source_name: str | None,
    schema_version: int,
    min_hindclaw_version: str,
    min_hindsight_version: str | None = None,
    version: str | None = None,
    source_url: str | None = None,
    source_revision: str | None = None,
    description: str,
    author: str = "",
    tags: list[str],
    retain_mission: str,
    reflect_mission: str,
    observations_mission: str | None = None,
    retain_extraction_mode: str,
    retain_custom_instructions: str | None = None,
    retain_chunk_size: int | None = None,
    retain_default_strategy: str | None = None,
    retain_strategies: dict | None = None,
    entity_labels: list[dict] | None = None,
    entities_allow_free_form: bool = True,
    enable_observations: bool = True,
    consolidation_llm_batch_size: int | None = None,
    consolidation_source_facts_max_tokens: int | None = None,
    consolidation_source_facts_max_tokens_per_observation: int | None = None,
    disposition_skepticism: int = 3,
    disposition_literalism: int = 3,
    disposition_empathy: int = 3,
    directive_seeds: list[dict] | None = None,
    mental_model_seeds: list[dict] | None = None,
) -> TemplateRecord:
    """Insert a new bank template.

    Args:
        id: Template name.
        scope: 'server' or 'personal'.
        owner: User ID for personal scope, None for server.
        source_name: Marketplace source name (None if custom).
        schema_version: Template schema version.
        min_hindclaw_version: Minimum compatible Hindclaw version.
        min_hindsight_version: Minimum compatible Hindsight version.
        version: Semantic version from marketplace.
        source_url: Marketplace URL this was installed from.
        source_revision: Commit SHA or tag from marketplace.
        description: Human-readable description.
        author: Template author.
        tags: Searchable tags.
        retain_mission: Mission for retain operations.
        reflect_mission: Mission for reflect operations.
        observations_mission: Mission for observations.
        retain_extraction_mode: Extraction mode.
        retain_custom_instructions: Custom extraction prompt.
        retain_chunk_size: Max characters per chunk.
        retain_default_strategy: Default named strategy.
        retain_strategies: Named strategies with config overrides.
        entity_labels: Structured label vocabulary.
        entities_allow_free_form: Extract regular named entities.
        enable_observations: Toggle observation synthesis.
        consolidation_llm_batch_size: Facts per LLM call.
        consolidation_source_facts_max_tokens: Total token budget.
        consolidation_source_facts_max_tokens_per_observation: Per-observation budget.
        disposition_skepticism: 1-5 skepticism score.
        disposition_literalism: 1-5 literalism score.
        disposition_empathy: 1-5 empathy score.
        directive_seeds: Directive seeds list.
        mental_model_seeds: Mental model seeds list.

    Returns:
        The inserted row as a TemplateRecord.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO bank_templates (
            id, scope, owner, source_name, schema_version,
            min_hindclaw_version, min_hindsight_version, version,
            source_url, source_revision, description, author, tags,
            retain_mission, reflect_mission, observations_mission,
            retain_extraction_mode, retain_custom_instructions,
            retain_chunk_size, retain_default_strategy, retain_strategies,
            entity_labels, entities_allow_free_form, enable_observations,
            consolidation_llm_batch_size,
            consolidation_source_facts_max_tokens,
            consolidation_source_facts_max_tokens_per_observation,
            disposition_skepticism, disposition_literalism, disposition_empathy,
            directive_seeds, mental_model_seeds
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8,
            $9, $10, $11, $12, $13::jsonb,
            $14, $15, $16,
            $17, $18,
            $19, $20, $21::jsonb,
            $22::jsonb, $23, $24,
            $25, $26, $27,
            $28, $29, $30,
            $31::jsonb, $32::jsonb
        ) RETURNING *
        """,
        id, scope, owner, source_name, schema_version,
        min_hindclaw_version, min_hindsight_version, version,
        source_url, source_revision, description, author, json.dumps(tags),
        retain_mission, reflect_mission, observations_mission,
        retain_extraction_mode, retain_custom_instructions,
        retain_chunk_size, retain_default_strategy, json.dumps(retain_strategies or {}),
        json.dumps(entity_labels or []), entities_allow_free_form, enable_observations,
        consolidation_llm_batch_size,
        consolidation_source_facts_max_tokens,
        consolidation_source_facts_max_tokens_per_observation,
        disposition_skepticism, disposition_literalism, disposition_empathy,
        json.dumps(directive_seeds or []), json.dumps(mental_model_seeds or []),
    )
    return _row_to_template(row)


async def get_template(
    id: str,
    scope: str,
    *,
    source_name: str | None,
    owner: str | None,
) -> TemplateRecord | None:
    """Fetch a single template by its composite key.

    Args:
        id: Template name.
        scope: 'server' or 'personal'.
        source_name: Marketplace source name (None for custom).
        owner: User ID for personal scope.

    Returns:
        TemplateRecord or None if not found.
    """
    pool = await get_pool()
    if source_name is not None:
        row = await pool.fetchrow(
            "SELECT * FROM bank_templates WHERE id = $1 AND scope = $2 AND source_name = $3 AND owner IS NOT DISTINCT FROM $4",
            id, scope, source_name, owner,
        )
    else:
        row = await pool.fetchrow(
            "SELECT * FROM bank_templates WHERE id = $1 AND scope = $2 AND source_name IS NULL AND owner IS NOT DISTINCT FROM $3",
            id, scope, owner,
        )
    return _row_to_template(row) if row else None


async def list_templates(
    *,
    scope: str | None = None,
    owner: str | None = None,
    source_name: str | None = None,
) -> list[TemplateRecord]:
    """List templates with optional filters.

    Args:
        scope: Filter by scope ('server' or 'personal').
        owner: Filter by owner user ID.
        source_name: Filter by marketplace source name.

    Returns:
        List of TemplateRecord instances.
    """
    pool = await get_pool()
    conditions = []
    params = []
    idx = 1
    if scope is not None:
        conditions.append(f"scope = ${idx}")
        params.append(scope)
        idx += 1
    if owner is not None:
        conditions.append(f"owner = ${idx}")
        params.append(owner)
        idx += 1
    if source_name is not None:
        conditions.append(f"source_name = ${idx}")
        params.append(source_name)
        idx += 1
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = await pool.fetch(
        f"SELECT * FROM bank_templates{where} ORDER BY source_name, id",
        *params,
    )
    return [_row_to_template(r) for r in rows]


async def update_template(
    id: str,
    scope: str,
    *,
    source_name: str | None,
    owner: str | None,
    updates: dict,
) -> TemplateRecord | None:
    """Update a template's fields.

    Args:
        id: Template name.
        scope: 'server' or 'personal'.
        source_name: Marketplace source name.
        owner: User ID for personal scope.
        updates: Dict of column names to new values.

    Returns:
        The updated TemplateRecord, or None if not found.
    """
    if not updates:
        return await get_template(id, scope, source_name=source_name, owner=owner)

    pool = await get_pool()
    set_clauses = []
    params = []
    idx = 1
    jsonb_cols = {"tags", "retain_strategies", "entity_labels", "directive_seeds", "mental_model_seeds"}
    for col, val in updates.items():
        if col in jsonb_cols:
            set_clauses.append(f"{col} = ${idx}::jsonb")
            params.append(json.dumps(val))
        else:
            set_clauses.append(f"{col} = ${idx}")
            params.append(val)
        idx += 1
    set_clauses.append("updated_at = now()")

    if source_name is not None:
        where = f"id = ${idx} AND scope = ${idx+1} AND source_name = ${idx+2} AND owner IS NOT DISTINCT FROM ${idx+3}"
        params.extend([id, scope, source_name, owner])
    else:
        where = f"id = ${idx} AND scope = ${idx+1} AND source_name IS NULL AND owner IS NOT DISTINCT FROM ${idx+2}"
        params.extend([id, scope, owner])

    row = await pool.fetchrow(
        f"UPDATE bank_templates SET {', '.join(set_clauses)} WHERE {where} RETURNING *",
        *params,
    )
    return _row_to_template(row) if row else None


async def delete_template(
    id: str,
    scope: str,
    *,
    source_name: str | None,
    owner: str | None,
) -> bool:
    """Delete a template.

    Args:
        id: Template name.
        scope: 'server' or 'personal'.
        source_name: Marketplace source name.
        owner: User ID for personal scope.

    Returns:
        True if a row was deleted, False if not found.
    """
    pool = await get_pool()
    if source_name is not None:
        result = await pool.execute(
            "DELETE FROM bank_templates WHERE id = $1 AND scope = $2 AND source_name = $3 AND owner IS NOT DISTINCT FROM $4",
            id, scope, source_name, owner,
        )
    else:
        result = await pool.execute(
            "DELETE FROM bank_templates WHERE id = $1 AND scope = $2 AND source_name IS NULL AND owner IS NOT DISTINCT FROM $3",
            id, scope, owner,
        )
    return result == "DELETE 1"


async def upsert_template_from_marketplace(
    *,
    id: str,
    scope: str,
    owner: str | None,
    source_name: str,
    source_url: str | None = None,
    source_revision: str | None = None,
    schema_version: int,
    min_hindclaw_version: str,
    min_hindsight_version: str | None = None,
    version: str,
    description: str,
    author: str = "",
    tags: list[str],
    retain_mission: str,
    reflect_mission: str,
    observations_mission: str | None = None,
    retain_extraction_mode: str,
    retain_custom_instructions: str | None = None,
    retain_chunk_size: int | None = None,
    retain_default_strategy: str | None = None,
    retain_strategies: dict | None = None,
    entity_labels: list[dict] | None = None,
    entities_allow_free_form: bool = True,
    enable_observations: bool = True,
    consolidation_llm_batch_size: int | None = None,
    consolidation_source_facts_max_tokens: int | None = None,
    consolidation_source_facts_max_tokens_per_observation: int | None = None,
    disposition_skepticism: int = 3,
    disposition_literalism: int = 3,
    disposition_empathy: int = 3,
    directive_seeds: list[dict] | None = None,
    mental_model_seeds: list[dict] | None = None,
) -> "TemplateRecord":
    """Insert or update a marketplace template.

    Uses a two-step approach in a transaction: check if exists, then
    INSERT or UPDATE. This avoids expression-index inference issues
    with ON CONFLICT on the COALESCE-based unique indexes.

    Args:
        id: Template name.
        scope: 'server' or 'personal'.
        owner: User ID for personal scope, None for server.
        source_name: Marketplace source name (must not be None).
        ... (remaining fields match create_template)

    Returns:
        The upserted TemplateRecord.
    """
    # Check if template already exists
    existing = await get_template(id, scope, source_name=source_name, owner=owner)

    if existing:
        # UPDATE all fields
        updates = {
            "schema_version": schema_version,
            "min_hindclaw_version": min_hindclaw_version,
            "min_hindsight_version": min_hindsight_version,
            "version": version,
            "source_url": source_url,
            "source_revision": source_revision,
            "description": description,
            "author": author,
            "tags": tags or [],
            "retain_mission": retain_mission,
            "reflect_mission": reflect_mission,
            "observations_mission": observations_mission,
            "retain_extraction_mode": retain_extraction_mode,
            "retain_custom_instructions": retain_custom_instructions,
            "retain_chunk_size": retain_chunk_size,
            "retain_default_strategy": retain_default_strategy,
            "retain_strategies": retain_strategies or {},
            "entity_labels": entity_labels or [],
            "entities_allow_free_form": entities_allow_free_form,
            "enable_observations": enable_observations,
            "consolidation_llm_batch_size": consolidation_llm_batch_size,
            "consolidation_source_facts_max_tokens": consolidation_source_facts_max_tokens,
            "consolidation_source_facts_max_tokens_per_observation": consolidation_source_facts_max_tokens_per_observation,
            "disposition_skepticism": disposition_skepticism,
            "disposition_literalism": disposition_literalism,
            "disposition_empathy": disposition_empathy,
            "directive_seeds": directive_seeds or [],
            "mental_model_seeds": mental_model_seeds or [],
        }
        result = await update_template(
            id, scope,
            source_name=source_name,
            owner=owner,
            updates=updates,
        )
        if result is None:
            raise RuntimeError(f"Failed to update template {id} in {scope} scope")
        return result
    else:
        # INSERT new
        return await create_template(
            id=id,
            scope=scope,
            owner=owner,
            source_name=source_name,
            schema_version=schema_version,
            min_hindclaw_version=min_hindclaw_version,
            min_hindsight_version=min_hindsight_version,
            version=version,
            source_url=source_url,
            source_revision=source_revision,
            description=description,
            author=author,
            tags=tags or [],
            retain_mission=retain_mission,
            reflect_mission=reflect_mission,
            observations_mission=observations_mission,
            retain_extraction_mode=retain_extraction_mode,
            retain_custom_instructions=retain_custom_instructions,
            retain_chunk_size=retain_chunk_size,
            retain_default_strategy=retain_default_strategy,
            retain_strategies=retain_strategies or {},
            entity_labels=entity_labels or [],
            entities_allow_free_form=entities_allow_free_form,
            enable_observations=enable_observations,
            consolidation_llm_batch_size=consolidation_llm_batch_size,
            consolidation_source_facts_max_tokens=consolidation_source_facts_max_tokens,
            consolidation_source_facts_max_tokens_per_observation=consolidation_source_facts_max_tokens_per_observation,
            disposition_skepticism=disposition_skepticism,
            disposition_literalism=disposition_literalism,
            disposition_empathy=disposition_empathy,
            directive_seeds=directive_seeds or [],
            mental_model_seeds=mental_model_seeds or [],
        )


# --- Template source queries ---


def _row_to_source(row) -> TemplateSourceRecord:
    """Convert an asyncpg Record to a TemplateSourceRecord.

    Args:
        row: asyncpg Record from template_sources table.

    Returns:
        TemplateSourceRecord with fields mapped.
    """
    d = dict(row)
    return TemplateSourceRecord(
        name=d["name"],
        url=d["url"],
        auth_token=d.get("auth_token"),
        created_at=str(d["created_at"]),
    )


async def create_template_source(
    name: str,
    url: str,
    auth_token: str | None = None,
) -> TemplateSourceRecord:
    """Create a marketplace template source.

    Args:
        name: Source name (derived from git org or admin-provided alias).
        url: Marketplace repository URL.
        auth_token: Optional auth token for private repositories.

    Returns:
        The created TemplateSourceRecord.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO template_sources (name, url, auth_token)
           VALUES ($1, $2, $3)
           RETURNING *""",
        name, url, auth_token,
    )
    return _row_to_source(row)


async def get_template_source(name: str) -> TemplateSourceRecord | None:
    """Get a marketplace source by name.

    Args:
        name: Source name.

    Returns:
        TemplateSourceRecord or None.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM template_sources WHERE name = $1",
        name,
    )
    return _row_to_source(row) if row else None


async def list_template_sources() -> list[TemplateSourceRecord]:
    """List all registered marketplace sources.

    Returns:
        List of TemplateSourceRecord instances, ordered by name.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM template_sources ORDER BY name",
    )
    return [_row_to_source(r) for r in rows]


async def delete_template_source(name: str) -> bool:
    """Delete a marketplace source.

    Args:
        name: Source name to delete.

    Returns:
        True if a row was deleted, False if not found.
    """
    pool = await get_pool()
    result = await pool.execute(
        "DELETE FROM template_sources WHERE name = $1",
        name,
    )
    return result == "DELETE 1"

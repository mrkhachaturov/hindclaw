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
from hindclaw_ext.template_models import TemplateScope

# Sentinel for partial-update functions: distinguishes "not provided" from "set to None".
# _UNSET = caller did not provide this argument (don't touch the column).
# None   = caller explicitly wants to set the column to SQL NULL.
# value  = caller wants to set the column to this value.
_UNSET: object = object()

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()

# Template and template_sources DDL — see spec Sections 4.3, 5. Pulled out of
# the main _DDL string so tests can introspect individual schemas.
BANK_TEMPLATES_DDL = """
CREATE TABLE IF NOT EXISTS bank_templates (
    row_id       BIGSERIAL PRIMARY KEY,

    id           TEXT NOT NULL,
    scope        TEXT NOT NULL CHECK (scope IN ('server', 'personal')),
    owner        TEXT,

    source_name        TEXT,
    source_scope       TEXT CHECK (source_scope IS NULL OR source_scope IN ('server', 'personal')),
    source_template_id TEXT,
    source_url         TEXT,
    source_revision    TEXT,

    name         TEXT NOT NULL,
    description  TEXT,
    category     TEXT,
    integrations JSONB NOT NULL DEFAULT '[]',
    tags         JSONB NOT NULL DEFAULT '[]',

    manifest     JSONB NOT NULL,

    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bank_templates_scope_owner
        CHECK ((scope = 'personal' AND owner IS NOT NULL)
            OR (scope = 'server' AND owner IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS bank_templates_natural_key
    ON bank_templates (id, scope, owner) NULLS NOT DISTINCT;

CREATE INDEX IF NOT EXISTS bank_templates_scope_owner_idx
    ON bank_templates (scope, owner);

CREATE INDEX IF NOT EXISTS bank_templates_source_idx
    ON bank_templates (source_name, source_scope);

CREATE INDEX IF NOT EXISTS bank_templates_category_idx
    ON bank_templates (category);

CREATE INDEX IF NOT EXISTS bank_templates_tags_gin
    ON bank_templates USING GIN (tags jsonb_path_ops);
"""

TEMPLATE_SOURCES_DDL = """
-- Drop any pre-surrogate-key version of template_sources so the CREATE below
-- gets the new shape. Safe per project rule: no DB migrations until production.
DROP TABLE IF EXISTS template_sources CASCADE;

CREATE TABLE IF NOT EXISTS template_sources (
    row_id       BIGSERIAL PRIMARY KEY,

    name         TEXT NOT NULL,
    scope        TEXT NOT NULL CHECK (scope IN ('server', 'personal')),
    owner        TEXT,
    url          TEXT NOT NULL,
    auth_token   TEXT,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT template_sources_scope_owner
        CHECK ((scope = 'personal' AND owner IS NOT NULL)
            OR (scope = 'server' AND owner IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS template_sources_natural_key
    ON template_sources (name, scope, owner) NULLS NOT DISTINCT;

CREATE INDEX IF NOT EXISTS template_sources_scope_owner_idx
    ON template_sources (scope, owner);
"""

# DDL for hindclaw tables — executed on first get_pool() call
_DDL = (
    """\
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

"""
    + BANK_TEMPLATES_DDL
    + TEMPLATE_SOURCES_DDL
    + """
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
    ('template:admin', 'Template Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["template:*","bank:create"],"banks":["*"]}]}', TRUE),
    ('template:user', 'Template User', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["template:list","template:create","template:install","template:manage","template:source","bank:create"],"banks":["*"]}]}', TRUE),
    ('iam:self-service', 'IAM Self-Service', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["iam:api_keys:read","iam:api_keys:write","iam:service_accounts:read","iam:service_accounts:write","iam:service_account_keys:write"],"banks":["*"]}]}', TRUE)
ON CONFLICT (id) DO NOTHING;
"""
)


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
            # Seed root user if env vars are set
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
                await conn.execute(
                    "INSERT INTO hindclaw_policy_attachments (policy_id, principal_type, principal_id, priority) VALUES ('template:admin', 'user', $1, 0) ON CONFLICT DO NOTHING",
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
    return UserRecord(
        id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        is_active=row["is_active"],
    )


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
    return ApiKeyRecord(
        id=row["id"],
        api_key=row["api_key"],
        user_id=row["user_id"],
        description=row["description"],
    )


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
        id=row["id"],
        display_name=row["display_name"],
        document_json=_parse_json(row["document_json"]),
        is_builtin=row["is_builtin"],
    )


async def get_policies_for_user(user_id: str, group_ids: list[str]) -> list[AttachedPolicyRecord]:
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
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        scoping_policy_id=row["scoping_policy_id"],
        display_name=row["display_name"],
        is_active=row["is_active"],
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
        id=row["id"],
        display_name=row["display_name"],
        email=row.get("email"),
        is_active=row["is_active"],
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
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        display_name=row["display_name"],
        is_active=row["is_active"],
        scoping_policy_id=row.get("scoping_policy_id"),
    )


# --- CRUD functions (policies, attachments, service accounts, bank policies) ---


async def create_policy(policy_id: str, display_name: str, document_json: dict) -> None:
    """Create an access policy."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_policies (id, display_name, document_json) VALUES ($1, $2, $3::jsonb)",
        policy_id,
        display_name,
        json.dumps(document_json),
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
    return [
        PolicyRecord(
            id=r["id"],
            display_name=r["display_name"],
            document_json=_parse_json(r["document_json"]),
            is_builtin=r["is_builtin"],
        )
        for r in rows
    ]


async def create_policy_attachment(policy_id: str, principal_type: str, principal_id: str, priority: int = 0) -> None:
    """Attach a policy to a principal."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO hindclaw_policy_attachments (policy_id, principal_type, principal_id, priority)
           VALUES ($1, $2, $3, $4) ON CONFLICT (policy_id, principal_type, principal_id) DO UPDATE SET priority = $4""",
        policy_id,
        principal_type,
        principal_id,
        priority,
    )


async def delete_policy_attachment(policy_id: str, principal_type: str, principal_id: str) -> None:
    """Remove a policy attachment."""
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM hindclaw_policy_attachments WHERE policy_id = $1 AND principal_type = $2 AND principal_id = $3",
        policy_id,
        principal_type,
        principal_id,
    )


async def list_policy_attachments(policy_id: str) -> list[PolicyAttachmentRecord]:
    """List all attachments for a policy."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT policy_id, principal_type, principal_id, priority FROM hindclaw_policy_attachments WHERE policy_id = $1 ORDER BY principal_type, principal_id",
        policy_id,
    )
    return [
        PolicyAttachmentRecord(
            policy_id=r["policy_id"],
            principal_type=r["principal_type"],
            principal_id=r["principal_id"],
            priority=r["priority"],
        )
        for r in rows
    ]


async def get_policy_attachment(
    policy_id: str, principal_type: str, principal_id: str
) -> PolicyAttachmentRecord | None:
    """Fetch a single policy attachment."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT policy_id, principal_type, principal_id, priority FROM hindclaw_policy_attachments WHERE policy_id = $1 AND principal_type = $2 AND principal_id = $3",
        policy_id,
        principal_type,
        principal_id,
    )
    if row is None:
        return None
    return PolicyAttachmentRecord(
        policy_id=row["policy_id"],
        principal_type=row["principal_type"],
        principal_id=row["principal_id"],
        priority=row["priority"],
    )


async def create_service_account(
    sa_id: str,
    owner_user_id: str,
    display_name: str,
    scoping_policy_id: str | None = None,
) -> None:
    """Create a service account."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_service_accounts (id, owner_user_id, display_name, scoping_policy_id) VALUES ($1, $2, $3, $4)",
        sa_id,
        owner_user_id,
        display_name,
        scoping_policy_id,
    )


async def update_service_account(
    sa_id: str,
    *,
    display_name: str | None | object = _UNSET,
    scoping_policy_id: str | None | object = _UNSET,
    is_active: bool | None | object = _UNSET,
) -> bool:
    """Update a service account. Returns True if found.

    Uses the _UNSET sentinel to distinguish "not provided" from "set to None":
        _UNSET  — do not touch the column
        None    — set column to SQL NULL
        <value> — set column to that value

    Args:
        sa_id: Service account ID.
        display_name: New display name, None to clear, or _UNSET to skip.
        scoping_policy_id: New policy ID, None to clear, or _UNSET to skip.
        is_active: New active state, None to clear, or _UNSET to skip.

    Returns:
        True if the service account was found (even if no columns changed).
    """
    pool = await get_pool()
    parts: list[str] = []
    params: list[object] = [sa_id]
    idx = 2
    if display_name is not _UNSET:
        parts.append(f"display_name = ${idx}")
        params.append(display_name)
        idx += 1
    if scoping_policy_id is not _UNSET:
        parts.append(f"scoping_policy_id = ${idx}")
        params.append(scoping_policy_id)
        idx += 1
    if is_active is not _UNSET:
        parts.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1
    if not parts:
        return True
    result = await pool.execute(
        f"UPDATE hindclaw_service_accounts SET {', '.join(parts)} WHERE id = $1",
        *params,
    )
    return result != "UPDATE 0"


async def delete_service_account(sa_id: str) -> None:
    """Delete a service account (cascades to keys)."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_service_accounts WHERE id = $1", sa_id)


async def list_service_accounts() -> list[ServiceAccountRecord]:
    """List all service accounts."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, owner_user_id, display_name, is_active, scoping_policy_id FROM hindclaw_service_accounts ORDER BY id"
    )
    return [
        ServiceAccountRecord(
            id=r["id"],
            owner_user_id=r["owner_user_id"],
            display_name=r["display_name"],
            is_active=r["is_active"],
            scoping_policy_id=r["scoping_policy_id"],
        )
        for r in rows
    ]


async def list_service_accounts_by_owner(
    owner_user_id: str,
) -> list[ServiceAccountRecord]:
    """List service accounts owned by a specific user.

    Args:
        owner_user_id: User ID to filter by.

    Returns:
        List of ServiceAccountRecord for the given owner.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, owner_user_id, display_name, is_active, scoping_policy_id "
        "FROM hindclaw_service_accounts WHERE owner_user_id = $1 ORDER BY id",
        owner_user_id,
    )
    return [
        ServiceAccountRecord(
            id=r["id"],
            owner_user_id=r["owner_user_id"],
            display_name=r["display_name"],
            is_active=r["is_active"],
            scoping_policy_id=r["scoping_policy_id"],
        )
        for r in rows
    ]


async def create_sa_key(key_id: str, sa_id: str, api_key: str, description: str | None = None) -> None:
    """Create an API key for a service account."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO hindclaw_service_account_keys (id, service_account_id, api_key, description) VALUES ($1, $2, $3, $4)",
        key_id,
        sa_id,
        api_key,
        description,
    )


async def delete_sa_key(key_id: str, sa_id: str) -> None:
    """Delete an SA API key."""
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM hindclaw_service_account_keys WHERE id = $1 AND service_account_id = $2",
        key_id,
        sa_id,
    )


async def list_sa_keys(sa_id: str) -> list[ServiceAccountKeyRecord]:
    """List API keys for a service account."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, api_key, description FROM hindclaw_service_account_keys WHERE service_account_id = $1 ORDER BY id",
        sa_id,
    )
    return [
        ServiceAccountKeyRecord(
            id=r["id"],
            service_account_id=sa_id,
            api_key=r["api_key"],
            description=r["description"],
        )
        for r in rows
    ]


async def get_sa_key(key_id: str, sa_id: str) -> ServiceAccountKeyRecord | None:
    """Fetch a single SA key."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, api_key, description FROM hindclaw_service_account_keys WHERE id = $1 AND service_account_id = $2",
        key_id,
        sa_id,
    )
    if row is None:
        return None
    return ServiceAccountKeyRecord(
        id=row["id"],
        service_account_id=sa_id,
        api_key=row["api_key"],
        description=row["description"],
    )


async def upsert_bank_policy(bank_id: str, document_json: dict) -> None:
    """Create or update a bank policy."""
    pool = await get_pool()
    await pool.execute(
        """INSERT INTO hindclaw_bank_policies (bank_id, document_json) VALUES ($1, $2::jsonb)
           ON CONFLICT (bank_id) DO UPDATE SET document_json = $2::jsonb, updated_at = NOW()""",
        bank_id,
        json.dumps(document_json),
    )


async def delete_bank_policy(bank_id: str) -> None:
    """Delete a bank policy."""
    pool = await get_pool()
    await pool.execute("DELETE FROM hindclaw_bank_policies WHERE bank_id = $1", bank_id)


# --- Template queries ---


def _row_to_template_record(row) -> TemplateRecord:
    """Translate an asyncpg row into a TemplateRecord dataclass."""

    def _loads(value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    return TemplateRecord(
        id=row["id"],
        scope=TemplateScope(row["scope"]),
        owner=row["owner"],
        source_name=row["source_name"],
        source_scope=TemplateScope(row["source_scope"]) if row["source_scope"] else None,
        source_template_id=row["source_template_id"],
        source_url=row["source_url"],
        source_revision=row["source_revision"],
        name=row["name"],
        description=row["description"],
        category=row["category"],
        integrations=_loads(row["integrations"]) or [],
        tags=_loads(row["tags"]) or [],
        manifest=_loads(row["manifest"]) or {},
        installed_at=row["installed_at"],
        updated_at=row["updated_at"],
    )


_TEMPLATE_COLUMNS = """
    id, scope, owner,
    source_name, source_scope, source_template_id,
    source_url, source_revision,
    name, description, category,
    integrations, tags, manifest,
    installed_at, updated_at
"""


async def create_template(pool, record: TemplateRecord) -> None:
    """Insert a new template row. Upsert on the natural key — reinstalling
    the same (id, scope, owner) replaces the existing row regardless of
    source. Section 4.2 identity invariant."""
    await pool.execute(
        """
        INSERT INTO bank_templates (
            id, scope, owner,
            source_name, source_scope, source_template_id,
            source_url, source_revision,
            name, description, category,
            integrations, tags, manifest,
            installed_at, updated_at
        ) VALUES (
            $1, $2, $3,
            $4, $5, $6,
            $7, $8,
            $9, $10, $11,
            $12::jsonb, $13::jsonb, $14::jsonb,
            $15, $16
        )
        ON CONFLICT (id, scope, owner) DO UPDATE SET
            source_name        = EXCLUDED.source_name,
            source_scope       = EXCLUDED.source_scope,
            source_template_id = EXCLUDED.source_template_id,
            source_url         = EXCLUDED.source_url,
            source_revision    = EXCLUDED.source_revision,
            name               = EXCLUDED.name,
            description        = EXCLUDED.description,
            category           = EXCLUDED.category,
            integrations       = EXCLUDED.integrations,
            tags               = EXCLUDED.tags,
            manifest           = EXCLUDED.manifest,
            updated_at         = EXCLUDED.updated_at
        """,
        record.id,
        record.scope.value,
        record.owner,
        record.source_name,
        record.source_scope.value if record.source_scope is not None else None,
        record.source_template_id,
        record.source_url,
        record.source_revision,
        record.name,
        record.description,
        record.category,
        json.dumps(record.integrations),
        json.dumps(record.tags),
        json.dumps(record.manifest),
        record.installed_at,
        record.updated_at,
    )


async def get_template(
    pool,
    *,
    id: str,
    scope: TemplateScope,
    owner: str | None,
) -> TemplateRecord | None:
    row = await pool.fetchrow(
        f"""
        SELECT {_TEMPLATE_COLUMNS}
        FROM bank_templates
        WHERE id = $1
          AND scope = $2
          AND owner IS NOT DISTINCT FROM $3
        """,
        id,
        scope.value,
        owner,
    )
    return _row_to_template_record(row) if row else None


async def list_templates(
    pool,
    *,
    scope: TemplateScope,
    owner: str | None,
    category: str | None = None,
    tag: str | None = None,
) -> list[TemplateRecord]:
    clauses = [
        "scope = $1",
        "owner IS NOT DISTINCT FROM $2",
    ]
    params: list = [scope.value, owner]

    if category is not None:
        clauses.append(f"category = ${len(params) + 1}")
        params.append(category)

    if tag is not None:
        clauses.append(f"tags @> ${len(params) + 1}::jsonb")
        params.append(json.dumps([tag]))

    sql = f"""
        SELECT {_TEMPLATE_COLUMNS}
        FROM bank_templates
        WHERE {" AND ".join(clauses)}
        ORDER BY name
    """
    rows = await pool.fetch(sql, *params)
    return [_row_to_template_record(row) for row in rows]


async def update_template(pool, record: TemplateRecord) -> None:
    """In-place update — identity tuple unchanged."""
    await pool.execute(
        """
        UPDATE bank_templates SET
            source_name        = $4,
            source_scope       = $5,
            source_template_id = $6,
            source_url         = $7,
            source_revision    = $8,
            name               = $9,
            description        = $10,
            category           = $11,
            integrations       = $12::jsonb,
            tags               = $13::jsonb,
            manifest           = $14::jsonb,
            updated_at         = $15
        WHERE id = $1
          AND scope = $2
          AND owner IS NOT DISTINCT FROM $3
        """,
        record.id,
        record.scope.value,
        record.owner,
        record.source_name,
        record.source_scope.value if record.source_scope is not None else None,
        record.source_template_id,
        record.source_url,
        record.source_revision,
        record.name,
        record.description,
        record.category,
        json.dumps(record.integrations),
        json.dumps(record.tags),
        json.dumps(record.manifest),
        record.updated_at,
    )


async def delete_template(
    pool,
    *,
    id: str,
    scope: TemplateScope,
    owner: str | None,
) -> bool:
    result = await pool.execute(
        """
        DELETE FROM bank_templates
        WHERE id = $1
          AND scope = $2
          AND owner IS NOT DISTINCT FROM $3
        """,
        id,
        scope.value,
        owner,
    )
    if isinstance(result, str):
        return result.endswith("1")
    return bool(result)


async def fetch_installed_template_for_apply(
    pool,
    *,
    template: str,
    current_user: str | None,
) -> TemplateRecord | None:
    """Parse a scope/id ref and look up the installed row.

    Personal refs scope to the current user; server refs scope to owner NULL.
    """
    if "/" not in template:
        raise ValueError(f"template must be '{{scope}}/{{id}}', got {template!r}")
    scope_part, _, id_part = template.partition("/")
    try:
        scope = TemplateScope(scope_part)
    except ValueError as exc:
        raise ValueError(f"template scope must be 'personal' or 'server', got {scope_part!r}") from exc
    if not id_part:
        raise ValueError(f"template id must be non-empty, got {template!r}")

    if scope is TemplateScope.PERSONAL:
        row = await pool.fetchrow(
            f"""
            SELECT {_TEMPLATE_COLUMNS}
            FROM bank_templates
            WHERE id = $1
              AND scope = 'personal'
              AND owner = $2
            """,
            id_part,
            current_user,
        )
    else:
        row = await pool.fetchrow(
            f"""
            SELECT {_TEMPLATE_COLUMNS}
            FROM bank_templates
            WHERE id = $1
              AND scope = 'server'
              AND owner IS NULL
            """,
            id_part,
        )
    return _row_to_template_record(row) if row else None


# --- Template source queries ---


def _row_to_source(row) -> TemplateSourceRecord:
    """Convert an asyncpg Record to a TemplateSourceRecord."""
    d = dict(row)
    return TemplateSourceRecord(
        name=d["name"],
        url=d["url"],
        scope=d["scope"],
        owner=d.get("owner"),
        auth_token=d.get("auth_token"),
        description=d.get("description"),
        created_at=str(d["created_at"]) if d.get("created_at") else None,
        updated_at=str(d["updated_at"]) if d.get("updated_at") else None,
    )


async def create_template_source(
    name: str,
    url: str,
    scope: str = "server",
    owner: str | None = None,
    auth_token: str | None = None,
    description: str | None = None,
) -> TemplateSourceRecord:
    """Create a marketplace template source.

    Additive `description` kwarg persists a human-readable label so the
    default-source hook (Plan C) can seed rows with context.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO template_sources (name, url, scope, owner, auth_token, description)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING *""",
        name,
        url,
        scope,
        owner,
        auth_token,
        description,
    )
    return _row_to_source(row)


async def get_template_source(
    name: str,
    scope: str | None = None,
    owner: str | None = None,
) -> TemplateSourceRecord | None:
    """Get a marketplace source by the natural key (name, scope, owner).

    Signature preserved from the prior revision for callers that still
    pass only ``name``; the WHERE clause now always filters on all three
    components via ``IS NOT DISTINCT FROM`` so scope=None/owner=None
    collapses to an exact NULL match rather than an unscoped fuzzy match.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT row_id, name, scope, owner, url, auth_token, description,
               created_at, updated_at
        FROM template_sources
        WHERE name = $1
          AND scope IS NOT DISTINCT FROM $2
          AND owner IS NOT DISTINCT FROM $3
        """,
        name,
        scope,
        owner,
    )
    return _row_to_source(row) if row else None


async def list_template_sources(
    *,
    scope: str | None = None,
    owner: str | None = None,
) -> list[TemplateSourceRecord]:
    """List registered marketplace sources, optionally filtered by scope and owner."""
    pool = await get_pool()
    if scope == "personal" and owner is not None:
        rows = await pool.fetch(
            "SELECT * FROM template_sources WHERE scope = $1 AND owner = $2 ORDER BY name",
            scope,
            owner,
        )
    elif scope is not None:
        rows = await pool.fetch(
            "SELECT * FROM template_sources WHERE scope = $1 ORDER BY name",
            scope,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM template_sources ORDER BY name",
        )
    return [_row_to_source(r) for r in rows]


async def resolve_source(
    name: str,
    caller: str,
    source_scope: str | None = None,
) -> TemplateSourceRecord:
    """Resolve a source by name for the given caller.

    Queries server sources and the caller's personal sources for a name.
    If source_scope is specified, filters to that scope only.

    Args:
        name: Source name to resolve.
        caller: User ID of the calling user (for personal source lookup).
        source_scope: Optional scope filter ('server' or 'personal').

    Returns:
        The matching TemplateSourceRecord.

    Raises:
        KeyError: If no matching source is found.
        ValueError: If multiple sources match and scope is ambiguous.
    """
    pool = await get_pool()
    if source_scope is not None:
        if source_scope == "personal":
            rows = await pool.fetch(
                "SELECT * FROM template_sources WHERE name = $1 AND scope = 'personal' AND owner = $2",
                name,
                caller,
            )
        else:
            rows = await pool.fetch(
                "SELECT * FROM template_sources WHERE name = $1 AND scope = $2",
                name,
                source_scope,
            )
    else:
        rows = await pool.fetch(
            """SELECT * FROM template_sources
               WHERE name = $1
                 AND (scope = 'server' OR (scope = 'personal' AND owner = $2))""",
            name,
            caller,
        )
    if len(rows) == 0:
        raise KeyError(f"Source not found: {name!r}")
    if len(rows) > 1:
        raise ValueError(f"Ambiguous source {name!r}: matches both server and personal scopes")
    return _row_to_source(rows[0])


async def delete_template_source(
    name: str,
    scope: str = "server",
    owner: str | None = None,
) -> bool:
    """Delete a marketplace source.

    Args:
        name: Source name to delete.
        scope: Scope of the source ('server' or 'personal').
        owner: Owner user ID for personal sources; must be None for server sources.

    Returns:
        True if a row was deleted, False if not found.
    """
    pool = await get_pool()
    if scope == "personal" and owner is not None:
        result = await pool.execute(
            "DELETE FROM template_sources WHERE name = $1 AND scope = $2 AND owner = $3",
            name,
            scope,
            owner,
        )
    else:
        result = await pool.execute(
            "DELETE FROM template_sources WHERE name = $1 AND scope = $2 AND owner IS NULL",
            name,
            scope,
        )
    return result == "DELETE 1"

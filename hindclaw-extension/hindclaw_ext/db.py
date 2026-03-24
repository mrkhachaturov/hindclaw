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
    BankPermissionRecord,
    BankPolicyRecord,
    GroupRecord,
    PolicyRecord,
    ServiceAccountKeyRecord,
    ServiceAccountRecord,
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
    id              TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    recall          BOOLEAN,
    retain          BOOLEAN,
    retain_roles    JSONB,
    retain_tags     JSONB,
    retain_every_n_turns INTEGER,
    recall_budget   TEXT CHECK (recall_budget IN ('low', 'mid', 'high')),
    recall_max_tokens INTEGER,
    recall_tag_groups JSONB,
    llm_model       TEXT,
    llm_provider    TEXT,
    exclude_providers JSONB,
    retain_strategy TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hindclaw_group_members (
    group_id TEXT NOT NULL REFERENCES hindclaw_groups(id) ON DELETE CASCADE,
    user_id  TEXT NOT NULL REFERENCES hindclaw_users(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS hindclaw_bank_permissions (
    bank_id         TEXT NOT NULL,
    scope_type      TEXT NOT NULL CHECK (scope_type IN ('group', 'user')),
    scope_id        TEXT NOT NULL,
    recall          BOOLEAN,
    retain          BOOLEAN,
    retain_roles    JSONB,
    retain_tags     JSONB,
    retain_every_n_turns INTEGER,
    recall_budget   TEXT CHECK (recall_budget IN ('low', 'mid', 'high')),
    recall_max_tokens INTEGER,
    recall_tag_groups JSONB,
    llm_model       TEXT,
    llm_provider    TEXT,
    exclude_providers JSONB,
    retain_strategy TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (bank_id, scope_type, scope_id)
);

CREATE TABLE IF NOT EXISTS hindclaw_strategy_scopes (
    bank_id     TEXT NOT NULL,
    scope_type  TEXT NOT NULL CHECK (scope_type IN ('agent', 'channel', 'topic', 'group', 'user')),
    scope_value TEXT NOT NULL,
    strategy    TEXT NOT NULL,
    UNIQUE (bank_id, scope_type, scope_value)
);

-- New tables for MinIO-style access model

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

INSERT INTO hindclaw_groups (id, display_name, recall, retain)
VALUES ('_default', 'Anonymous', false, false)
ON CONFLICT DO NOTHING;

-- Seed built-in policies (idempotent)
INSERT INTO hindclaw_policies (id, display_name, document_json, is_builtin) VALUES
    ('bank:readwrite', 'Bank Read/Write', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:recall","bank:reflect","bank:retain"],"banks":["*"]}]}', TRUE),
    ('bank:readonly', 'Bank Read-Only', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:recall","bank:reflect"],"banks":["*"]}]}', TRUE),
    ('bank:retain-only', 'Bank Retain-Only', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:retain"],"banks":["*"]}]}', TRUE),
    ('bank:admin', 'Bank Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["bank:*"],"banks":["*"]}]}', TRUE),
    ('iam:admin', 'IAM Admin', '{"version":"2026-03-24","statements":[{"effect":"allow","actions":["iam:*"],"banks":["*"]}]}', TRUE)
ON CONFLICT (id) DO NOTHING;
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
        SELECT g.id, g.display_name, g.recall, g.retain,
               g.retain_roles, g.retain_tags, g.retain_every_n_turns,
               g.recall_budget, g.recall_max_tokens, g.recall_tag_groups,
               g.llm_model, g.llm_provider, g.exclude_providers, g.retain_strategy
        FROM hindclaw_groups g
        JOIN hindclaw_group_members m ON m.group_id = g.id
        WHERE m.user_id = $1
        ORDER BY g.id
        """,
        user_id,
    )
    return [
        GroupRecord(
            id=r["id"],
            display_name=r["display_name"],
            recall=r["recall"],
            retain=r["retain"],
            retain_roles=_parse_json(r["retain_roles"]),
            retain_tags=_parse_json(r["retain_tags"]),
            retain_every_n_turns=r["retain_every_n_turns"],
            recall_budget=r["recall_budget"],
            recall_max_tokens=r["recall_max_tokens"],
            recall_tag_groups=_parse_json(r["recall_tag_groups"]),
            llm_model=r["llm_model"],
            llm_provider=r["llm_provider"],
            exclude_providers=_parse_json(r["exclude_providers"]),
            retain_strategy=r["retain_strategy"],
        )
        for r in rows
    ]


async def get_default_group() -> GroupRecord | None:
    """Get the _default group used for anonymous/ungrouped users.

    Returns:
        GroupRecord for the _default group, or None if it doesn't exist.
    """
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, display_name, recall, retain,
               retain_roles, retain_tags, retain_every_n_turns,
               recall_budget, recall_max_tokens, recall_tag_groups,
               llm_model, llm_provider, exclude_providers, retain_strategy
        FROM hindclaw_groups WHERE id = '_default'
        """
    )
    if row is None:
        return None
    return GroupRecord(
        id=row["id"],
        display_name=row["display_name"],
        recall=row["recall"],
        retain=row["retain"],
        retain_roles=_parse_json(row["retain_roles"]),
        retain_tags=_parse_json(row["retain_tags"]),
        retain_every_n_turns=row["retain_every_n_turns"],
        recall_budget=row["recall_budget"],
        recall_max_tokens=row["recall_max_tokens"],
        recall_tag_groups=_parse_json(row["recall_tag_groups"]),
        llm_model=row["llm_model"],
        llm_provider=row["llm_provider"],
        exclude_providers=_parse_json(row["exclude_providers"]),
        retain_strategy=row["retain_strategy"],
    )


async def get_bank_permissions(
    bank_id: str, group_ids: list[str], user_id: str
) -> list[BankPermissionRecord]:
    """Get all bank-level permission entries for a user's groups and the user itself.

    Automatically includes the _default group in the query.

    Args:
        bank_id: Hindsight bank identifier.
        group_ids: List of group IDs the user belongs to.
        user_id: Canonical user identifier.

    Returns:
        List of BankPermissionRecord ordered by scope_type, scope_id.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT bank_id, scope_type, scope_id,
               recall, retain, retain_roles, retain_tags,
               retain_every_n_turns, recall_budget, recall_max_tokens,
               recall_tag_groups, llm_model, llm_provider,
               exclude_providers, retain_strategy
        FROM hindclaw_bank_permissions
        WHERE bank_id = $1
          AND (
            (scope_type = 'group' AND scope_id = ANY($2))
            OR (scope_type = 'user' AND scope_id = $3)
          )
        ORDER BY scope_type, scope_id
        """,
        bank_id,
        group_ids + ["_default"],
        user_id,
    )
    return [
        BankPermissionRecord(
            bank_id=r["bank_id"],
            scope_type=r["scope_type"],
            scope_id=r["scope_id"],
            recall=r["recall"],
            retain=r["retain"],
            retain_roles=_parse_json(r["retain_roles"]),
            retain_tags=_parse_json(r["retain_tags"]),
            retain_every_n_turns=r["retain_every_n_turns"],
            recall_budget=r["recall_budget"],
            recall_max_tokens=r["recall_max_tokens"],
            recall_tag_groups=_parse_json(r["recall_tag_groups"]),
            llm_model=r["llm_model"],
            llm_provider=r["llm_provider"],
            exclude_providers=_parse_json(r["exclude_providers"]),
            retain_strategy=r["retain_strategy"],
        )
        for r in rows
    ]


async def resolve_strategy(
    bank_id: str,
    agent: str | None = None,
    channel: str | None = None,
    topic: str | None = None,
    group_ids: list[str] | None = None,
    user_id: str | None = None,
) -> str | None:
    """Resolve the retain strategy via the 5-level scope cascade.

    Most specific scope wins. Tiebreaker within same scope_type:
    alphabetically first scope_value. See spec Section 7.

    Cascade priority: user(5) > group(4) > topic(3) > channel(2) > agent(1).

    Args:
        bank_id: Hindsight bank identifier.
        agent: Agent name from JWT claims.
        channel: Channel name from JWT claims.
        topic: Topic ID from JWT claims.
        group_ids: User's group IDs (for group-level strategy scopes).
        user_id: Canonical user identifier (for user-level strategy scopes).

    Returns:
        Named strategy string, or None if no strategy scope matches.
    """
    pool = await get_pool()

    # Build WHERE conditions dynamically
    conditions = []
    params: list = [bank_id]
    idx = 2

    if agent:
        conditions.append(f"(scope_type = 'agent' AND scope_value = ${idx})")
        params.append(agent)
        idx += 1
    if channel:
        conditions.append(f"(scope_type = 'channel' AND scope_value = ${idx})")
        params.append(channel)
        idx += 1
    if topic:
        conditions.append(f"(scope_type = 'topic' AND scope_value = ${idx})")
        params.append(topic)
        idx += 1
    if group_ids:
        conditions.append(f"(scope_type = 'group' AND scope_value = ANY(${idx}))")
        params.append(group_ids)
        idx += 1
    if user_id:
        conditions.append(f"(scope_type = 'user' AND scope_value = ${idx})")
        params.append(user_id)
        idx += 1

    if not conditions:
        return None

    where = " OR ".join(conditions)
    return await pool.fetchval(
        f"""
        SELECT strategy FROM hindclaw_strategy_scopes
        WHERE bank_id = $1 AND ({where})
        ORDER BY
            CASE scope_type
                WHEN 'user'    THEN 5
                WHEN 'group'   THEN 4
                WHEN 'topic'   THEN 3
                WHEN 'channel' THEN 2
                WHEN 'agent'   THEN 1
            END DESC,
            scope_value ASC
        LIMIT 1
        """,
        *params,
    )


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

"""HindclawHttp — Hindsight HttpExtension for managing access control.

REST API at /ext/hindclaw/ for users, groups, permissions, strategies, API keys.
Parses JWT independently — /ext/ routes do NOT pass through TenantExtension.

See spec Section 8.
"""

import logging
import os
import secrets

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hindsight_api.extensions import AuthenticationError, HttpExtension

from hindclaw_ext import db
from hindclaw_ext.auth import decode_jwt
from hindclaw_ext.policy_engine import AccessResult, apply_sa_scoping, evaluate_access, intersect_sa_policy
from hindclaw_ext.http_models import (
    AddChannelRequest,
    AddMemberRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    BankPolicyResponse,
    ChannelResponse,
    CreateApiKeyRequest,
    CreateGroupRequest,
    CreatePolicyAttachmentRequest,
    CreatePolicyRequest,
    CreateSAKeyRequest,
    CreateServiceAccountRequest,
    CreateUserRequest,
    GroupMemberResponse,
    GroupMembershipConfirmation,
    GroupResponse,
    GroupSummaryResponse,
    PolicyAttachmentResponse,
    PolicyResponse,
    SAKeyCreateResponse,
    SAKeyResponse,
    ServiceAccountResponse,
    UpdateGroupRequest,
    UpdatePolicyRequest,
    UpdateServiceAccountRequest,
    UpdateUserRequest,
    UpsertBankPolicyRequest,
    UserResponse,
)
from hindclaw_ext.policy_models import BankPolicyDocument, PolicyDocument

logger = logging.getLogger(__name__)

# Number of characters to show when masking API keys in list responses.
_API_KEY_MASK_LENGTH = 12


_bearer = HTTPBearer()


async def _evaluate_iam_access(user_id: str, action: str) -> AccessResult:
    """Evaluate IAM access for a user.

    Args:
        user_id: User identifier.
        action: IAM action (e.g., "iam:users:read").

    Returns:
        AccessResult with allowed flag.
    """
    groups = await db.get_user_groups(user_id)
    group_ids = [g.id for g in groups]
    policies = await db.get_policies_for_user(user_id, group_ids)
    return evaluate_access(policies, action=action, bank_id="*")


async def require_admin_for_action(
    action: str,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Authenticate and authorize for a specific IAM action.

    Accepts both JWT and API keys. Resolves the principal, then checks
    their effective policy for the required iam:* action.

    Args:
        action: Required IAM action (e.g., "iam:users:read").
        credentials: Bearer token from Authorization header.

    Returns:
        Dict with principal info (user_id, principal_type).

    Raises:
        AuthenticationError: If token is invalid or principal lacks required action.
    """
    token = credentials.credentials

    if token.startswith("eyJ"):
        # JWT path
        try:
            claims = decode_jwt(token)
        except Exception as e:
            raise AuthenticationError(str(e))

        sender = claims.get("sender")
        if sender and ":" in sender:
            provider, sender_id = sender.split(":", 1)
            channel_user = await db.get_user_by_channel(provider, sender_id)
            user = await db.get_user(channel_user.id) if channel_user else None
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            user_id = user.id
        else:
            raise AuthenticationError("JWT must have sender for admin access")

    elif token.startswith("hc_sa_"):
        # SA key path
        sa = await db.get_service_account_by_api_key(token)
        if not sa or not sa.is_active:
            raise AuthenticationError("Invalid or inactive service account key")
        parent = await db.get_user(sa.owner_user_id)
        if not parent or not parent.is_active:
            raise AuthenticationError("Service account owner is inactive")
        user_id = sa.owner_user_id
        parent_access = await _evaluate_iam_access(user_id, action)
        if sa.scoping_policy_id:
            final = await apply_sa_scoping(parent_access, sa.scoping_policy_id, sa.id, action, "*")
            if not final.allowed:
                raise AuthenticationError(f"{action} denied for sa:{sa.id}")
            return {"principal_type": "service_account", "principal_id": f"sa:{sa.id}", "action": action, "user_id": user_id, "sa_id": sa.id}
        if not parent_access.allowed:
            raise AuthenticationError(f"{action} denied for {user_id}")
        return {"principal_type": "service_account", "principal_id": f"sa:{sa.id}", "action": action, "user_id": user_id, "sa_id": sa.id}

    else:
        # User key path
        key_record = await db.get_api_key(token)
        if not key_record:
            raise AuthenticationError("Invalid API key")
        user = await db.get_user(key_record.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        user_id = key_record.user_id

    # Evaluate IAM policy
    access = await _evaluate_iam_access(user_id, action)
    if not access.allowed:
        raise AuthenticationError(f"{action} denied for {user_id}")

    return {"principal_type": "user", "principal_id": user_id, "action": action, "user_id": user_id}


def _require_iam(action: str):
    """Create a FastAPI dependency that requires a specific IAM action.

    Args:
        action: IAM action string (e.g., "iam:users:read").

    Returns:
        Async dependency function.
    """
    async def dependency(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
        return await require_admin_for_action(action, credentials)
    return dependency


class HindclawHttp(HttpExtension):
    """REST API for managing hindclaw access control data.

    Provides CRUD endpoints at ``/ext/hindclaw/`` for users, groups,
    permissions, strategy scopes, and API keys. All endpoints require
    admin JWT authentication via the ``require_admin`` dependency.

    See spec Section 8.
    """

    def get_router(self, memory) -> APIRouter:
        """Return FastAPI router with all hindclaw management endpoints.

        Args:
            memory: MemoryEngine instance (not used directly — we use our own
                DB pool from ``db.get_pool()`` for consistency).

        Returns:
            APIRouter mounted at ``/ext/hindclaw/`` by the Hindsight server.
        """
        router = APIRouter(prefix="/hindclaw", dependencies=[Depends(_require_iam("iam:admin"))])

        # --- Users ---

        @router.get("/users", response_model=list[UserResponse], operation_id="list_users")
        async def list_users():
            pool = await db.get_pool()
            rows = await pool.fetch("SELECT id, display_name, email FROM hindclaw_users ORDER BY id")
            return [{"id": r["id"], "display_name": r["display_name"], "email": r["email"]} for r in rows]

        @router.post("/users", status_code=201, response_model=UserResponse, operation_id="create_user")
        async def create_user(req: CreateUserRequest):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_users (id, display_name, email) VALUES ($1, $2, $3)",
                    req.id, req.display_name, req.email,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"User {req.id} already exists")
            return {"id": req.id, "display_name": req.display_name, "email": req.email}

        @router.get("/users/{user_id}", response_model=UserResponse, operation_id="get_user")
        async def get_user(user_id: str):
            pool = await db.get_pool()
            row = await pool.fetchrow("SELECT id, display_name, email FROM hindclaw_users WHERE id = $1", user_id)
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return {"id": row["id"], "display_name": row["display_name"], "email": row["email"]}

        @router.put("/users/{user_id}", response_model=UserResponse, operation_id="update_user")
        async def update_user(user_id: str, req: UpdateUserRequest):
            pool = await db.get_pool()
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(400, "No fields to update")
            # Column names come from Pydantic model field names (not user input) — safe
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
            set_clause += ", updated_at = NOW()"
            row = await pool.fetchrow(
                f"UPDATE hindclaw_users SET {set_clause} WHERE id = $1 RETURNING id, display_name, email",
                user_id, *updates.values(),
            )
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return row

        @router.delete("/users/{user_id}", status_code=204, operation_id="delete_user")
        async def delete_user(user_id: str):
            pool = await db.get_pool()
            existing = await pool.fetchval("SELECT id FROM hindclaw_users WHERE id = $1", user_id)
            if not existing:
                raise HTTPException(404, f"User {user_id} not found")
            # Application-level cascade in transaction (FK handles channels, api_keys, group_members)
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "DELETE FROM hindclaw_bank_permissions WHERE scope_type = 'user' AND scope_id = $1", user_id
                    )
                    await conn.execute(
                        "DELETE FROM hindclaw_strategy_scopes WHERE scope_type = 'user' AND scope_value = $1", user_id
                    )
                    await conn.execute("DELETE FROM hindclaw_users WHERE id = $1", user_id)

        # --- User Channels ---

        @router.get("/users/{user_id}/channels", response_model=list[ChannelResponse], operation_id="list_user_channels")
        async def list_user_channels(user_id: str):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT provider, sender_id FROM hindclaw_user_channels WHERE user_id = $1", user_id
            )
            return [{"provider": r["provider"], "sender_id": r["sender_id"]} for r in rows]

        @router.post("/users/{user_id}/channels", status_code=201, response_model=ChannelResponse, operation_id="add_user_channel")
        async def add_user_channel(user_id: str, req: AddChannelRequest):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_user_channels (user_id, provider, sender_id) VALUES ($1, $2, $3)",
                    user_id, req.provider, req.sender_id,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Channel {req.provider}:{req.sender_id} already mapped")
            return {"provider": req.provider, "sender_id": req.sender_id}

        @router.delete("/users/{user_id}/channels/{provider}/{sender_id}", status_code=204, operation_id="remove_user_channel")
        async def remove_user_channel(user_id: str, provider: str, sender_id: str):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_user_channels WHERE user_id = $1 AND provider = $2 AND sender_id = $3",
                user_id, provider, sender_id,
            )

        # --- Groups ---

        @router.get("/groups", response_model=list[GroupSummaryResponse], operation_id="list_groups")
        async def list_groups():
            pool = await db.get_pool()
            rows = await pool.fetch("SELECT id, display_name FROM hindclaw_groups ORDER BY id")
            return [{"id": r["id"], "display_name": r["display_name"]} for r in rows]

        @router.post("/groups", status_code=201, response_model=GroupSummaryResponse, operation_id="create_group")
        async def create_group(req: CreateGroupRequest):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_groups (id, display_name) VALUES ($1, $2)",
                    req.id, req.display_name,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Group {req.id} already exists")
            return {"id": req.id, "display_name": req.display_name}

        @router.get("/groups/{group_id}", response_model=GroupSummaryResponse, operation_id="get_group")
        async def get_group(group_id: str):
            pool = await db.get_pool()
            row = await pool.fetchrow(
                "SELECT id, display_name FROM hindclaw_groups WHERE id = $1", group_id,
            )
            if not row:
                raise HTTPException(404, f"Group {group_id} not found")
            return {"id": row["id"], "display_name": row["display_name"]}

        @router.put("/groups/{group_id}", response_model=GroupSummaryResponse, operation_id="update_group")
        async def update_group(group_id: str, req: UpdateGroupRequest):
            pool = await db.get_pool()
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(400, "No fields to update")
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
            set_clause += ", updated_at = NOW()"
            row = await pool.fetchrow(
                f"UPDATE hindclaw_groups SET {set_clause} WHERE id = $1 RETURNING id, display_name",
                group_id, *updates.values(),
            )
            if not row:
                raise HTTPException(404, f"Group {group_id} not found")
            return {"id": row["id"], "display_name": row["display_name"]}

        @router.delete("/groups/{group_id}", status_code=204, operation_id="delete_group")
        async def delete_group(group_id: str):
            pool = await db.get_pool()
            existing = await pool.fetchval("SELECT id FROM hindclaw_groups WHERE id = $1", group_id)
            if not existing:
                raise HTTPException(404, f"Group {group_id} not found")
            # FK CASCADE handles group_members, policy_attachments
            await pool.execute("DELETE FROM hindclaw_groups WHERE id = $1", group_id)

        # --- Group Members ---

        @router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse], operation_id="list_group_members")
        async def list_group_members(group_id: str):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT user_id FROM hindclaw_group_members WHERE group_id = $1 ORDER BY user_id", group_id
            )
            return [{"user_id": r["user_id"]} for r in rows]

        @router.post("/groups/{group_id}/members", status_code=201, response_model=GroupMembershipConfirmation, operation_id="add_group_member")
        async def add_group_member(group_id: str, req: AddMemberRequest):
            pool = await db.get_pool()
            await pool.execute(
                "INSERT INTO hindclaw_group_members (group_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                group_id, req.user_id,
            )
            return {"group_id": group_id, "user_id": req.user_id}

        @router.delete("/groups/{group_id}/members/{user_id}", status_code=204, operation_id="remove_group_member")
        async def remove_group_member(group_id: str, user_id: str):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_group_members WHERE group_id = $1 AND user_id = $2",
                group_id, user_id,
            )

        # --- API Keys ---

        @router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyResponse], operation_id="list_api_keys")
        async def list_api_keys(user_id: str):
            """List API keys for a user. Keys are masked after creation."""
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT id, api_key, description FROM hindclaw_api_keys WHERE user_id = $1 ORDER BY id",
                user_id,
            )
            return [
                {"id": r["id"], "api_key_prefix": r["api_key"][:_API_KEY_MASK_LENGTH] + "...", "description": r["description"]}
                for r in rows
            ]

        @router.post("/users/{user_id}/api-keys", status_code=201, response_model=ApiKeyCreateResponse, operation_id="create_api_key")
        async def create_api_key(user_id: str, req: CreateApiKeyRequest):
            pool = await db.get_pool()
            key_id = secrets.token_hex(8)
            api_key = f"hc_u_{user_id}_{secrets.token_hex(16)}"
            await pool.execute(
                "INSERT INTO hindclaw_api_keys (id, api_key, user_id, description) VALUES ($1, $2, $3, $4)",
                key_id, api_key, user_id, req.description,
            )
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/users/{user_id}/api-keys/{key_id}", status_code=204, operation_id="delete_api_key")
        async def delete_api_key(user_id: str, key_id: str):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_api_keys WHERE id = $1 AND user_id = $2",
                key_id, user_id,
            )

        # --- Policies ---

        @router.get("/policies", response_model=list[PolicyResponse], operation_id="list_policies")
        async def list_policies():
            results = await db.list_policies()
            return [{"id": r.id, "display_name": r.display_name, "document": r.document_json, "is_builtin": r.is_builtin} for r in results]

        @router.post("/policies", status_code=201, response_model=PolicyResponse, operation_id="create_policy")
        async def create_policy(req: CreatePolicyRequest):
            PolicyDocument(**req.document)
            await db.create_policy(req.id, req.display_name, req.document)
            return {"id": req.id, "display_name": req.display_name, "document": req.document, "is_builtin": False}

        @router.get("/policies/{policy_id}", response_model=PolicyResponse, operation_id="get_policy")
        async def get_policy_endpoint(policy_id: str):
            result = await db.get_policy(policy_id)
            if not result:
                raise HTTPException(404, f"Policy {policy_id} not found")
            return {"id": result.id, "display_name": result.display_name, "document": result.document_json, "is_builtin": result.is_builtin}

        @router.put("/policies/{policy_id}", response_model=PolicyResponse, operation_id="update_policy")
        async def update_policy_endpoint(policy_id: str, req: UpdatePolicyRequest):
            if req.document:
                PolicyDocument(**req.document)
            updated = await db.update_policy(policy_id, req.display_name, req.document)
            if not updated:
                raise HTTPException(404, f"Policy {policy_id} not found or is built-in")
            result = await db.get_policy(policy_id)
            return {"id": result.id, "display_name": result.display_name, "document": result.document_json, "is_builtin": result.is_builtin}

        @router.delete("/policies/{policy_id}", status_code=204, operation_id="delete_policy")
        async def delete_policy_endpoint(policy_id: str):
            existing = await db.get_policy(policy_id)
            if not existing:
                raise HTTPException(404, f"Policy {policy_id} not found")
            await db.delete_policy(policy_id)

        # --- Policy Attachments ---

        @router.get("/policy-attachments", response_model=list[PolicyAttachmentResponse], operation_id="list_policy_attachments")
        async def list_attachments(policy_id: str = Query(...)):
            return await db.list_policy_attachments(policy_id)

        @router.put("/policy-attachments", response_model=PolicyAttachmentResponse, operation_id="upsert_policy_attachment")
        async def upsert_attachment(req: CreatePolicyAttachmentRequest):
            await db.create_policy_attachment(req.policy_id, req.principal_type, req.principal_id, req.priority)
            return req.model_dump()

        @router.delete("/policy-attachments/{policy_id}/{principal_type}/{principal_id}", status_code=204, operation_id="delete_policy_attachment")
        async def delete_attachment(policy_id: str, principal_type: str, principal_id: str):
            existing = await db.get_policy_attachment(policy_id, principal_type, principal_id)
            if not existing:
                raise HTTPException(404, f"Attachment {policy_id}/{principal_type}/{principal_id} not found")
            await db.delete_policy_attachment(policy_id, principal_type, principal_id)

        # --- Service Accounts ---

        @router.get("/service-accounts", response_model=list[ServiceAccountResponse], operation_id="list_service_accounts")
        async def list_service_accounts():
            return await db.list_service_accounts()

        @router.post("/service-accounts", status_code=201, response_model=ServiceAccountResponse, operation_id="create_service_account")
        async def create_service_account(req: CreateServiceAccountRequest):
            await db.create_service_account(req.id, req.owner_user_id, req.display_name, req.scoping_policy_id)
            return {"id": req.id, "owner_user_id": req.owner_user_id, "display_name": req.display_name, "is_active": True, "scoping_policy_id": req.scoping_policy_id}

        @router.get("/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="get_service_account")
        async def get_service_account_endpoint(sa_id: str):
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.put("/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="update_service_account")
        async def update_service_account_endpoint(sa_id: str, req: UpdateServiceAccountRequest):
            updates = req.model_dump(exclude_unset=True)
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            await db.update_service_account(sa_id, display_name=updates.get("display_name"), scoping_policy_id=updates.get("scoping_policy_id"), is_active=updates.get("is_active"))
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.delete("/service-accounts/{sa_id}", status_code=204, operation_id="delete_service_account")
        async def delete_service_account_endpoint(sa_id: str):
            existing = await db.get_service_account(sa_id)
            if not existing:
                raise HTTPException(404, f"Service account {sa_id} not found")
            await db.delete_service_account(sa_id)

        # --- SA Keys ---

        @router.get("/service-accounts/{sa_id}/keys", response_model=list[SAKeyResponse], operation_id="list_sa_keys")
        async def list_sa_keys(sa_id: str):
            keys = await db.list_sa_keys(sa_id)
            return [{"id": k.id, "api_key_prefix": k.api_key[:_API_KEY_MASK_LENGTH], "description": k.description} for k in keys]

        @router.post("/service-accounts/{sa_id}/keys", status_code=201, response_model=SAKeyCreateResponse, operation_id="create_sa_key")
        async def create_sa_key(sa_id: str, req: CreateSAKeyRequest):
            key_id = secrets.token_hex(8)
            api_key = f"hc_sa_{sa_id}_{secrets.token_hex(16)}"
            await db.create_sa_key(key_id, sa_id, api_key, req.description)
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/service-accounts/{sa_id}/keys/{key_id}", status_code=204, operation_id="delete_sa_key")
        async def delete_sa_key(sa_id: str, key_id: str):
            existing = await db.get_sa_key(key_id, sa_id)
            if not existing:
                raise HTTPException(404, f"SA key {key_id} not found")
            await db.delete_sa_key(key_id, sa_id)

        # --- Bank Policies ---

        @router.get("/banks/{bank_id}/policy", response_model=BankPolicyResponse, operation_id="get_bank_policy")
        async def get_bank_policy_endpoint(bank_id: str):
            result = await db.get_bank_policy(bank_id)
            if not result:
                raise HTTPException(404, f"Bank policy for {bank_id} not found")
            return {"bank_id": result.bank_id, "document": result.document_json}

        @router.put("/banks/{bank_id}/policy", response_model=BankPolicyResponse, operation_id="upsert_bank_policy")
        async def upsert_bank_policy_endpoint(bank_id: str, req: UpsertBankPolicyRequest):
            BankPolicyDocument(**req.document)
            await db.upsert_bank_policy(bank_id, req.document)
            return {"bank_id": bank_id, "document": req.document}

        @router.delete("/banks/{bank_id}/policy", status_code=204, operation_id="delete_bank_policy")
        async def delete_bank_policy_endpoint(bank_id: str):
            existing = await db.get_bank_policy(bank_id)
            if not existing:
                raise HTTPException(404, f"Bank policy for {bank_id} not found")
            await db.delete_bank_policy(bank_id)

        # --- Debug ---

        @router.get("/debug/resolve", operation_id="debug_resolve")
        async def debug_resolve(
            bank: str = Query(...),
            sender: str | None = Query(None),
            agent: str | None = Query(None),
            channel: str | None = Query(None),
            topic: str | None = Query(None),
        ):
            """Resolve and return full permissions for a given context."""
            user_id = "_unmapped"
            if sender:
                if ":" not in sender:
                    raise HTTPException(400, f"Invalid sender format: {sender!r} (expected 'provider:id')")
                provider, sender_id = sender.split(":", 1)
                channel_user = await db.get_user_by_channel(provider, sender_id)
                user = await db.get_user(channel_user.id) if channel_user else None
                user_id = user.id if (user and user.is_active) else "_unmapped"

            from hindclaw_ext.validator import _resolve_user_access, _resolve_public_access
            if user_id == "_unmapped":
                access = await _resolve_public_access(bank, "bank:recall")
            else:
                access = await _resolve_user_access(user_id, "bank:recall", bank)
            return access.model_dump()

        return router

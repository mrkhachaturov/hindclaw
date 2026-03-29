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

from hindclaw_ext import db, marketplace
from hindclaw_ext.models import ServiceAccountRecord
from hindclaw_ext.auth import decode_jwt
from hindclaw_ext.bank_bootstrap import bootstrap_bank_from_template
from hindclaw_ext.marketplace import derive_source_name
from hindclaw_ext.version import is_version_compatible
from hindclaw_ext.policy_engine import AccessResult, apply_sa_scoping, evaluate_access, intersect_sa_policy
from hindclaw_ext.template_ref import parse_template_ref
from hindclaw_ext.http_models import (
    AddChannelRequest,
    AddMemberRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    BankCreationResponse,
    BankPolicyResponse,
    ChannelResponse,
    CreateApiKeyRequest,
    CreateBankFromTemplateRequest,
    CreateGroupRequest,
    CreatePolicyAttachmentRequest,
    CreatePolicyRequest,
    CreateSAKeyRequest,
    CreateSelfServiceAccountRequest,
    CreateServiceAccountRequest,
    CreateSourceRequest,
    CreateTemplateRequest,
    CreateUserRequest,
    DirectiveSeedResult,
    GroupMemberResponse,
    GroupMembershipConfirmation,
    GroupSummaryResponse,
    InstallTemplateRequest,
    MarketplaceSearchResponse,
    MentalModelSeedResult,
    PolicyAttachmentResponse,
    PolicyResponse,
    SAKeyCreateResponse,
    SAKeyResponse,
    ServiceAccountResponse,
    SourceResponse,
    TemplateSummaryResponse,
    TemplateResponse,
    TemplateUpdateResponse,
    UpdateGroupRequest,
    UpdateSelfServiceAccountRequest,
    UpdateTemplateRequest,
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
            memory: MemoryEngine instance passed to bootstrap_bank_from_template
                for in-process bank creation.

        Returns:
            APIRouter mounted at ``/ext/hindclaw/`` by the Hindsight server.
        """
        _memory = memory
        router = APIRouter(prefix="/hindclaw")

        # --- Users ---

        @router.get("/users", response_model=list[UserResponse], operation_id="list_users")
        async def list_users(_auth=Depends(_require_iam("iam:users:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch("SELECT id, display_name, email, is_active FROM hindclaw_users ORDER BY id")
            return [{"id": r["id"], "display_name": r["display_name"], "email": r["email"], "is_active": r["is_active"]} for r in rows]

        @router.post("/users", status_code=201, response_model=UserResponse, operation_id="create_user")
        async def create_user(req: CreateUserRequest, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_users (id, display_name, email, is_active) VALUES ($1, $2, $3, $4)",
                    req.id, req.display_name, req.email, req.is_active,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"User {req.id} already exists")
            return {"id": req.id, "display_name": req.display_name, "email": req.email, "is_active": req.is_active}

        @router.get("/users/{user_id}", response_model=UserResponse, operation_id="get_user")
        async def get_user(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
            pool = await db.get_pool()
            row = await pool.fetchrow("SELECT id, display_name, email, is_active FROM hindclaw_users WHERE id = $1", user_id)
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return {"id": row["id"], "display_name": row["display_name"], "email": row["email"], "is_active": row["is_active"]}

        @router.put("/users/{user_id}", response_model=UserResponse, operation_id="update_user")
        async def update_user(user_id: str, req: UpdateUserRequest, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(400, "No fields to update")
            # Column names come from Pydantic model field names (not user input) — safe
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
            set_clause += ", updated_at = NOW()"
            row = await pool.fetchrow(
                f"UPDATE hindclaw_users SET {set_clause} WHERE id = $1 RETURNING id, display_name, email, is_active",
                user_id, *updates.values(),
            )
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return {"id": row["id"], "display_name": row["display_name"], "email": row["email"], "is_active": row["is_active"]}

        @router.delete("/users/{user_id}", status_code=204, operation_id="delete_user")
        async def delete_user(user_id: str, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            existing = await pool.fetchval("SELECT id FROM hindclaw_users WHERE id = $1", user_id)
            if not existing:
                raise HTTPException(404, f"User {user_id} not found")
            # FK CASCADE handles channels, api_keys, group_members, policy_attachments, service_accounts
            await pool.execute("DELETE FROM hindclaw_users WHERE id = $1", user_id)

        # --- User Channels ---

        @router.get("/users/{user_id}/channels", response_model=list[ChannelResponse], operation_id="list_user_channels")
        async def list_user_channels(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT provider, sender_id FROM hindclaw_user_channels WHERE user_id = $1", user_id
            )
            return [{"provider": r["provider"], "sender_id": r["sender_id"]} for r in rows]

        @router.post("/users/{user_id}/channels", status_code=201, response_model=ChannelResponse, operation_id="add_user_channel")
        async def add_user_channel(user_id: str, req: AddChannelRequest, _auth=Depends(_require_iam("iam:users:write"))):
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
        async def remove_user_channel(user_id: str, provider: str, sender_id: str, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_user_channels WHERE user_id = $1 AND provider = $2 AND sender_id = $3",
                user_id, provider, sender_id,
            )

        # --- Groups ---

        @router.get("/groups", response_model=list[GroupSummaryResponse], operation_id="list_groups")
        async def list_groups(_auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch("SELECT id, display_name FROM hindclaw_groups ORDER BY id")
            return [{"id": r["id"], "display_name": r["display_name"]} for r in rows]

        @router.post("/groups", status_code=201, response_model=GroupSummaryResponse, operation_id="create_group")
        async def create_group(req: CreateGroupRequest, _auth=Depends(_require_iam("iam:groups:write"))):
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
        async def get_group(group_id: str, _auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            row = await pool.fetchrow(
                "SELECT id, display_name FROM hindclaw_groups WHERE id = $1", group_id,
            )
            if not row:
                raise HTTPException(404, f"Group {group_id} not found")
            return {"id": row["id"], "display_name": row["display_name"]}

        @router.put("/groups/{group_id}", response_model=GroupSummaryResponse, operation_id="update_group")
        async def update_group(group_id: str, req: UpdateGroupRequest, _auth=Depends(_require_iam("iam:groups:write"))):
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
        async def delete_group(group_id: str, _auth=Depends(_require_iam("iam:groups:write"))):
            pool = await db.get_pool()
            existing = await pool.fetchval("SELECT id FROM hindclaw_groups WHERE id = $1", group_id)
            if not existing:
                raise HTTPException(404, f"Group {group_id} not found")
            # FK CASCADE handles group_members, policy_attachments
            await pool.execute("DELETE FROM hindclaw_groups WHERE id = $1", group_id)

        # --- Group Members ---

        @router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse], operation_id="list_group_members")
        async def list_group_members(group_id: str, _auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT user_id FROM hindclaw_group_members WHERE group_id = $1 ORDER BY user_id", group_id
            )
            return [{"user_id": r["user_id"]} for r in rows]

        @router.post("/groups/{group_id}/members", status_code=201, response_model=GroupMembershipConfirmation, operation_id="add_group_member")
        async def add_group_member(group_id: str, req: AddMemberRequest, _auth=Depends(_require_iam("iam:groups:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "INSERT INTO hindclaw_group_members (group_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                group_id, req.user_id,
            )
            return {"group_id": group_id, "user_id": req.user_id}

        @router.delete("/groups/{group_id}/members/{user_id}", status_code=204, operation_id="remove_group_member")
        async def remove_group_member(group_id: str, user_id: str, _auth=Depends(_require_iam("iam:groups:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_group_members WHERE group_id = $1 AND user_id = $2",
                group_id, user_id,
            )

        # --- API Keys ---

        @router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyResponse], operation_id="list_api_keys")
        async def list_api_keys(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
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
        async def create_api_key(user_id: str, req: CreateApiKeyRequest, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            key_id = secrets.token_hex(8)
            api_key = f"hc_u_{user_id}_{secrets.token_hex(16)}"
            await pool.execute(
                "INSERT INTO hindclaw_api_keys (id, api_key, user_id, description) VALUES ($1, $2, $3, $4)",
                key_id, api_key, user_id, req.description,
            )
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/users/{user_id}/api-keys/{key_id}", status_code=204, operation_id="delete_api_key")
        async def delete_api_key(user_id: str, key_id: str, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_api_keys WHERE id = $1 AND user_id = $2",
                key_id, user_id,
            )

        # --- Policies ---

        @router.get("/policies", response_model=list[PolicyResponse], operation_id="list_policies")
        async def list_policies(_auth=Depends(_require_iam("iam:policies:read"))):
            results = await db.list_policies()
            return [{"id": r.id, "display_name": r.display_name, "document": r.document_json, "is_builtin": r.is_builtin} for r in results]

        @router.post("/policies", status_code=201, response_model=PolicyResponse, operation_id="create_policy")
        async def create_policy(req: CreatePolicyRequest, _auth=Depends(_require_iam("iam:policies:write"))):
            PolicyDocument(**req.document)
            await db.create_policy(req.id, req.display_name, req.document)
            return {"id": req.id, "display_name": req.display_name, "document": req.document, "is_builtin": False}

        @router.get("/policies/{policy_id}", response_model=PolicyResponse, operation_id="get_policy")
        async def get_policy_endpoint(policy_id: str, _auth=Depends(_require_iam("iam:policies:read"))):
            result = await db.get_policy(policy_id)
            if not result:
                raise HTTPException(404, f"Policy {policy_id} not found")
            return {"id": result.id, "display_name": result.display_name, "document": result.document_json, "is_builtin": result.is_builtin}

        @router.put("/policies/{policy_id}", response_model=PolicyResponse, operation_id="update_policy")
        async def update_policy_endpoint(policy_id: str, req: UpdatePolicyRequest, _auth=Depends(_require_iam("iam:policies:write"))):
            if req.document:
                PolicyDocument(**req.document)
            updated = await db.update_policy(policy_id, req.display_name, req.document)
            if not updated:
                raise HTTPException(404, f"Policy {policy_id} not found or is built-in")
            result = await db.get_policy(policy_id)
            return {"id": result.id, "display_name": result.display_name, "document": result.document_json, "is_builtin": result.is_builtin}

        @router.delete("/policies/{policy_id}", status_code=204, operation_id="delete_policy")
        async def delete_policy_endpoint(policy_id: str, _auth=Depends(_require_iam("iam:policies:write"))):
            existing = await db.get_policy(policy_id)
            if not existing:
                raise HTTPException(404, f"Policy {policy_id} not found")
            await db.delete_policy(policy_id)

        # --- Policy Attachments ---

        @router.get("/policy-attachments", response_model=list[PolicyAttachmentResponse], operation_id="list_policy_attachments")
        async def list_attachments(policy_id: str = Query(...), _auth=Depends(_require_iam("iam:policies:read"))):
            return await db.list_policy_attachments(policy_id)

        @router.put("/policy-attachments", response_model=PolicyAttachmentResponse, operation_id="upsert_policy_attachment")
        async def upsert_attachment(req: CreatePolicyAttachmentRequest, _auth=Depends(_require_iam("iam:attachments:write"))):
            await db.create_policy_attachment(req.policy_id, req.principal_type, req.principal_id, req.priority)
            return req.model_dump()

        @router.delete("/policy-attachments/{policy_id}/{principal_type}/{principal_id}", status_code=204, operation_id="delete_policy_attachment")
        async def delete_attachment(policy_id: str, principal_type: str, principal_id: str, _auth=Depends(_require_iam("iam:attachments:write"))):
            existing = await db.get_policy_attachment(policy_id, principal_type, principal_id)
            if not existing:
                raise HTTPException(404, f"Attachment {policy_id}/{principal_type}/{principal_id} not found")
            await db.delete_policy_attachment(policy_id, principal_type, principal_id)

        # --- Self-Service SA Helpers ---

        async def _get_owned_sa(sa_id: str, owner_user_id: str) -> ServiceAccountRecord:
            """Fetch an SA and verify the caller owns it.

            Returns 404 for both 'not found' and 'not yours' — no information leakage.

            Args:
                sa_id: Service account ID.
                owner_user_id: Authenticated caller's user ID.

            Returns:
                ServiceAccountRecord.

            Raises:
                HTTPException: 404 if SA not found or not owned by caller.
            """
            sa = await db.get_service_account(sa_id)
            if not sa or sa.owner_user_id != owner_user_id:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return sa

        # --- Self-Service Service Accounts (/me/service-accounts) ---

        @router.get("/me/service-accounts", response_model=list[ServiceAccountResponse], operation_id="list_my_service_accounts")
        async def list_my_service_accounts(_auth=Depends(_require_iam("iam:service_accounts:read"))):
            return await db.list_service_accounts_by_owner(_auth["user_id"])

        @router.post("/me/service-accounts", status_code=201, response_model=ServiceAccountResponse, operation_id="create_my_service_account")
        async def create_my_service_account(req: CreateSelfServiceAccountRequest, _auth=Depends(_require_iam("iam:service_accounts:write"))):
            owner_user_id = _auth["user_id"]
            await db.create_service_account(req.id, owner_user_id, req.display_name, req.scoping_policy_id)
            return {"id": req.id, "owner_user_id": owner_user_id, "display_name": req.display_name, "is_active": True, "scoping_policy_id": req.scoping_policy_id}

        @router.get("/me/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="get_my_service_account")
        async def get_my_service_account(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:read"))):
            return await _get_owned_sa(sa_id, _auth["user_id"])

        @router.put("/me/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="update_my_service_account")
        async def update_my_service_account(sa_id: str, req: UpdateSelfServiceAccountRequest, _auth=Depends(_require_iam("iam:service_accounts:write"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            await db.update_service_account(sa_id, display_name=req.display_name)
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.delete("/me/service-accounts/{sa_id}", status_code=204, operation_id="delete_my_service_account")
        async def delete_my_service_account(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:write"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            await db.delete_service_account(sa_id)

        @router.get("/me/service-accounts/{sa_id}/keys", response_model=list[SAKeyResponse], operation_id="list_my_sa_keys")
        async def list_my_sa_keys(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:read"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            keys = await db.list_sa_keys(sa_id)
            return [{"id": k.id, "api_key_prefix": k.api_key[:_API_KEY_MASK_LENGTH], "description": k.description} for k in keys]

        @router.post("/me/service-accounts/{sa_id}/keys", status_code=201, response_model=SAKeyCreateResponse, operation_id="create_my_sa_key")
        async def create_my_sa_key(sa_id: str, req: CreateSAKeyRequest, _auth=Depends(_require_iam("iam:service_account_keys:write"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            key_id = secrets.token_hex(8)
            api_key = f"hc_sa_{sa_id}_{secrets.token_hex(16)}"
            await db.create_sa_key(key_id, sa_id, api_key, req.description)
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/me/service-accounts/{sa_id}/keys/{key_id}", status_code=204, operation_id="delete_my_sa_key")
        async def delete_my_sa_key(sa_id: str, key_id: str, _auth=Depends(_require_iam("iam:service_account_keys:write"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            existing = await db.get_sa_key(key_id, sa_id)
            if not existing:
                raise HTTPException(404, f"SA key {key_id} not found")
            await db.delete_sa_key(key_id, sa_id)

        # --- Service Accounts ---

        @router.get("/service-accounts", response_model=list[ServiceAccountResponse], operation_id="list_service_accounts")
        async def list_service_accounts(_auth=Depends(_require_iam("iam:service_accounts:manage"))):
            return await db.list_service_accounts()

        @router.post("/service-accounts", status_code=201, response_model=ServiceAccountResponse, operation_id="create_service_account")
        async def create_service_account(req: CreateServiceAccountRequest, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            await db.create_service_account(req.id, req.owner_user_id, req.display_name, req.scoping_policy_id)
            return {"id": req.id, "owner_user_id": req.owner_user_id, "display_name": req.display_name, "is_active": True, "scoping_policy_id": req.scoping_policy_id}

        @router.get("/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="get_service_account")
        async def get_service_account_endpoint(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.put("/service-accounts/{sa_id}", response_model=ServiceAccountResponse, operation_id="update_service_account")
        async def update_service_account_endpoint(sa_id: str, req: UpdateServiceAccountRequest, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            updates = req.model_dump(exclude_unset=True)
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            # Pass only fields that were present in the request body.
            # Absent fields stay as _UNSET (don't touch), explicit null clears to NULL.
            kwargs: dict = {}
            if "display_name" in updates:
                kwargs["display_name"] = updates["display_name"]
            if "scoping_policy_id" in updates:
                kwargs["scoping_policy_id"] = updates["scoping_policy_id"]
            if "is_active" in updates:
                kwargs["is_active"] = updates["is_active"]
            await db.update_service_account(sa_id, **kwargs)
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.delete("/service-accounts/{sa_id}", status_code=204, operation_id="delete_service_account")
        async def delete_service_account_endpoint(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            existing = await db.get_service_account(sa_id)
            if not existing:
                raise HTTPException(404, f"Service account {sa_id} not found")
            await db.delete_service_account(sa_id)

        # --- SA Keys ---

        @router.get("/service-accounts/{sa_id}/keys", response_model=list[SAKeyResponse], operation_id="list_sa_keys")
        async def list_sa_keys(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            keys = await db.list_sa_keys(sa_id)
            return [{"id": k.id, "api_key_prefix": k.api_key[:_API_KEY_MASK_LENGTH], "description": k.description} for k in keys]

        @router.post("/service-accounts/{sa_id}/keys", status_code=201, response_model=SAKeyCreateResponse, operation_id="create_sa_key")
        async def create_sa_key(sa_id: str, req: CreateSAKeyRequest, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            key_id = secrets.token_hex(8)
            api_key = f"hc_sa_{sa_id}_{secrets.token_hex(16)}"
            await db.create_sa_key(key_id, sa_id, api_key, req.description)
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/service-accounts/{sa_id}/keys/{key_id}", status_code=204, operation_id="delete_sa_key")
        async def delete_sa_key(sa_id: str, key_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            existing = await db.get_sa_key(key_id, sa_id)
            if not existing:
                raise HTTPException(404, f"SA key {key_id} not found")
            await db.delete_sa_key(key_id, sa_id)

        # --- Bank Policies ---

        @router.get("/banks/{bank_id}/policy", response_model=BankPolicyResponse, operation_id="get_bank_policy")
        async def get_bank_policy_endpoint(bank_id: str, _auth=Depends(_require_iam("iam:banks:read"))):
            result = await db.get_bank_policy(bank_id)
            if not result:
                raise HTTPException(404, f"Bank policy for {bank_id} not found")
            return {"bank_id": result.bank_id, "document": result.document_json}

        @router.put("/banks/{bank_id}/policy", response_model=BankPolicyResponse, operation_id="upsert_bank_policy")
        async def upsert_bank_policy_endpoint(bank_id: str, req: UpsertBankPolicyRequest, _auth=Depends(_require_iam("iam:banks:write"))):
            BankPolicyDocument(**req.document)
            await db.upsert_bank_policy(bank_id, req.document)
            return {"bank_id": bank_id, "document": req.document}

        @router.delete("/banks/{bank_id}/policy", status_code=204, operation_id="delete_bank_policy")
        async def delete_bank_policy_endpoint(bank_id: str, _auth=Depends(_require_iam("iam:banks:write"))):
            existing = await db.get_bank_policy(bank_id)
            if not existing:
                raise HTTPException(404, f"Bank policy for {bank_id} not found")
            await db.delete_bank_policy(bank_id)

        # --- Debug ---

        @router.get("/debug/resolve", operation_id="debug_resolve")
        async def debug_resolve(
            bank: str = Query(...),
            action: str = Query(default="bank:recall"),
            sender: str | None = Query(None),
            user_id: str | None = Query(None),
            sa_id: str | None = Query(None),
            _auth=Depends(_require_iam("iam:users:read")),
        ):
            """Resolve and return effective access policy + bank policy for a context."""
            from hindclaw_ext.validator import _resolve_user_access, _resolve_sa_access, _resolve_public_access

            if sa_id:
                tenant_id = f"sa:{sa_id}"
                principal_type = "service_account"
            elif user_id:
                tenant_id = user_id
                principal_type = "user"
            elif sender:
                if ":" not in sender:
                    raise HTTPException(400, f"Invalid sender format: {sender!r}")
                provider, sender_id_val = sender.split(":", 1)
                channel_user = await db.get_user_by_channel(provider, sender_id_val)
                user = await db.get_user(channel_user.id) if channel_user else None
                if user and user.is_active:
                    tenant_id = user.id
                    principal_type = "user"
                else:
                    tenant_id = "_unmapped"
                    principal_type = "unmapped"
            else:
                raise HTTPException(400, "Provide sender, user_id, or sa_id")

            if tenant_id == "_unmapped":
                access = await _resolve_public_access(bank, action)
            elif tenant_id.startswith("sa:"):
                access = await _resolve_sa_access(tenant_id[3:], action, bank)
            else:
                access = await _resolve_user_access(tenant_id, action, bank)

            bank_policy_record = await db.get_bank_policy(bank)
            bank_policy_dict = bank_policy_record.document_json if bank_policy_record else None

            return {
                "tenant_id": tenant_id,
                "principal_type": principal_type,
                "access": access.model_dump(),
                "bank_policy": bank_policy_dict,
            }

        # --- Templates ---

        @router.get("/templates", response_model=list[TemplateSummaryResponse], operation_id="list_templates")
        async def list_templates(
            scope: str | None = None,
            principal=Depends(_require_iam("template:list")),
        ):
            """List installed templates filtered by access.

            When scope is None, returns all server templates plus the caller's
            personal templates. When scope is specified, returns only that scope.

            Args:
                scope: Optional scope filter ('server' or 'personal').
                principal: Authenticated principal from IAM.

            Returns:
                List of template summaries.
            """
            user_id = principal["user_id"]
            if scope == "server":
                rows = await db.list_templates(scope="server")
            elif scope == "personal":
                rows = await db.list_templates(scope="personal", owner=user_id)
            else:
                server = await db.list_templates(scope="server")
                personal = await db.list_templates(scope="personal", owner=user_id)
                rows = server + personal
            return [r.model_dump() for r in rows]

        @router.post("/templates", response_model=TemplateResponse, status_code=201, operation_id="create_template")
        async def create_template(
            request: CreateTemplateRequest,
            principal=Depends(_require_iam("template:create")),
        ):
            """Create a custom template (no marketplace source).

            Args:
                request: Template creation payload.
                principal: Authenticated principal from IAM.

            Returns:
                The created template.

            Raises:
                HTTPException: 409 if template already exists.
            """
            owner = principal["user_id"] if request.scope == "personal" else None
            try:
                rec = await db.create_template(
                    id=request.id,
                    scope=request.scope,
                    owner=owner,
                    source_name=None,
                    schema_version=1,
                    min_hindclaw_version=request.min_hindclaw_version,
                    min_hindsight_version=request.min_hindsight_version,
                    description=request.description,
                    author=request.author,
                    tags=request.tags,
                    retain_mission=request.retain_mission,
                    reflect_mission=request.reflect_mission,
                    observations_mission=request.observations_mission,
                    retain_extraction_mode=request.retain_extraction_mode,
                    retain_custom_instructions=request.retain_custom_instructions,
                    retain_chunk_size=request.retain_chunk_size,
                    retain_default_strategy=request.retain_default_strategy,
                    retain_strategies=request.retain_strategies,
                    entity_labels=[l.model_dump() for l in request.entity_labels],
                    entities_allow_free_form=request.entities_allow_free_form,
                    enable_observations=request.enable_observations,
                    consolidation_llm_batch_size=request.consolidation_llm_batch_size,
                    consolidation_source_facts_max_tokens=request.consolidation_source_facts_max_tokens,
                    consolidation_source_facts_max_tokens_per_observation=request.consolidation_source_facts_max_tokens_per_observation,
                    disposition_skepticism=request.disposition_skepticism,
                    disposition_literalism=request.disposition_literalism,
                    disposition_empathy=request.disposition_empathy,
                    directive_seeds=[s.model_dump() for s in request.directive_seeds],
                    mental_model_seeds=[s.model_dump() for s in request.mental_model_seeds],
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(status_code=409, detail="Template already exists")
            return rec.model_dump()

        @router.get("/templates/{scope}/{name}", response_model=TemplateResponse, operation_id="get_template")
        async def get_template_endpoint(
            scope: str,
            name: str,
            principal=Depends(_require_iam("template:list")),
        ):
            """Get a template by scope and name.

            Finds any template matching (scope, name) regardless of source.
            This covers both custom templates and marketplace-installed ones.

            Args:
                scope: Template scope ('server' or 'personal').
                name: Template name.
                principal: Authenticated principal from IAM.

            Returns:
                Full template details.

            Raises:
                HTTPException: 404 if template not found.
            """
            owner = principal["user_id"] if scope == "personal" else None
            rec = await db.get_template(name, scope, owner=owner)
            if rec is None:
                raise HTTPException(status_code=404, detail="Template not found")
            return rec.model_dump()

        @router.put("/templates/{scope}/{name}", response_model=TemplateResponse, operation_id="update_template")
        async def update_template_endpoint(
            scope: str,
            name: str,
            request: UpdateTemplateRequest,
            principal=Depends(_require_iam("template:manage")),
        ):
            """Update a custom template.

            Performs cross-field validation when extraction mode or custom
            instructions are part of the update by merging with the existing
            record before applying.

            Args:
                scope: Template scope ('server' or 'personal').
                name: Template name.
                request: Partial update payload.
                principal: Authenticated principal from IAM.

            Returns:
                The updated template.

            Raises:
                HTTPException: 404 if template not found, 422 if cross-field
                    validation fails.
            """
            owner = principal["user_id"] if scope == "personal" else None
            updates = request.model_dump(exclude_unset=True)
            if "directive_seeds" in updates:
                updates["directive_seeds"] = [
                    s.model_dump() if hasattr(s, "model_dump") else s
                    for s in updates["directive_seeds"]
                ]
            if "mental_model_seeds" in updates:
                updates["mental_model_seeds"] = [
                    s.model_dump() if hasattr(s, "model_dump") else s
                    for s in updates["mental_model_seeds"]
                ]
            if "entity_labels" in updates:
                updates["entity_labels"] = [
                    l.model_dump() if hasattr(l, "model_dump") else l
                    for l in updates["entity_labels"]
                ]

            # Cross-field validation: merge with existing record to check final state.
            if "retain_extraction_mode" in updates or "retain_custom_instructions" in updates:
                existing = await db.get_template(name, scope, owner=owner)
                if existing is None:
                    raise HTTPException(status_code=404, detail="Template not found")
                merged_mode = updates.get("retain_extraction_mode", existing.retain_extraction_mode)
                merged_instructions = updates.get("retain_custom_instructions", existing.retain_custom_instructions)
                if merged_mode == "custom" and not merged_instructions:
                    raise HTTPException(
                        status_code=422,
                        detail="retain_custom_instructions required when retain_extraction_mode is 'custom'",
                    )
                if merged_mode != "custom" and merged_instructions is not None:
                    raise HTTPException(
                        status_code=422,
                        detail="retain_custom_instructions only valid when retain_extraction_mode is 'custom'",
                    )

            rec = await db.update_template(name, scope, owner=owner, updates=updates)
            if rec is None:
                raise HTTPException(status_code=404, detail="Template not found")
            return rec.model_dump()

        @router.delete("/templates/{scope}/{name}", status_code=204, operation_id="delete_template")
        async def delete_template_endpoint(
            scope: str,
            name: str,
            principal=Depends(_require_iam("template:manage")),
        ):
            """Delete a custom template.

            Args:
                scope: Template scope ('server' or 'personal').
                name: Template name.
                principal: Authenticated principal from IAM.

            Raises:
                HTTPException: 404 if template not found.
            """
            owner = principal["user_id"] if scope == "personal" else None
            deleted = await db.delete_template(name, scope, owner=owner)
            if not deleted:
                raise HTTPException(status_code=404, detail="Template not found")

        # --- Bank Creation from Template ---

        @router.post("/banks", response_model=BankCreationResponse, status_code=201, operation_id="create_bank_from_template")
        async def create_bank_from_template(
            request: CreateBankFromTemplateRequest,
            principal=Depends(_require_iam("bank:create")),
        ):
            """Create a bank from an installed template."""
            try:
                ref = parse_template_ref(request.template)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            owner = principal["user_id"] if ref.scope == "personal" else None
            template = await db.get_template(
                ref.name, ref.scope, source_name=ref.source, owner=owner,
            )
            if template is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Template not installed. Install with: "
                    f"hindclaw template install {ref.source}/{ref.name}" if ref.source
                    else f"Template '{ref.name}' not found in {ref.scope} scope",
                )

            try:
                result = await bootstrap_bank_from_template(
                    memory=_memory,
                    bank_id=request.bank_id,
                    template=template,
                    requesting_user_id=principal["user_id"],
                    bank_name=request.name,
                )
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Bank creation failed: {e}")

            return BankCreationResponse(
                bank_id=request.bank_id,
                template=request.template,
                bank_created=result.bank_created,
                config_applied=result.config_applied,
                directives=result.directives,
                mental_models=result.mental_models,
                errors=result.errors,
            )

        # --- Template Source Admin ---

        @router.post(
            "/admin/template-sources",
            response_model=SourceResponse,
            status_code=201,
            operation_id="create_template_source",
        )
        async def create_template_source(
            request: CreateSourceRequest,
            _auth=Depends(_require_iam("template:source")),
        ):
            """Register a trusted marketplace source."""
            try:
                name = request.alias or derive_source_name(request.url)
            except ValueError as e:
                raise HTTPException(422, str(e))
            try:
                rec = await db.create_template_source(
                    name=name,
                    url=request.url,
                    auth_token=request.auth_token,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Source '{name}' already exists")
            return SourceResponse(
                name=rec.name,
                url=rec.url,
                has_auth=rec.auth_token is not None,
                created_at=str(rec.created_at),
            )

        @router.get(
            "/admin/template-sources",
            response_model=list[SourceResponse],
            operation_id="list_template_sources",
        )
        async def list_template_sources(
            _auth=Depends(_require_iam("template:source")),
        ):
            """List all configured marketplace sources."""
            sources = await db.list_template_sources()
            return [
                SourceResponse(
                    name=s.name,
                    url=s.url,
                    has_auth=s.auth_token is not None,
                    created_at=str(s.created_at),
                )
                for s in sources
            ]

        @router.delete(
            "/admin/template-sources/{name}",
            status_code=204,
            operation_id="delete_template_source",
        )
        async def delete_template_source(
            name: str,
            _auth=Depends(_require_iam("template:source")),
        ):
            """Remove a trusted marketplace source."""
            deleted = await db.delete_template_source(name)
            if not deleted:
                raise HTTPException(404, f"Source '{name}' not found")

        # --- Marketplace Search ---

        @router.get(
            "/marketplace/search",
            response_model=MarketplaceSearchResponse,
            operation_id="marketplace_search",
        )
        async def marketplace_search(
            q: str | None = Query(None, description="Search query"),
            source: str | None = Query(None, description="Filter by source name"),
            tag: str | None = Query(None, description="Filter by tag"),
            principal=Depends(_require_iam("template:list")),
        ):
            """Search marketplace templates across configured sources."""
            user_id = principal.get("user_id")
            # Only visible sources: all server + caller's personal
            server_sources = await db.list_template_sources(scope="server")
            personal_sources = (
                await db.list_template_sources(scope="personal", owner=user_id)
                if user_id else []
            )
            sources = server_sources + personal_sources
            if source:
                sources = [s for s in sources if s.name == source]

            if not sources:
                return MarketplaceSearchResponse(results=[], total=0)

            # Fetch installed templates for "installed" flag.
            server_installed = await db.list_templates(scope="server")
            personal_installed = (
                await db.list_templates(scope="personal", owner=user_id)
                if user_id
                else []
            )
            # Build installed map keyed by (source_name, source_scope, template_id)
            # to prevent conflation when same source name exists in both scopes.
            installed_map: dict[tuple[str, str, str], set[str]] = {}
            for t in server_installed:
                if t.source_name:
                    key = (t.source_name, "server", t.id)
                    installed_map.setdefault(key, set()).add("server")
            for t in personal_installed:
                if t.source_name:
                    for src in sources:
                        if src.name == t.source_name:
                            key = (t.source_name, src.scope, t.id)
                            installed_map.setdefault(key, set()).add("personal")

            all_results = []
            for src in sources:
                index = await marketplace.fetch_index(src)
                if not index:
                    continue
                results = marketplace.search_marketplace(
                    index,
                    source_name=src.name,
                    source_scope=src.scope,
                    query=q,
                    tag=tag,
                )
                # Populate installed_in from the installed map
                for r in results:
                    key = (r.source, r.source_scope, r.name)
                    if key in installed_map:
                        r.installed_in = sorted(installed_map[key])
                all_results.extend(results)

            return MarketplaceSearchResponse(
                results=all_results,
                total=len(all_results),
            )

        # --- Template Install / Update ---

        @router.post(
            "/templates/install",
            response_model=TemplateResponse,
            status_code=201,
            operation_id="install_template",
        )
        async def install_template(
            request: InstallTemplateRequest,
            principal=Depends(_require_iam("template:install")),
        ):
            """Install a template from a registered marketplace source."""
            # 1. Resolve source with ambiguity detection
            try:
                source = await db.resolve_source(
                    request.source_name,
                    caller=principal["user_id"],
                    source_scope=request.source_scope,
                )
            except KeyError as e:
                raise HTTPException(404, str(e))
            except ValueError as e:
                raise HTTPException(409, str(e))

            # 2. Fetch template from marketplace
            template = await marketplace.fetch_template(source, request.name)
            if not template:
                raise HTTPException(
                    404,
                    f"Template '{request.name}' not found in source '{request.source_name}'",
                )

            # 3. Verify name matches request
            if template.name != request.name:
                raise HTTPException(
                    422,
                    f"Template name mismatch: requested '{request.name}' "
                    f"but file contains '{template.name}'",
                )

            # 4. Validate compatibility
            errors = marketplace.validate_template(template)
            if errors:
                raise HTTPException(422, "; ".join(errors))

            # 5. Determine owner
            owner = principal["user_id"] if request.scope == "personal" else None

            # 6. Upsert into bank_templates
            try:
                rec = await db.upsert_template_from_marketplace(
                    id=template.name,
                    scope=request.scope,
                    owner=owner,
                    source_name=request.source_name,
                    source_url=source.url,
                    source_revision=None,
                    schema_version=template.schema_version,
                    min_hindclaw_version=template.min_hindclaw_version,
                    min_hindsight_version=template.min_hindsight_version,
                    version=template.version,
                    description=template.description,
                    author=template.author,
                    tags=template.tags,
                    retain_mission=template.retain_mission,
                    reflect_mission=template.reflect_mission,
                    observations_mission=template.observations_mission,
                    retain_extraction_mode=template.retain_extraction_mode,
                    retain_custom_instructions=template.retain_custom_instructions,
                    retain_chunk_size=template.retain_chunk_size,
                    retain_default_strategy=template.retain_default_strategy,
                    retain_strategies=template.retain_strategies,
                    entity_labels=[l.model_dump() for l in template.entity_labels],
                    entities_allow_free_form=template.entities_allow_free_form,
                    enable_observations=template.enable_observations,
                    consolidation_llm_batch_size=template.consolidation_llm_batch_size,
                    consolidation_source_facts_max_tokens=template.consolidation_source_facts_max_tokens,
                    consolidation_source_facts_max_tokens_per_observation=template.consolidation_source_facts_max_tokens_per_observation,
                    disposition_skepticism=template.disposition_skepticism,
                    disposition_literalism=template.disposition_literalism,
                    disposition_empathy=template.disposition_empathy,
                    directive_seeds=[s.model_dump() for s in template.directive_seeds],
                    mental_model_seeds=[s.model_dump() for s in template.mental_model_seeds],
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    409,
                    f"Template '{template.name}' already exists in {request.scope} scope",
                )
            return rec.model_dump()

        @router.post(
            "/templates/{scope}/{source}/{name}/update",
            response_model=TemplateUpdateResponse,
            operation_id="update_template_from_marketplace",
        )
        async def update_template_from_marketplace(
            scope: str,
            source: str,
            name: str,
            principal=Depends(_require_iam("template:manage")),
        ):
            """Update an installed template from its marketplace source."""
            # 1. Look up installed template
            owner = principal["user_id"] if scope == "personal" else None
            installed = await db.get_template(
                name, scope, source_name=source, owner=owner,
            )
            if not installed:
                raise HTTPException(
                    404,
                    f"Template '{source}/{name}' not installed in {scope} scope",
                )

            # 2. Look up the source
            src = await db.get_template_source(source)
            if not src:
                raise HTTPException(
                    404,
                    f"Source '{source}' not found. Was it removed?",
                )

            # 3. Fetch latest from marketplace
            latest = await marketplace.fetch_template(src, name)
            if not latest:
                raise HTTPException(
                    404,
                    f"Template '{name}' no longer available in source '{source}'",
                )

            # 4. Verify name matches
            if latest.name != name:
                raise HTTPException(
                    422,
                    f"Template name mismatch: requested '{name}' "
                    f"but file contains '{latest.name}'",
                )

            # 5. Validate compatibility
            errors = marketplace.validate_template(latest)
            if errors:
                raise HTTPException(422, "; ".join(errors))

            # 6. Check if newer
            if installed.version and latest.version:
                if is_version_compatible(installed.version, latest.version):
                    # installed >= latest — no update needed
                    return TemplateUpdateResponse(
                        updated=False,
                        previous_version=installed.version,
                        new_version=latest.version,
                    )

            # 7. Apply update
            rec = await db.upsert_template_from_marketplace(
                id=latest.name,
                scope=scope,
                owner=owner,
                source_name=source,
                source_url=src.url,
                source_revision=None,
                schema_version=latest.schema_version,
                min_hindclaw_version=latest.min_hindclaw_version,
                min_hindsight_version=latest.min_hindsight_version,
                version=latest.version,
                description=latest.description,
                author=latest.author,
                tags=latest.tags,
                retain_mission=latest.retain_mission,
                reflect_mission=latest.reflect_mission,
                observations_mission=latest.observations_mission,
                retain_extraction_mode=latest.retain_extraction_mode,
                retain_custom_instructions=latest.retain_custom_instructions,
                retain_chunk_size=latest.retain_chunk_size,
                retain_default_strategy=latest.retain_default_strategy,
                retain_strategies=latest.retain_strategies,
                entity_labels=[l.model_dump() for l in latest.entity_labels],
                entities_allow_free_form=latest.entities_allow_free_form,
                enable_observations=latest.enable_observations,
                consolidation_llm_batch_size=latest.consolidation_llm_batch_size,
                consolidation_source_facts_max_tokens=latest.consolidation_source_facts_max_tokens,
                consolidation_source_facts_max_tokens_per_observation=latest.consolidation_source_facts_max_tokens_per_observation,
                disposition_skepticism=latest.disposition_skepticism,
                disposition_literalism=latest.disposition_literalism,
                disposition_empathy=latest.disposition_empathy,
                directive_seeds=[s.model_dump() for s in latest.directive_seeds],
                mental_model_seeds=[s.model_dump() for s in latest.mental_model_seeds],
            )
            return TemplateUpdateResponse(
                updated=True,
                previous_version=installed.version,
                new_version=latest.version,
                template=rec.model_dump(),
            )

        return router

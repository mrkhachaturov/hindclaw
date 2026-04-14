"""HindclawHttp — Hindsight HttpExtension for managing access control.

REST API at /ext/hindclaw/ for users, groups, permissions, strategies, API keys.
Parses JWT independently — /ext/ routes do NOT pass through TenantExtension.

See spec Section 8.
"""

import logging
import secrets
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from hindsight_api.api.http import (  # type: ignore[attr-defined]
    BankTemplateManifest,
    validate_bank_template,
)
from hindsight_api.extensions import AuthenticationError, HttpExtension
from hindsight_api.models import RequestContext  # type: ignore[attr-defined]

from hindclaw_ext import db, marketplace
from hindclaw_ext.auth import decode_jwt
from hindclaw_ext.bank_bootstrap import bootstrap_bank_from_template
from hindclaw_ext.http_models import (
    AddChannelRequest,
    AddMemberRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    BankPolicyResponse,
    ChannelResponse,
    CheckUpdateResponse,
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
    GroupMemberResponse,
    GroupMembershipConfirmation,
    GroupSummaryResponse,
    InstallTemplateRequest,
    ListTemplatesResponse,
    MeProfileResponse,
    PatchTemplateRequest,
    PolicyAttachmentResponse,
    PolicyResponse,
    SAKeyCreateResponse,
    SAKeyResponse,
    ServiceAccountResponse,
    SourceResponse,
    TemplateResponse,
    UpdateGroupRequest,
    UpdatePolicyRequest,
    UpdateSelfServiceAccountRequest,
    UpdateServiceAccountRequest,
    UpdateTemplateResponse,
    UpdateUserRequest,
    UpsertBankPolicyRequest,
    UserResponse,
)
from hindclaw_ext.marketplace import derive_source_name
from hindclaw_ext.models import ServiceAccountRecord, TemplateRecord
from hindclaw_ext.policy_engine import AccessResult, apply_sa_scoping, evaluate_access
from hindclaw_ext.policy_models import BankPolicyDocument, PolicyDocument
from hindclaw_ext.template_models import CatalogEntry, TemplateScope

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
            return {
                "principal_type": "service_account",
                "principal_id": f"sa:{sa.id}",
                "action": action,
                "user_id": user_id,
                "sa_id": sa.id,
            }
        if not parent_access.allowed:
            raise AuthenticationError(f"{action} denied for {user_id}")
        return {
            "principal_type": "service_account",
            "principal_id": f"sa:{sa.id}",
            "action": action,
            "user_id": user_id,
            "sa_id": sa.id,
        }

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

    return {
        "principal_type": "user",
        "principal_id": user_id,
        "action": action,
        "user_id": user_id,
    }


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


async def _require_action(user_id: str, action: str) -> None:
    """Second-pass policy check (user already authenticated).

    Args:
        user_id: The authenticated user ID.
        action: Required action (e.g., "template:admin").

    Raises:
        HTTPException: 403 if the user lacks the required action.
    """
    access = await _evaluate_iam_access(user_id, action)
    if not access.allowed:
        raise HTTPException(403, f"Server scope requires {action}")


def _require_iam_user_only(action: str):
    """IAM check that also rejects SA credentials.

    Used for /me/api-keys endpoints where SAs must not mint user keys.

    Args:
        action: Required IAM action.

    Returns:
        Async FastAPI dependency function.
    """

    async def dependency(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
        token = credentials.credentials
        if token.startswith("hc_sa_"):
            raise HTTPException(403, "Service account credentials not accepted on /me/ endpoints")
        return await require_admin_for_action(action, credentials)

    return dependency


async def _authenticate_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Authenticate and return principal — user credentials only, no IAM check.

    Rejects service-account credentials. Used for /me endpoints that
    don't require a specific IAM action (e.g., GET /me profile).

    Returns:
        Dict with principal info (user_id, principal_type).

    Raises:
        HTTPException: 403 if SA credentials used.
        AuthenticationError: If token is invalid.
    """
    token = credentials.credentials
    if token.startswith("hc_sa_"):
        raise HTTPException(403, "Service account credentials not accepted on /me/ endpoints")

    if token.startswith("eyJ"):
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
            return {
                "principal_type": "user",
                "principal_id": user.id,
                "user_id": user.id,
            }
        raise AuthenticationError("JWT must have sender")
    else:
        key_record = await db.get_api_key(token)
        if not key_record:
            raise AuthenticationError("Invalid API key")
        user = await db.get_user(key_record.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        return {
            "principal_type": "user",
            "principal_id": key_record.user_id,
            "user_id": key_record.user_id,
        }


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
            return [
                {
                    "id": r["id"],
                    "display_name": r["display_name"],
                    "email": r["email"],
                    "is_active": r["is_active"],
                }
                for r in rows
            ]

        @router.post(
            "/users",
            status_code=201,
            response_model=UserResponse,
            operation_id="create_user",
        )
        async def create_user(req: CreateUserRequest, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_users (id, display_name, email, is_active) VALUES ($1, $2, $3, $4)",
                    req.id,
                    req.display_name,
                    req.email,
                    req.is_active,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"User {req.id} already exists")
            return {
                "id": req.id,
                "display_name": req.display_name,
                "email": req.email,
                "is_active": req.is_active,
            }

        @router.get("/users/{user_id}", response_model=UserResponse, operation_id="get_user")
        async def get_user(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
            pool = await db.get_pool()
            row = await pool.fetchrow(
                "SELECT id, display_name, email, is_active FROM hindclaw_users WHERE id = $1",
                user_id,
            )
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return {
                "id": row["id"],
                "display_name": row["display_name"],
                "email": row["email"],
                "is_active": row["is_active"],
            }

        @router.put("/users/{user_id}", response_model=UserResponse, operation_id="update_user")
        async def update_user(
            user_id: str,
            req: UpdateUserRequest,
            _auth=Depends(_require_iam("iam:users:write")),
        ):
            pool = await db.get_pool()
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(400, "No fields to update")
            # Column names come from Pydantic model field names (not user input) — safe
            set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates.keys()))
            set_clause += ", updated_at = NOW()"
            row = await pool.fetchrow(
                f"UPDATE hindclaw_users SET {set_clause} WHERE id = $1 RETURNING id, display_name, email, is_active",
                user_id,
                *updates.values(),
            )
            if not row:
                raise HTTPException(404, f"User {user_id} not found")
            return {
                "id": row["id"],
                "display_name": row["display_name"],
                "email": row["email"],
                "is_active": row["is_active"],
            }

        @router.delete("/users/{user_id}", status_code=204, operation_id="delete_user")
        async def delete_user(user_id: str, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            existing = await pool.fetchval("SELECT id FROM hindclaw_users WHERE id = $1", user_id)
            if not existing:
                raise HTTPException(404, f"User {user_id} not found")
            # FK CASCADE handles channels, api_keys, group_members, policy_attachments, service_accounts
            await pool.execute("DELETE FROM hindclaw_users WHERE id = $1", user_id)

        # --- User Channels ---

        @router.get(
            "/users/{user_id}/channels",
            response_model=list[ChannelResponse],
            operation_id="list_user_channels",
        )
        async def list_user_channels(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT provider, sender_id FROM hindclaw_user_channels WHERE user_id = $1",
                user_id,
            )
            return [{"provider": r["provider"], "sender_id": r["sender_id"]} for r in rows]

        @router.post(
            "/users/{user_id}/channels",
            status_code=201,
            response_model=ChannelResponse,
            operation_id="add_user_channel",
        )
        async def add_user_channel(
            user_id: str,
            req: AddChannelRequest,
            _auth=Depends(_require_iam("iam:users:write")),
        ):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_user_channels (user_id, provider, sender_id) VALUES ($1, $2, $3)",
                    user_id,
                    req.provider,
                    req.sender_id,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Channel {req.provider}:{req.sender_id} already mapped")
            return {"provider": req.provider, "sender_id": req.sender_id}

        @router.delete(
            "/users/{user_id}/channels/{provider}/{sender_id}",
            status_code=204,
            operation_id="remove_user_channel",
        )
        async def remove_user_channel(
            user_id: str,
            provider: str,
            sender_id: str,
            _auth=Depends(_require_iam("iam:users:write")),
        ):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_user_channels WHERE user_id = $1 AND provider = $2 AND sender_id = $3",
                user_id,
                provider,
                sender_id,
            )

        # --- Groups ---

        @router.get(
            "/groups",
            response_model=list[GroupSummaryResponse],
            operation_id="list_groups",
        )
        async def list_groups(_auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch("SELECT id, display_name FROM hindclaw_groups ORDER BY id")
            return [{"id": r["id"], "display_name": r["display_name"]} for r in rows]

        @router.post(
            "/groups",
            status_code=201,
            response_model=GroupSummaryResponse,
            operation_id="create_group",
        )
        async def create_group(req: CreateGroupRequest, _auth=Depends(_require_iam("iam:groups:write"))):
            pool = await db.get_pool()
            try:
                await pool.execute(
                    "INSERT INTO hindclaw_groups (id, display_name) VALUES ($1, $2)",
                    req.id,
                    req.display_name,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Group {req.id} already exists")
            return {"id": req.id, "display_name": req.display_name}

        @router.get(
            "/groups/{group_id}",
            response_model=GroupSummaryResponse,
            operation_id="get_group",
        )
        async def get_group(group_id: str, _auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            row = await pool.fetchrow(
                "SELECT id, display_name FROM hindclaw_groups WHERE id = $1",
                group_id,
            )
            if not row:
                raise HTTPException(404, f"Group {group_id} not found")
            return {"id": row["id"], "display_name": row["display_name"]}

        @router.put(
            "/groups/{group_id}",
            response_model=GroupSummaryResponse,
            operation_id="update_group",
        )
        async def update_group(
            group_id: str,
            req: UpdateGroupRequest,
            _auth=Depends(_require_iam("iam:groups:write")),
        ):
            pool = await db.get_pool()
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(400, "No fields to update")
            set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates.keys()))
            set_clause += ", updated_at = NOW()"
            row = await pool.fetchrow(
                f"UPDATE hindclaw_groups SET {set_clause} WHERE id = $1 RETURNING id, display_name",
                group_id,
                *updates.values(),
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

        @router.get(
            "/groups/{group_id}/members",
            response_model=list[GroupMemberResponse],
            operation_id="list_group_members",
        )
        async def list_group_members(group_id: str, _auth=Depends(_require_iam("iam:groups:read"))):
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT user_id FROM hindclaw_group_members WHERE group_id = $1 ORDER BY user_id",
                group_id,
            )
            return [{"user_id": r["user_id"]} for r in rows]

        @router.post(
            "/groups/{group_id}/members",
            status_code=201,
            response_model=GroupMembershipConfirmation,
            operation_id="add_group_member",
        )
        async def add_group_member(
            group_id: str,
            req: AddMemberRequest,
            _auth=Depends(_require_iam("iam:groups:write")),
        ):
            pool = await db.get_pool()
            await pool.execute(
                "INSERT INTO hindclaw_group_members (group_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                group_id,
                req.user_id,
            )
            return {"group_id": group_id, "user_id": req.user_id}

        @router.delete(
            "/groups/{group_id}/members/{user_id}",
            status_code=204,
            operation_id="remove_group_member",
        )
        async def remove_group_member(group_id: str, user_id: str, _auth=Depends(_require_iam("iam:groups:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_group_members WHERE group_id = $1 AND user_id = $2",
                group_id,
                user_id,
            )

        # --- API Keys ---

        @router.get(
            "/users/{user_id}/api-keys",
            response_model=list[ApiKeyResponse],
            operation_id="list_api_keys",
        )
        async def list_api_keys(user_id: str, _auth=Depends(_require_iam("iam:users:read"))):
            """List API keys for a user. Keys are masked after creation."""
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT id, api_key, description FROM hindclaw_api_keys WHERE user_id = $1 ORDER BY id",
                user_id,
            )
            return [
                {
                    "id": r["id"],
                    "api_key_prefix": r["api_key"][:_API_KEY_MASK_LENGTH] + "...",
                    "description": r["description"],
                }
                for r in rows
            ]

        @router.post(
            "/users/{user_id}/api-keys",
            status_code=201,
            response_model=ApiKeyCreateResponse,
            operation_id="create_api_key",
        )
        async def create_api_key(
            user_id: str,
            req: CreateApiKeyRequest,
            _auth=Depends(_require_iam("iam:users:write")),
        ):
            pool = await db.get_pool()
            key_id = secrets.token_hex(8)
            api_key = f"hc_u_{user_id}_{secrets.token_hex(16)}"
            await pool.execute(
                "INSERT INTO hindclaw_api_keys (id, api_key, user_id, description) VALUES ($1, $2, $3, $4)",
                key_id,
                api_key,
                user_id,
                req.description,
            )
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete(
            "/users/{user_id}/api-keys/{key_id}",
            status_code=204,
            operation_id="delete_api_key",
        )
        async def delete_api_key(user_id: str, key_id: str, _auth=Depends(_require_iam("iam:users:write"))):
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_api_keys WHERE id = $1 AND user_id = $2",
                key_id,
                user_id,
            )

        # --- Policies ---

        @router.get(
            "/policies",
            response_model=list[PolicyResponse],
            operation_id="list_policies",
        )
        async def list_policies(_auth=Depends(_require_iam("iam:policies:read"))):
            results = await db.list_policies()
            return [
                {
                    "id": r.id,
                    "display_name": r.display_name,
                    "document": r.document_json,
                    "is_builtin": r.is_builtin,
                }
                for r in results
            ]

        @router.post(
            "/policies",
            status_code=201,
            response_model=PolicyResponse,
            operation_id="create_policy",
        )
        async def create_policy(req: CreatePolicyRequest, _auth=Depends(_require_iam("iam:policies:write"))):
            PolicyDocument(**req.document)
            await db.create_policy(req.id, req.display_name, req.document)
            return {
                "id": req.id,
                "display_name": req.display_name,
                "document": req.document,
                "is_builtin": False,
            }

        @router.get(
            "/policies/{policy_id}",
            response_model=PolicyResponse,
            operation_id="get_policy",
        )
        async def get_policy_endpoint(policy_id: str, _auth=Depends(_require_iam("iam:policies:read"))):
            result = await db.get_policy(policy_id)
            if not result:
                raise HTTPException(404, f"Policy {policy_id} not found")
            return {
                "id": result.id,
                "display_name": result.display_name,
                "document": result.document_json,
                "is_builtin": result.is_builtin,
            }

        @router.put(
            "/policies/{policy_id}",
            response_model=PolicyResponse,
            operation_id="update_policy",
        )
        async def update_policy_endpoint(
            policy_id: str,
            req: UpdatePolicyRequest,
            _auth=Depends(_require_iam("iam:policies:write")),
        ):
            if req.document:
                PolicyDocument(**req.document)
            updated = await db.update_policy(policy_id, req.display_name, req.document)
            if not updated:
                raise HTTPException(404, f"Policy {policy_id} not found or is built-in")
            result = await db.get_policy(policy_id)
            if result is None:
                raise HTTPException(500, f"Policy {policy_id} disappeared after update")
            return {
                "id": result.id,
                "display_name": result.display_name,
                "document": result.document_json,
                "is_builtin": result.is_builtin,
            }

        @router.delete("/policies/{policy_id}", status_code=204, operation_id="delete_policy")
        async def delete_policy_endpoint(policy_id: str, _auth=Depends(_require_iam("iam:policies:write"))):
            existing = await db.get_policy(policy_id)
            if not existing:
                raise HTTPException(404, f"Policy {policy_id} not found")
            await db.delete_policy(policy_id)

        # --- Policy Attachments ---

        @router.get(
            "/policy-attachments",
            response_model=list[PolicyAttachmentResponse],
            operation_id="list_policy_attachments",
        )
        async def list_attachments(
            policy_id: str = Query(...),
            _auth=Depends(_require_iam("iam:policies:read")),
        ):
            return await db.list_policy_attachments(policy_id)

        @router.put(
            "/policy-attachments",
            response_model=PolicyAttachmentResponse,
            operation_id="upsert_policy_attachment",
        )
        async def upsert_attachment(
            req: CreatePolicyAttachmentRequest,
            _auth=Depends(_require_iam("iam:attachments:write")),
        ):
            await db.create_policy_attachment(req.policy_id, req.principal_type, req.principal_id, req.priority)
            return req.model_dump()

        @router.delete(
            "/policy-attachments/{policy_id}/{principal_type}/{principal_id}",
            status_code=204,
            operation_id="delete_policy_attachment",
        )
        async def delete_attachment(
            policy_id: str,
            principal_type: str,
            principal_id: str,
            _auth=Depends(_require_iam("iam:attachments:write")),
        ):
            existing = await db.get_policy_attachment(policy_id, principal_type, principal_id)
            if not existing:
                raise HTTPException(
                    404,
                    f"Attachment {policy_id}/{principal_type}/{principal_id} not found",
                )
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

        @router.get(
            "/me/service-accounts",
            response_model=list[ServiceAccountResponse],
            operation_id="list_my_service_accounts",
        )
        async def list_my_service_accounts(
            _auth=Depends(_require_iam("iam:service_accounts:read")),
        ):
            return await db.list_service_accounts_by_owner(_auth["user_id"])

        @router.post(
            "/me/service-accounts",
            status_code=201,
            response_model=ServiceAccountResponse,
            operation_id="create_my_service_account",
        )
        async def create_my_service_account(
            req: CreateSelfServiceAccountRequest,
            _auth=Depends(_require_iam("iam:service_accounts:write")),
        ):
            owner_user_id = _auth["user_id"]
            await db.create_service_account(req.id, owner_user_id, req.display_name, req.scoping_policy_id)
            return {
                "id": req.id,
                "owner_user_id": owner_user_id,
                "display_name": req.display_name,
                "is_active": True,
                "scoping_policy_id": req.scoping_policy_id,
            }

        @router.get(
            "/me/service-accounts/{sa_id}",
            response_model=ServiceAccountResponse,
            operation_id="get_my_service_account",
        )
        async def get_my_service_account(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:read"))):
            return await _get_owned_sa(sa_id, _auth["user_id"])

        @router.put(
            "/me/service-accounts/{sa_id}",
            response_model=ServiceAccountResponse,
            operation_id="update_my_service_account",
        )
        async def update_my_service_account(
            sa_id: str,
            req: UpdateSelfServiceAccountRequest,
            _auth=Depends(_require_iam("iam:service_accounts:write")),
        ):
            await _get_owned_sa(sa_id, _auth["user_id"])
            await db.update_service_account(sa_id, display_name=req.display_name)
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.delete(
            "/me/service-accounts/{sa_id}",
            status_code=204,
            operation_id="delete_my_service_account",
        )
        async def delete_my_service_account(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:write"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            await db.delete_service_account(sa_id)

        @router.get(
            "/me/service-accounts/{sa_id}/keys",
            response_model=list[SAKeyResponse],
            operation_id="list_my_sa_keys",
        )
        async def list_my_sa_keys(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:read"))):
            await _get_owned_sa(sa_id, _auth["user_id"])
            keys = await db.list_sa_keys(sa_id)
            return [
                {
                    "id": k.id,
                    "api_key_prefix": k.api_key[:_API_KEY_MASK_LENGTH],
                    "description": k.description,
                }
                for k in keys
            ]

        @router.post(
            "/me/service-accounts/{sa_id}/keys",
            status_code=201,
            response_model=SAKeyCreateResponse,
            operation_id="create_my_sa_key",
        )
        async def create_my_sa_key(
            sa_id: str,
            req: CreateSAKeyRequest,
            _auth=Depends(_require_iam("iam:service_account_keys:write")),
        ):
            await _get_owned_sa(sa_id, _auth["user_id"])
            key_id = secrets.token_hex(8)
            api_key = f"hc_sa_{sa_id}_{secrets.token_hex(16)}"
            await db.create_sa_key(key_id, sa_id, api_key, req.description)
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete(
            "/me/service-accounts/{sa_id}/keys/{key_id}",
            status_code=204,
            operation_id="delete_my_sa_key",
        )
        async def delete_my_sa_key(
            sa_id: str,
            key_id: str,
            _auth=Depends(_require_iam("iam:service_account_keys:write")),
        ):
            await _get_owned_sa(sa_id, _auth["user_id"])
            existing = await db.get_sa_key(key_id, sa_id)
            if not existing:
                raise HTTPException(404, f"SA key {key_id} not found")
            await db.delete_sa_key(key_id, sa_id)

        # --- Self-Service Profile (/me) ---

        @router.get("/me", response_model=MeProfileResponse, operation_id="get_my_profile")
        async def get_my_profile(_auth=Depends(_authenticate_user)):
            """Return the caller's own profile including channels.

            Args:
                _auth: Authenticated principal (user only, SA rejected).

            Returns:
                MeProfileResponse with user record and channel list.
            """
            user = await db.get_user(_auth["user_id"])
            if user is None:
                raise HTTPException(404, f"User {_auth['user_id']} not found")
            pool = await db.get_pool()
            channel_rows = await pool.fetch(
                "SELECT provider, sender_id FROM hindclaw_user_channels WHERE user_id = $1",
                _auth["user_id"],
            )
            return MeProfileResponse(
                id=user.id,
                display_name=user.display_name,
                email=user.email,
                is_active=user.is_active,
                channels=[{"provider": c["provider"], "sender_id": c["sender_id"]} for c in channel_rows],
            )

        # --- Self-Service API Keys (/me/api-keys) ---

        @router.get(
            "/me/api-keys",
            response_model=list[ApiKeyResponse],
            operation_id="list_my_api_keys",
        )
        async def list_my_api_keys(
            _auth=Depends(_require_iam_user_only("iam:api_keys:read")),
        ):
            """List the caller's own API keys (masked).

            Args:
                _auth: Authenticated principal (user only, SA rejected).

            Returns:
                List of ApiKeyResponse with masked key prefixes.
            """
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT id, api_key, description FROM hindclaw_api_keys WHERE user_id = $1 ORDER BY id",
                _auth["user_id"],
            )
            return [
                {
                    "id": r["id"],
                    "api_key_prefix": r["api_key"][:_API_KEY_MASK_LENGTH] + "...",
                    "description": r["description"],
                }
                for r in rows
            ]

        @router.post(
            "/me/api-keys",
            status_code=201,
            response_model=ApiKeyCreateResponse,
            operation_id="create_my_api_key",
        )
        async def create_my_api_key(
            req: CreateApiKeyRequest,
            _auth=Depends(_require_iam_user_only("iam:api_keys:write")),
        ):
            """Create a new API key for the caller.

            Args:
                req: CreateApiKeyRequest with optional description.
                _auth: Authenticated principal (user only, SA rejected).

            Returns:
                ApiKeyCreateResponse with full api_key shown once.
            """
            pool = await db.get_pool()
            user_id = _auth["user_id"]
            key_id = secrets.token_hex(8)
            api_key = f"hc_u_{user_id}_{secrets.token_hex(16)}"
            await pool.execute(
                "INSERT INTO hindclaw_api_keys (id, api_key, user_id, description) VALUES ($1, $2, $3, $4)",
                key_id,
                api_key,
                user_id,
                req.description,
            )
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete("/me/api-keys/{key_id}", status_code=204, operation_id="delete_my_api_key")
        async def delete_my_api_key(key_id: str, _auth=Depends(_require_iam_user_only("iam:api_keys:write"))):
            """Delete one of the caller's own API keys.

            Scoped to the caller's user_id — cannot delete other users' keys.

            Args:
                key_id: API key record ID.
                _auth: Authenticated principal (user only, SA rejected).
            """
            pool = await db.get_pool()
            await pool.execute(
                "DELETE FROM hindclaw_api_keys WHERE id = $1 AND user_id = $2",
                key_id,
                _auth["user_id"],
            )

        # --- Self-Service Template Sources (/me/template-sources) ---

        @router.get(
            "/me/template-sources",
            response_model=list[SourceResponse],
            operation_id="list_my_template_sources",
        )
        async def list_my_template_sources(
            _auth=Depends(_require_iam("template:source")),
        ):
            """List the caller's personal template sources.

            Scoped to the caller's user_id — only returns sources with
            scope='personal' owned by the authenticated principal.

            Args:
                _auth: Authenticated principal (users and SAs allowed).

            Returns:
                List of SourceResponse for the caller's personal sources.
            """
            sources = await db.list_template_sources(scope="personal", owner=_auth["user_id"])
            return [
                SourceResponse(
                    name=s.name,
                    url=s.url,
                    scope=TemplateScope(s.scope),
                    owner=s.owner,
                    has_auth=s.auth_token is not None,
                    description=s.description,
                    created_at=str(s.created_at) if s.created_at else None,
                    updated_at=str(s.updated_at) if s.updated_at else None,
                )
                for s in sources
            ]

        @router.post(
            "/me/template-sources",
            response_model=SourceResponse,
            status_code=201,
            operation_id="create_my_template_source",
        )
        async def create_my_template_source(
            request: CreateSourceRequest,
            _auth=Depends(_require_iam("template:source")),
        ):
            """Register a personal template source for the caller.

            Source is created with scope='personal' and owner set to the
            caller's user_id. Name is derived from the URL unless an alias
            is provided.

            Args:
                request: CreateSourceRequest with url and optional alias/auth_token.
                _auth: Authenticated principal (users and SAs allowed).

            Returns:
                SourceResponse for the newly created personal source.

            Raises:
                HTTPException: 422 if the source name cannot be derived from the URL.
                HTTPException: 409 if a personal source with that name already exists.
            """
            try:
                name = request.alias or derive_source_name(request.url)
            except ValueError as e:
                raise HTTPException(422, str(e))
            try:
                rec = await db.create_template_source(
                    name=name,
                    url=request.url,
                    scope="personal",
                    owner=_auth["user_id"],
                    auth_token=request.auth_token,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, f"Source '{name}' already exists in your personal sources")
            return SourceResponse(
                name=rec.name,
                url=rec.url,
                scope=TemplateScope(rec.scope),
                owner=rec.owner,
                has_auth=rec.auth_token is not None,
                description=rec.description,
                created_at=str(rec.created_at) if rec.created_at else None,
                updated_at=str(rec.updated_at) if rec.updated_at else None,
            )

        @router.delete(
            "/me/template-sources/{name}",
            status_code=204,
            operation_id="delete_my_template_source",
        )
        async def delete_my_template_source(
            name: str,
            _auth=Depends(_require_iam("template:source")),
        ):
            """Remove a personal template source owned by the caller.

            Only deletes sources with scope='personal' that belong to the
            caller — cannot affect other users' sources or server-scope sources.

            Args:
                name: Template source name to delete.
                _auth: Authenticated principal (users and SAs allowed).

            Raises:
                HTTPException: 404 if the source is not found in the caller's
                    personal sources.
            """
            deleted = await db.delete_template_source(name, scope="personal", owner=_auth["user_id"])
            if not deleted:
                raise HTTPException(404, f"Source '{name}' not found in your personal sources")

        # --- Service Accounts ---

        @router.get(
            "/service-accounts",
            response_model=list[ServiceAccountResponse],
            operation_id="list_service_accounts",
        )
        async def list_service_accounts(
            _auth=Depends(_require_iam("iam:service_accounts:manage")),
        ):
            return await db.list_service_accounts()

        @router.post(
            "/service-accounts",
            status_code=201,
            response_model=ServiceAccountResponse,
            operation_id="create_service_account",
        )
        async def create_service_account(
            req: CreateServiceAccountRequest,
            _auth=Depends(_require_iam("iam:service_accounts:manage")),
        ):
            await db.create_service_account(req.id, req.owner_user_id, req.display_name, req.scoping_policy_id)
            return {
                "id": req.id,
                "owner_user_id": req.owner_user_id,
                "display_name": req.display_name,
                "is_active": True,
                "scoping_policy_id": req.scoping_policy_id,
            }

        @router.get(
            "/service-accounts/{sa_id}",
            response_model=ServiceAccountResponse,
            operation_id="get_service_account",
        )
        async def get_service_account_endpoint(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            result = await db.get_service_account(sa_id)
            if not result:
                raise HTTPException(404, f"Service account {sa_id} not found")
            return result

        @router.put(
            "/service-accounts/{sa_id}",
            response_model=ServiceAccountResponse,
            operation_id="update_service_account",
        )
        async def update_service_account_endpoint(
            sa_id: str,
            req: UpdateServiceAccountRequest,
            _auth=Depends(_require_iam("iam:service_accounts:manage")),
        ):
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

        @router.delete(
            "/service-accounts/{sa_id}",
            status_code=204,
            operation_id="delete_service_account",
        )
        async def delete_service_account_endpoint(
            sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))
        ):
            existing = await db.get_service_account(sa_id)
            if not existing:
                raise HTTPException(404, f"Service account {sa_id} not found")
            await db.delete_service_account(sa_id)

        # --- SA Keys ---

        @router.get(
            "/service-accounts/{sa_id}/keys",
            response_model=list[SAKeyResponse],
            operation_id="list_sa_keys",
        )
        async def list_sa_keys(sa_id: str, _auth=Depends(_require_iam("iam:service_accounts:manage"))):
            keys = await db.list_sa_keys(sa_id)
            return [
                {
                    "id": k.id,
                    "api_key_prefix": k.api_key[:_API_KEY_MASK_LENGTH],
                    "description": k.description,
                }
                for k in keys
            ]

        @router.post(
            "/service-accounts/{sa_id}/keys",
            status_code=201,
            response_model=SAKeyCreateResponse,
            operation_id="create_sa_key",
        )
        async def create_sa_key(
            sa_id: str,
            req: CreateSAKeyRequest,
            _auth=Depends(_require_iam("iam:service_accounts:manage")),
        ):
            key_id = secrets.token_hex(8)
            api_key = f"hc_sa_{sa_id}_{secrets.token_hex(16)}"
            await db.create_sa_key(key_id, sa_id, api_key, req.description)
            return {"id": key_id, "api_key": api_key, "description": req.description}

        @router.delete(
            "/service-accounts/{sa_id}/keys/{key_id}",
            status_code=204,
            operation_id="delete_sa_key",
        )
        async def delete_sa_key(
            sa_id: str,
            key_id: str,
            _auth=Depends(_require_iam("iam:service_accounts:manage")),
        ):
            existing = await db.get_sa_key(key_id, sa_id)
            if not existing:
                raise HTTPException(404, f"SA key {key_id} not found")
            await db.delete_sa_key(key_id, sa_id)

        # --- Bank Policies ---

        @router.get(
            "/banks/{bank_id}/policy",
            response_model=BankPolicyResponse,
            operation_id="get_bank_policy",
        )
        async def get_bank_policy_endpoint(bank_id: str, _auth=Depends(_require_iam("iam:banks:read"))):
            result = await db.get_bank_policy(bank_id)
            if not result:
                raise HTTPException(404, f"Bank policy for {bank_id} not found")
            return {"bank_id": result.bank_id, "document": result.document_json}

        @router.put(
            "/banks/{bank_id}/policy",
            response_model=BankPolicyResponse,
            operation_id="upsert_bank_policy",
        )
        async def upsert_bank_policy_endpoint(
            bank_id: str,
            req: UpsertBankPolicyRequest,
            _auth=Depends(_require_iam("iam:banks:write")),
        ):
            BankPolicyDocument(**req.document)
            await db.upsert_bank_policy(bank_id, req.document)
            return {"bank_id": bank_id, "document": req.document}

        @router.delete(
            "/banks/{bank_id}/policy",
            status_code=204,
            operation_id="delete_bank_policy",
        )
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
            from hindclaw_ext.validator import (
                _resolve_public_access,
                _resolve_sa_access,
                _resolve_user_access,
            )

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

        # --- Template Source Admin ---

        @router.post(
            "/admin/template-sources",
            response_model=SourceResponse,
            status_code=201,
            operation_id="create_template_source",
        )
        async def create_template_source(
            request: CreateSourceRequest,
            _auth=Depends(_require_iam("template:admin")),
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
                scope=TemplateScope(rec.scope),
                owner=rec.owner,
                has_auth=rec.auth_token is not None,
                description=rec.description,
                created_at=str(rec.created_at) if rec.created_at else None,
                updated_at=str(rec.updated_at) if rec.updated_at else None,
            )

        @router.get(
            "/admin/template-sources",
            response_model=list[SourceResponse],
            operation_id="list_template_sources",
        )
        async def list_template_sources(
            _auth=Depends(_require_iam("template:admin")),
        ):
            """List all configured marketplace sources."""
            sources = await db.list_template_sources()
            return [
                SourceResponse(
                    name=s.name,
                    url=s.url,
                    scope=TemplateScope(s.scope),
                    owner=s.owner,
                    has_auth=s.auth_token is not None,
                    description=s.description,
                    created_at=str(s.created_at) if s.created_at else None,
                    updated_at=str(s.updated_at) if s.updated_at else None,
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
            _auth=Depends(_require_iam("template:admin")),
        ):
            """Remove a trusted marketplace source."""
            deleted = await db.delete_template_source(name)
            if not deleted:
                raise HTTPException(404, f"Source '{name}' not found")

        # --- Templates (post-convergence) ----------------------------- #
        # Identity tuple: (id, scope, owner). Manifest is opaque upstream JSONB.
        # See spec docs/rkstack/specs/hindclaw/2026-04-13-template-upstream-convergence-design.md.

        def _now_utc() -> datetime:
            return datetime.now(timezone.utc)

        def _record_to_response(record: TemplateRecord) -> TemplateResponse:
            """Convert a stored TemplateRecord to its API response shape."""
            return TemplateResponse(
                id=record.id,
                name=record.name,
                description=record.description,
                category=record.category,
                integrations=record.integrations,
                tags=record.tags,
                scope=record.scope,
                owner=record.owner,
                source_name=record.source_name,
                source_scope=record.source_scope,
                source_revision=record.source_revision,
                installed_at=record.installed_at,
                updated_at=record.updated_at,
                manifest=record.manifest,
            )

        def _validate_manifest_or_422(manifest: BankTemplateManifest) -> None:
            errors = validate_bank_template(manifest)
            if errors:
                raise HTTPException(status_code=422, detail={"manifest_errors": errors})

        def _build_hand_authored_record(
            request: CreateTemplateRequest,
            *,
            scope: TemplateScope,
            owner: str | None,
        ) -> TemplateRecord:
            """Build a TemplateRecord for a POST /me|/admin/templates body."""
            now = _now_utc()
            return TemplateRecord(
                id=request.id,
                scope=scope,
                owner=owner,
                source_name=None,
                source_scope=None,
                source_template_id=None,
                source_url=None,
                source_revision=None,
                name=request.name,
                description=request.description,
                category=request.category,
                integrations=request.integrations,
                tags=request.tags,
                manifest=request.manifest.model_dump(exclude_none=True),
                installed_at=now,
                updated_at=now,
            )

        def _apply_patch(
            existing: TemplateRecord,
            patch: PatchTemplateRequest,
        ) -> TemplateRecord:
            """Return a new TemplateRecord with PATCH fields layered over existing."""
            return TemplateRecord(
                id=existing.id,
                scope=existing.scope,
                owner=existing.owner,
                source_name=existing.source_name,
                source_scope=existing.source_scope,
                source_template_id=existing.source_template_id,
                source_url=existing.source_url,
                source_revision=existing.source_revision,
                name=patch.name if patch.name is not None else existing.name,
                description=patch.description if patch.description is not None else existing.description,
                category=patch.category if patch.category is not None else existing.category,
                integrations=patch.integrations if patch.integrations is not None else existing.integrations,
                tags=patch.tags if patch.tags is not None else existing.tags,
                manifest=(
                    patch.manifest.model_dump(exclude_none=True) if patch.manifest is not None else existing.manifest
                ),
                installed_at=existing.installed_at,
                updated_at=_now_utc(),
            )

        def _build_installed_record(
            *,
            installed_id: str,
            scope: TemplateScope,
            owner: str | None,
            request: InstallTemplateRequest,
            template_id: str,
            entry: CatalogEntry,
            manifest: BankTemplateManifest,
            revision: str,
        ) -> TemplateRecord:
            """Build a TemplateRecord for a POST /install body."""
            now = _now_utc()
            return TemplateRecord(
                id=installed_id,
                scope=scope,
                owner=owner,
                source_name=request.source_name,
                source_scope=request.source_scope,
                source_template_id=template_id,
                source_url=None,
                source_revision=revision,
                name=entry.name,
                description=entry.description,
                category=entry.category,
                integrations=entry.integrations,
                tags=entry.tags,
                manifest=manifest.model_dump(exclude_none=True),
                installed_at=now,
                updated_at=now,
            )

        def _build_refreshed_record(
            existing: TemplateRecord,
            entry: CatalogEntry,
            manifest: BankTemplateManifest,
            new_revision: str,
        ) -> TemplateRecord:
            """Build a TemplateRecord for the /update flow (refresh from source)."""
            return TemplateRecord(
                id=existing.id,
                scope=existing.scope,
                owner=existing.owner,
                source_name=existing.source_name,
                source_scope=existing.source_scope,
                source_template_id=existing.source_template_id,
                source_url=existing.source_url,
                source_revision=new_revision,
                name=entry.name,
                description=entry.description,
                category=entry.category,
                integrations=entry.integrations,
                tags=entry.tags,
                manifest=manifest.model_dump(exclude_none=True),
                installed_at=existing.installed_at,
                updated_at=_now_utc(),
            )

        def _resolve_source_owner(
            source_scope: TemplateScope,
            *,
            installed_scope: TemplateScope,
            user_id: str,
        ) -> str | None:
            """Return the owner to query when resolving a source.

            For a personal install, a personal source belongs to the caller;
            a server source has owner=None. For a server install, the same
            logic still applies — admin can install from either source scope.
            """
            del installed_scope  # currently unused, kept for symmetry
            return user_id if source_scope is TemplateScope.PERSONAL else None

        async def _check_collision_or_409(
            pool,
            *,
            installed_id: str,
            scope: TemplateScope,
            owner: str | None,
        ) -> None:
            existing = await db.get_template(pool, id=installed_id, scope=scope, owner=owner)
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "Template id already installed; pass alias_id to coexist",
                        "existing": _record_to_response(existing).model_dump(mode="json"),
                    },
                )

        async def _do_install(
            *,
            template_id: str,
            request: InstallTemplateRequest,
            scope: TemplateScope,
            owner: str | None,
            user_id: str,
        ) -> TemplateRecord:
            """Shared body for /me/install and /admin/install."""
            pool = await db.get_pool()
            source_owner = _resolve_source_owner(request.source_scope, installed_scope=scope, user_id=user_id)
            entry, manifest, revision = await marketplace.fetch_and_resolve_template(
                source_name=request.source_name,
                source_scope=request.source_scope,
                source_owner=source_owner,
                template_id=template_id,
            )
            installed_id = request.alias_id or template_id
            await _check_collision_or_409(pool, installed_id=installed_id, scope=scope, owner=owner)
            record = _build_installed_record(
                installed_id=installed_id,
                scope=scope,
                owner=owner,
                request=request,
                template_id=template_id,
                entry=entry,
                manifest=manifest,
                revision=revision,
            )
            await db.create_template(pool, record)
            return record

        async def _do_update_from_source(
            *,
            template_id: str,
            scope: TemplateScope,
            owner: str | None,
            user_id: str,
        ) -> UpdateTemplateResponse:
            """Shared body for /me/update and /admin/update."""
            pool = await db.get_pool()
            existing = await db.get_template(pool, id=template_id, scope=scope, owner=owner)
            if existing is None:
                raise HTTPException(status_code=404, detail="template not found")
            if existing.source_name is None:
                raise HTTPException(
                    status_code=400,
                    detail="Template was not installed from a source; use PATCH for hand-edited templates",
                )
            assert existing.source_scope is not None
            source_owner = _resolve_source_owner(existing.source_scope, installed_scope=scope, user_id=user_id)
            entry, manifest, new_revision = await marketplace.fetch_and_resolve_template(
                source_name=existing.source_name,
                source_scope=existing.source_scope,
                source_owner=source_owner,
                template_id=existing.source_template_id or existing.id,
            )
            previous_revision = existing.source_revision
            if new_revision == previous_revision:
                return UpdateTemplateResponse(
                    updated=False,
                    previous_revision=previous_revision,
                    new_revision=new_revision,
                    template=_record_to_response(existing),
                )
            updated = _build_refreshed_record(existing, entry, manifest, new_revision)
            await db.update_template(pool, updated)
            return UpdateTemplateResponse(
                updated=True,
                previous_revision=previous_revision,
                new_revision=new_revision,
                template=_record_to_response(updated),
            )

        async def _do_check_update(
            *,
            template_id: str,
            scope: TemplateScope,
            owner: str | None,
            user_id: str,
        ) -> CheckUpdateResponse:
            """Shared body for /me/check-update and /admin/check-update."""
            pool = await db.get_pool()
            existing = await db.get_template(pool, id=template_id, scope=scope, owner=owner)
            if existing is None:
                raise HTTPException(status_code=404, detail="template not found")
            if existing.source_name is None:
                return CheckUpdateResponse(
                    has_update=False,
                    current_revision=None,
                    latest_revision=None,
                    source_name=None,
                    source_scope=None,
                )
            assert existing.source_scope is not None
            source_owner = _resolve_source_owner(existing.source_scope, installed_scope=scope, user_id=user_id)
            _, _, new_revision = await marketplace.fetch_and_resolve_template(
                source_name=existing.source_name,
                source_scope=existing.source_scope,
                source_owner=source_owner,
                template_id=existing.source_template_id or existing.id,
            )
            return CheckUpdateResponse(
                has_update=new_revision != existing.source_revision,
                current_revision=existing.source_revision,
                latest_revision=new_revision,
                source_name=existing.source_name,
                source_scope=existing.source_scope,
            )

        # /me/templates --------------------------------------------------- #

        @router.get(
            "/me/templates",
            response_model=ListTemplatesResponse,
            operation_id="list_my_templates",
            summary="List installed personal templates",
            tags=["Templates"],
        )
        async def list_me_templates(
            category: str | None = None,
            tag: str | None = None,
            _auth=Depends(_require_iam("template:list")),
        ):
            pool = await db.get_pool()
            records = await db.list_templates(
                pool,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
                category=category,
                tag=tag,
            )
            return ListTemplatesResponse(templates=[_record_to_response(r) for r in records])

        @router.post(
            "/me/templates",
            response_model=TemplateResponse,
            operation_id="create_my_template",
            summary="Create a hand-authored personal template",
            tags=["Templates"],
        )
        async def create_me_template(
            request: CreateTemplateRequest,
            _auth=Depends(_require_iam("template:create")),
        ):
            _validate_manifest_or_422(request.manifest)
            record = _build_hand_authored_record(request, scope=TemplateScope.PERSONAL, owner=_auth["user_id"])
            await db.create_template(await db.get_pool(), record)
            return _record_to_response(record)

        @router.get(
            "/me/templates/{template_id}",
            response_model=TemplateResponse,
            operation_id="get_my_template",
            summary="Get an installed personal template",
            tags=["Templates"],
        )
        async def get_me_template(
            template_id: str,
            _auth=Depends(_require_iam("template:list")),
        ):
            record = await db.get_template(
                await db.get_pool(),
                id=template_id,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
            )
            if record is None:
                raise HTTPException(status_code=404, detail="template not found")
            return _record_to_response(record)

        @router.patch(
            "/me/templates/{template_id}",
            response_model=TemplateResponse,
            operation_id="patch_my_template",
            summary="Update a hand-authored personal template",
            tags=["Templates"],
        )
        async def patch_me_template(
            template_id: str,
            request: PatchTemplateRequest,
            _auth=Depends(_require_iam("template:manage")),
        ):
            pool = await db.get_pool()
            existing = await db.get_template(pool, id=template_id, scope=TemplateScope.PERSONAL, owner=_auth["user_id"])
            if existing is None:
                raise HTTPException(status_code=404, detail="template not found")
            if request.manifest is not None:
                _validate_manifest_or_422(request.manifest)
            updated = _apply_patch(existing, request)
            await db.update_template(pool, updated)
            return _record_to_response(updated)

        @router.delete(
            "/me/templates/{template_id}",
            status_code=204,
            operation_id="delete_my_template",
            summary="Delete an installed personal template",
            tags=["Templates"],
        )
        async def delete_me_template(
            template_id: str,
            _auth=Depends(_require_iam("template:manage")),
        ):
            deleted = await db.delete_template(
                await db.get_pool(),
                id=template_id,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
            )
            if not deleted:
                raise HTTPException(status_code=404, detail="template not found")

        @router.post(
            "/me/templates/{template_id}/install",
            response_model=TemplateResponse,
            operation_id="install_my_template",
            summary="Install a marketplace template into the personal scope",
            tags=["Templates"],
        )
        async def install_me_template(
            template_id: str,
            request: InstallTemplateRequest,
            _auth=Depends(_require_iam("template:install")),
        ):
            record = await _do_install(
                template_id=template_id,
                request=request,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
                user_id=_auth["user_id"],
            )
            return _record_to_response(record)

        @router.post(
            "/me/templates/{template_id}/update",
            response_model=UpdateTemplateResponse,
            operation_id="update_my_template_from_source",
            summary="Re-fetch an installed personal template from its source",
            tags=["Templates"],
        )
        async def update_me_template_from_source(
            template_id: str,
            _auth=Depends(_require_iam("template:install")),
        ):
            return await _do_update_from_source(
                template_id=template_id,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
                user_id=_auth["user_id"],
            )

        @router.get(
            "/me/templates/{template_id}/check-update",
            response_model=CheckUpdateResponse,
            operation_id="check_my_template_update",
            summary="Check whether the source has a newer revision",
            tags=["Templates"],
        )
        async def check_me_template_update(
            template_id: str,
            _auth=Depends(_require_iam("template:list")),
        ):
            return await _do_check_update(
                template_id=template_id,
                scope=TemplateScope.PERSONAL,
                owner=_auth["user_id"],
                user_id=_auth["user_id"],
            )

        # /admin/templates ------------------------------------------------ #
        # Server-scope mirror of /me/templates. Identical bodies aside from
        # scope=SERVER, owner=None, and the IAM gate at template:admin.

        @router.get(
            "/admin/templates",
            response_model=ListTemplatesResponse,
            operation_id="list_admin_templates",
            summary="List installed server-scope templates",
            tags=["Templates", "Admin"],
        )
        async def list_admin_templates(
            category: str | None = None,
            tag: str | None = None,
            _auth=Depends(_require_iam("template:admin")),
        ):
            records = await db.list_templates(
                await db.get_pool(),
                scope=TemplateScope.SERVER,
                owner=None,
                category=category,
                tag=tag,
            )
            return ListTemplatesResponse(templates=[_record_to_response(r) for r in records])

        @router.post(
            "/admin/templates",
            response_model=TemplateResponse,
            operation_id="create_admin_template",
            summary="Create a hand-authored server-scope template",
            tags=["Templates", "Admin"],
        )
        async def create_admin_template(
            request: CreateTemplateRequest,
            _auth=Depends(_require_iam("template:admin")),
        ):
            _validate_manifest_or_422(request.manifest)
            record = _build_hand_authored_record(request, scope=TemplateScope.SERVER, owner=None)
            await db.create_template(await db.get_pool(), record)
            return _record_to_response(record)

        @router.get(
            "/admin/templates/{template_id}",
            response_model=TemplateResponse,
            operation_id="get_admin_template",
            summary="Get an installed server-scope template",
            tags=["Templates", "Admin"],
        )
        async def get_admin_template(
            template_id: str,
            _auth=Depends(_require_iam("template:admin")),
        ):
            record = await db.get_template(
                await db.get_pool(),
                id=template_id,
                scope=TemplateScope.SERVER,
                owner=None,
            )
            if record is None:
                raise HTTPException(status_code=404, detail="template not found")
            return _record_to_response(record)

        @router.patch(
            "/admin/templates/{template_id}",
            response_model=TemplateResponse,
            operation_id="patch_admin_template",
            summary="Update a hand-authored server-scope template",
            tags=["Templates", "Admin"],
        )
        async def patch_admin_template(
            template_id: str,
            request: PatchTemplateRequest,
            _auth=Depends(_require_iam("template:admin")),
        ):
            pool = await db.get_pool()
            existing = await db.get_template(pool, id=template_id, scope=TemplateScope.SERVER, owner=None)
            if existing is None:
                raise HTTPException(status_code=404, detail="template not found")
            if request.manifest is not None:
                _validate_manifest_or_422(request.manifest)
            updated = _apply_patch(existing, request)
            await db.update_template(pool, updated)
            return _record_to_response(updated)

        @router.delete(
            "/admin/templates/{template_id}",
            status_code=204,
            operation_id="delete_admin_template",
            summary="Delete an installed server-scope template",
            tags=["Templates", "Admin"],
        )
        async def delete_admin_template(
            template_id: str,
            _auth=Depends(_require_iam("template:admin")),
        ):
            deleted = await db.delete_template(
                await db.get_pool(),
                id=template_id,
                scope=TemplateScope.SERVER,
                owner=None,
            )
            if not deleted:
                raise HTTPException(status_code=404, detail="template not found")

        @router.post(
            "/admin/templates/{template_id}/install",
            response_model=TemplateResponse,
            operation_id="install_admin_template",
            summary="Install a marketplace template into the server scope",
            tags=["Templates", "Admin"],
        )
        async def install_admin_template(
            template_id: str,
            request: InstallTemplateRequest,
            _auth=Depends(_require_iam("template:admin")),
        ):
            record = await _do_install(
                template_id=template_id,
                request=request,
                scope=TemplateScope.SERVER,
                owner=None,
                user_id=_auth["user_id"],
            )
            return _record_to_response(record)

        @router.post(
            "/admin/templates/{template_id}/update",
            response_model=UpdateTemplateResponse,
            operation_id="update_admin_template_from_source",
            summary="Re-fetch an installed server-scope template from its source",
            tags=["Templates", "Admin"],
        )
        async def update_admin_template_from_source(
            template_id: str,
            _auth=Depends(_require_iam("template:admin")),
        ):
            return await _do_update_from_source(
                template_id=template_id,
                scope=TemplateScope.SERVER,
                owner=None,
                user_id=_auth["user_id"],
            )

        @router.get(
            "/admin/templates/{template_id}/check-update",
            response_model=CheckUpdateResponse,
            operation_id="check_admin_template_update",
            summary="Check whether the source has a newer revision",
            tags=["Templates", "Admin"],
        )
        async def check_admin_template_update(
            template_id: str,
            _auth=Depends(_require_iam("template:admin")),
        ):
            return await _do_check_update(
                template_id=template_id,
                scope=TemplateScope.SERVER,
                owner=None,
                user_id=_auth["user_id"],
            )

        # POST /banks ----------------------------------------------------- #

        @router.post(
            "/banks",
            operation_id="create_bank_from_template",
            summary="Apply an installed template to a new or existing bank",
            tags=["Banks"],
        )
        async def create_bank_from_template(
            request: CreateBankFromTemplateRequest,
            _auth=Depends(_require_iam("bank:create")),
        ):
            await _require_action(_auth["user_id"], "template:list")
            record = await db.fetch_installed_template_for_apply(
                await db.get_pool(),
                template=request.template,
                current_user=_auth["user_id"],
            )
            if record is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"template not found for ref {request.template!r}",
                )
            ctx = RequestContext(internal=True)  # type: ignore[call-arg]
            return await bootstrap_bank_from_template(
                memory,
                bank_id=request.bank_id,
                template=record,
                request_context=ctx,
                bank_name=request.name,
            )

        return router

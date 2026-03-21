"""Pydantic request models for HindclawHttp API endpoints."""

from pydantic import BaseModel


# --- Users ---

class CreateUserRequest(BaseModel):
    id: str
    display_name: str
    email: str | None = None


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None


# --- Channels ---

class AddChannelRequest(BaseModel):
    provider: str
    sender_id: str


# --- Groups ---

class CreateGroupRequest(BaseModel):
    id: str
    display_name: str
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


class UpdateGroupRequest(BaseModel):
    display_name: str | None = None
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


# --- Group Members ---

class AddMemberRequest(BaseModel):
    user_id: str


# --- Bank Permissions ---

class BankPermissionRequest(BaseModel):
    recall: bool | None = None
    retain: bool | None = None
    retain_roles: list[str] | None = None
    retain_tags: list[str] | None = None
    retain_every_n_turns: int | None = None
    recall_budget: str | None = None
    recall_max_tokens: int | None = None
    recall_tag_groups: list[dict] | None = None
    llm_model: str | None = None
    llm_provider: str | None = None
    exclude_providers: list[str] | None = None
    retain_strategy: str | None = None


# --- Strategy Scopes ---

class StrategyRequest(BaseModel):
    strategy: str


# --- API Keys ---

class CreateApiKeyRequest(BaseModel):
    description: str | None = None

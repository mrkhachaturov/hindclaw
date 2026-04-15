"""HTTP route tests for the post-Plan-B template surface.

Covers the 16 routes added in the upstream-convergence refactor:
- /me/templates GET, POST, GET/{id}, PATCH/{id}, DELETE/{id},
  POST/{id}/install, POST/{id}/update, GET/{id}/check-update
- /admin/templates mirror (8 routes, gated on template:admin)
- POST /banks (create-or-apply via BankCreationResponse wrapper)

These tests pin the Plan-B-fix invariants the convergence design requires:
- ``source_owner`` is persisted on the row at install time and used
  at /update / /check-update — NOT recomputed from the current caller
  (Plan B finding #1).
- ``create_template`` raises 409 on natural-key collision and
  ``_check_collision_or_409`` runs BEFORE the network round-trip
  (findings #2 + #8).
- ``bank_bootstrap`` only sets ``name`` when the caller supplied one
  and never touches ``mission`` directly (finding #3).
- PATCH with ``{"description": null}`` clears the field; omitting the
  key leaves it untouched (finding #5).
- POST /banks returns ``BankCreationResponse`` with the right
  ``bank_created`` flag (finding #6).
- ``force=true`` on /update bypasses the revision-unchanged early
  return (finding #6 spec line 924).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hindsight_api.extensions import AuthenticationError

from hindclaw_ext.http import HindclawHttp
from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.policy_engine import AccessResult
from hindclaw_ext.template_models import CatalogEntry, TemplateScope

# --- Fixtures ---------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("HINDCLAW_JWT_SECRET", "test-secret-for-templates!!")


def _make_app(user_id: str) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=401, content={"detail": str(exc)})

    ext = HindclawHttp({})
    memory = AsyncMock()
    memory.list_banks = AsyncMock(return_value=[])

    # Two patches:
    #   1) require_admin_for_action — short-circuits the FastAPI dependency
    #      _require_iam closure so route entry-point auth always passes.
    #   2) _evaluate_iam_access — short-circuits the inline _require_action
    #      call inside POST /banks (and any other route that does a second
    #      IAM check after entering the handler body).
    with (
        patch(
            "hindclaw_ext.http.require_admin_for_action",
            new_callable=AsyncMock,
            return_value={"principal_type": "user", "user_id": user_id},
        ),
        patch(
            "hindclaw_ext.http._evaluate_iam_access",
            new_callable=AsyncMock,
            return_value=AccessResult(allowed=True),
        ),
    ):
        router = ext.get_router(memory)
        app.include_router(router, prefix="/ext")
        # Stash memory so individual tests can introspect/override it.
        app.state._memory = memory
        yield app


@pytest.fixture
def alice_app():
    yield from _make_app("alice")


@pytest.fixture
def bob_app():
    yield from _make_app("bob")


@pytest.fixture
def alice_client(alice_app):
    return TestClient(alice_app)


@pytest.fixture
def bob_client(bob_app):
    return TestClient(bob_app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer fake-token"}


@pytest.fixture
def mock_db():
    with patch("hindclaw_ext.http.db") as mock:
        mock.get_pool = AsyncMock(return_value=AsyncMock())
        yield mock


@pytest.fixture
def mock_marketplace():
    with patch("hindclaw_ext.http.marketplace") as mock:
        yield mock


# --- Helpers ----------------------------------------------------------- #


_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def _valid_manifest_dict() -> dict:
    return {
        "version": "1",
        "bank": {
            "reflect_mission": "Be helpful",
            "retain_mission": "Capture insights",
            "retain_extraction_mode": "verbose",
        },
        "directives": [
            {"name": "be-precise", "content": "Cite sources.", "priority": 5, "is_active": True},
        ],
        "mental_models": [
            {
                "id": "team-norms",
                "name": "Team norms",
                "source_query": "team norms",
                "max_tokens": 2000,
            }
        ],
    }


def _record(
    *,
    id: str = "backend-python",
    scope: TemplateScope = TemplateScope.PERSONAL,
    owner: str | None = "alice",
    source_name: str | None = "hub",
    source_scope: TemplateScope | None = TemplateScope.SERVER,
    source_owner: str | None = None,
    source_template_id: str | None = "backend-python",
    source_revision: str | None = "etag-1",
) -> TemplateRecord:
    return TemplateRecord(
        id=id,
        scope=scope,
        owner=owner,
        source_name=source_name,
        source_scope=source_scope,
        source_owner=source_owner,
        source_template_id=source_template_id,
        source_url=None,
        source_revision=source_revision,
        name=f"{id} display",
        description="d",
        category="coding",
        integrations=["claude-code"],
        tags=["python"],
        manifest=_valid_manifest_dict(),
        installed_at=_NOW,
        updated_at=_NOW,
    )


def _catalog_entry(template_id: str = "backend-python") -> CatalogEntry:
    return CatalogEntry(
        id=template_id,
        name=f"{template_id} display",
        description="d",
        category="coding",
        integrations=["claude-code"],
        tags=["python"],
        manifest_file=f"templates/{template_id}.json",
    )


def _import_response_dict() -> dict:
    return {
        "bank_id": "yoda",
        "config_applied": True,
        "mental_models_created": ["team-norms"],
        "directives_created": ["be-precise"],
        "mental_models_updated": [],
        "directives_updated": [],
        "operation_ids": ["op-1"],
        "errors": [],
        "dry_run": False,
    }


# --- /me/templates LIST + GET ----------------------------------------- #


def test_list_my_templates_returns_personal_scope_only(alice_client, headers, mock_db):
    mock_db.list_templates = AsyncMock(return_value=[_record()])
    resp = alice_client.get("/ext/hindclaw/me/templates", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["templates"]) == 1
    assert body["templates"][0]["id"] == "backend-python"
    assert body["templates"][0]["scope"] == "personal"
    assert body["templates"][0]["owner"] == "alice"
    # Filter by scope+owner=alice — never leak admin or bob's templates.
    call_kwargs = mock_db.list_templates.call_args.kwargs
    assert call_kwargs["scope"] is TemplateScope.PERSONAL
    assert call_kwargs["owner"] == "alice"


def test_get_my_template_owned(alice_client, headers, mock_db):
    mock_db.get_template = AsyncMock(return_value=_record())
    resp = alice_client.get("/ext/hindclaw/me/templates/backend-python", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == "backend-python"


def test_get_my_template_not_found(alice_client, headers, mock_db):
    mock_db.get_template = AsyncMock(return_value=None)
    resp = alice_client.get("/ext/hindclaw/me/templates/nope", headers=headers)
    assert resp.status_code == 404


# --- /me/templates POST (hand-authored) ------------------------------- #


def test_create_my_hand_authored_template(alice_client, headers, mock_db):
    mock_db.create_template = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/templates",
        json={
            "id": "my-tmpl",
            "name": "My Template",
            "description": "Hand-authored",
            "manifest": _valid_manifest_dict(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "my-tmpl"
    assert body["scope"] == "personal"
    assert body["owner"] == "alice"
    # Hand-authored templates have NO source attribution at all.
    assert body["source_name"] is None
    assert body["source_owner"] is None
    mock_db.create_template.assert_awaited_once()


def test_create_my_template_invalid_manifest_returns_422(alice_client, headers, mock_db):
    """A manifest that fails upstream's semantic validate_bank_template returns 422."""
    bad = _valid_manifest_dict()
    # Two mental models with the same id — upstream's validate_bank_template rejects.
    bad["mental_models"] = [
        {"id": "x", "name": "X", "source_query": "q", "max_tokens": 100},
        {"id": "x", "name": "Y", "source_query": "q", "max_tokens": 100},
    ]
    mock_db.create_template = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/templates",
        json={"id": "my-tmpl", "name": "My", "manifest": bad},
        headers=headers,
    )
    assert resp.status_code == 422
    mock_db.create_template.assert_not_called()


def test_create_my_template_collision_propagates_unique_violation(alice_client, headers, mock_db):
    """The hand-authored POST /me/templates path does NOT catch
    UniqueViolationError — only the install path documents 409 in the
    convergence spec. We assert the raw exception escapes (rather than
    being silently upserted) so a future maintainer can wire a 409 here
    too if the contract is extended."""
    mock_db.create_template = AsyncMock(
        side_effect=asyncpg.UniqueViolationError("duplicate key value violates unique constraint")
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        alice_client.post(
            "/ext/hindclaw/me/templates",
            json={"id": "x", "name": "X", "manifest": _valid_manifest_dict()},
            headers=headers,
        )


# --- /me/templates PATCH (Plan B finding #5) -------------------------- #


def test_patch_my_template_updates_fields(alice_client, headers, mock_db):
    mock_db.get_template = AsyncMock(return_value=_record())
    mock_db.update_template = AsyncMock()
    resp = alice_client.patch(
        "/ext/hindclaw/me/templates/backend-python",
        json={"description": "new description", "category": "infra"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new description"
    assert resp.json()["category"] == "infra"
    mock_db.update_template.assert_awaited_once()


def test_patch_my_template_clears_description_with_explicit_null(alice_client, headers, mock_db):
    """Plan B finding #5: PATCH {"description": null} must actually clear."""
    mock_db.get_template = AsyncMock(return_value=_record())
    mock_db.update_template = AsyncMock()
    resp = alice_client.patch(
        "/ext/hindclaw/me/templates/backend-python",
        json={"description": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] is None
    written = mock_db.update_template.call_args.args[1]
    assert written.description is None


def test_patch_my_template_omitted_field_left_untouched(alice_client, headers, mock_db):
    """Plan B finding #5 counterpart: omitting a key must NOT clear it."""
    mock_db.get_template = AsyncMock(return_value=_record())
    mock_db.update_template = AsyncMock()
    resp = alice_client.patch(
        "/ext/hindclaw/me/templates/backend-python",
        json={"category": "infra"},  # description omitted, must remain "d"
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "d"
    written = mock_db.update_template.call_args.args[1]
    assert written.description == "d"
    assert written.category == "infra"


def test_patch_my_template_not_found(alice_client, headers, mock_db):
    mock_db.get_template = AsyncMock(return_value=None)
    resp = alice_client.patch(
        "/ext/hindclaw/me/templates/nope",
        json={"description": "x"},
        headers=headers,
    )
    assert resp.status_code == 404


# --- /me/templates DELETE --------------------------------------------- #


def test_delete_my_template(alice_client, headers, mock_db):
    mock_db.delete_template = AsyncMock(return_value=True)
    resp = alice_client.delete("/ext/hindclaw/me/templates/backend-python", headers=headers)
    assert resp.status_code == 204


def test_delete_my_template_not_found(alice_client, headers, mock_db):
    mock_db.delete_template = AsyncMock(return_value=False)
    resp = alice_client.delete("/ext/hindclaw/me/templates/nope", headers=headers)
    assert resp.status_code == 404


# --- /me/templates/{id}/install (findings #1, #2, #8) ----------------- #


def test_install_my_template_persists_source_owner_for_personal_source(
    alice_client, headers, mock_db, mock_marketplace
):
    """Plan B finding #1: installing from a PERSONAL source persists the
    caller's user_id on the row so a later /update from a different admin
    still resolves the original source — instead of conflating with the
    current caller's identity at refresh time."""
    mock_db.get_template = AsyncMock(return_value=None)  # no collision
    mock_db.create_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-rev-1"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/install",
        json={"source_name": "my-private-hub", "source_scope": "personal"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_owner"] == "alice"
    written = mock_db.create_template.call_args.args[1]
    assert written.source_owner == "alice"
    assert written.source_scope is TemplateScope.PERSONAL
    # The marketplace fetch is invoked with the caller-derived owner at install.
    fetch_kwargs = mock_marketplace.fetch_and_resolve_template.call_args.kwargs
    assert fetch_kwargs["source_owner"] == "alice"


def test_install_my_template_persists_source_owner_none_for_server_source(
    alice_client, headers, mock_db, mock_marketplace
):
    mock_db.get_template = AsyncMock(return_value=None)
    mock_db.create_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-rev-1"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/install",
        json={"source_name": "hub", "source_scope": "server"},
        headers=headers,
    )
    assert resp.status_code == 200
    written = mock_db.create_template.call_args.args[1]
    assert written.source_owner is None
    assert written.source_scope is TemplateScope.SERVER


def test_install_my_template_collision_returns_409_before_network_fetch(
    alice_client, headers, mock_db, mock_marketplace
):
    """Plan B finding #8: collision pre-check runs BEFORE the marketplace fetch."""
    mock_db.get_template = AsyncMock(return_value=_record())
    mock_db.create_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/install",
        json={"source_name": "hub", "source_scope": "server"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "alias_id" in resp.json()["detail"]["error"]
    mock_marketplace.fetch_and_resolve_template.assert_not_called()
    mock_db.create_template.assert_not_called()


def test_install_my_template_with_alias_id_creates_under_alias(alice_client, headers, mock_db, mock_marketplace):
    mock_db.get_template = AsyncMock(return_value=None)
    mock_db.create_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-rev-1"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/install",
        json={
            "source_name": "hub",
            "source_scope": "server",
            "alias_id": "my-fork",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "my-fork"
    # source_template_id remembers the original id for future refreshes.
    written = mock_db.create_template.call_args.args[1]
    assert written.id == "my-fork"
    assert written.source_template_id == "backend-python"


def test_install_my_template_unique_violation_race_returns_409(alice_client, headers, mock_db, mock_marketplace):
    """Defense-in-depth: if a parallel install slips past the pre-check,
    the INSERT raises UniqueViolationError and the route still surfaces 409."""
    # First call (pre-check) returns None, second (race recovery) returns existing.
    mock_db.get_template = AsyncMock(side_effect=[None, _record()])

    async def _raise(*args, **kwargs):
        raise asyncpg.UniqueViolationError("collision")

    mock_db.create_template = AsyncMock(side_effect=_raise)
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-rev-1"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/install",
        json={"source_name": "hub", "source_scope": "server"},
        headers=headers,
    )
    assert resp.status_code == 409


# --- /me/templates/{id}/update (findings #1 + #6) --------------------- #


def test_update_my_template_uses_persisted_source_owner_not_caller(bob_client, headers, mock_db, mock_marketplace):
    """Plan B finding #1: when bob refreshes a template that alice
    originally installed from her personal source, the marketplace lookup
    must use ``alice`` (the persisted source_owner), NOT bob.

    The personal-template row itself is owned by bob in this test (so the
    natural-key lookup succeeds for bob); only ``source_owner`` differs.
    """
    persisted = _record(
        owner="bob",
        source_scope=TemplateScope.PERSONAL,
        source_owner="alice",  # alice is the source-side owner
    )
    mock_db.get_template = AsyncMock(return_value=persisted)
    mock_db.update_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-new"))
    resp = bob_client.post(
        "/ext/hindclaw/me/templates/backend-python/update",
        headers=headers,
    )
    assert resp.status_code == 200
    fetch_kwargs = mock_marketplace.fetch_and_resolve_template.call_args.kwargs
    assert fetch_kwargs["source_owner"] == "alice"  # NOT "bob"
    assert fetch_kwargs["source_scope"] is TemplateScope.PERSONAL


def test_update_my_template_no_op_when_revision_unchanged(alice_client, headers, mock_db, mock_marketplace):
    persisted = _record(source_revision="etag-same")
    mock_db.get_template = AsyncMock(return_value=persisted)
    mock_db.update_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-same"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/update",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is False
    mock_db.update_template.assert_not_called()


def test_update_my_template_force_re_fetches_when_revision_unchanged(alice_client, headers, mock_db, mock_marketplace):
    """Plan B finding #6: ?force=true bypasses the no-op early return."""
    persisted = _record(source_revision="etag-same")
    mock_db.get_template = AsyncMock(return_value=persisted)
    mock_db.update_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-same"))
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/update?force=true",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is True
    mock_db.update_template.assert_awaited_once()


def test_update_my_template_hand_authored_returns_400(alice_client, headers, mock_db):
    persisted = _record(source_name=None, source_scope=None, source_revision=None)
    mock_db.get_template = AsyncMock(return_value=persisted)
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/backend-python/update",
        headers=headers,
    )
    assert resp.status_code == 400


def test_update_my_template_not_found(alice_client, headers, mock_db):
    mock_db.get_template = AsyncMock(return_value=None)
    resp = alice_client.post(
        "/ext/hindclaw/me/templates/nope/update",
        headers=headers,
    )
    assert resp.status_code == 404


# --- /me/templates/{id}/check-update (finding #1) --------------------- #


def test_check_update_my_template_uses_persisted_source_owner(bob_client, headers, mock_db, mock_marketplace):
    """Plan B finding #1 mirror: check-update also reads source_owner
    from the row, not from the current caller."""
    persisted = _record(
        owner="bob",
        source_scope=TemplateScope.PERSONAL,
        source_owner="alice",
    )
    mock_db.get_template = AsyncMock(return_value=persisted)
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-new"))
    resp = bob_client.get(
        "/ext/hindclaw/me/templates/backend-python/check-update",
        headers=headers,
    )
    assert resp.status_code == 200
    fetch_kwargs = mock_marketplace.fetch_and_resolve_template.call_args.kwargs
    assert fetch_kwargs["source_owner"] == "alice"


def test_check_update_my_template_hand_authored_returns_no_update(alice_client, headers, mock_db):
    persisted = _record(source_name=None, source_scope=None, source_revision=None)
    mock_db.get_template = AsyncMock(return_value=persisted)
    resp = alice_client.get(
        "/ext/hindclaw/me/templates/backend-python/check-update",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["has_update"] is False


# --- /admin/templates mirror ------------------------------------------ #


def test_list_admin_templates_returns_server_scope(alice_client, headers, mock_db):
    mock_db.list_templates = AsyncMock(return_value=[_record(scope=TemplateScope.SERVER, owner=None)])
    resp = alice_client.get("/ext/hindclaw/admin/templates", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["templates"][0]["scope"] == "server"
    assert body["templates"][0]["owner"] is None
    call_kwargs = mock_db.list_templates.call_args.kwargs
    assert call_kwargs["scope"] is TemplateScope.SERVER
    assert call_kwargs["owner"] is None


def test_create_admin_template_persists_with_owner_none(alice_client, headers, mock_db):
    mock_db.create_template = AsyncMock()
    resp = alice_client.post(
        "/ext/hindclaw/admin/templates",
        json={"id": "server-tmpl", "name": "Server", "manifest": _valid_manifest_dict()},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "server"
    assert body["owner"] is None
    written = mock_db.create_template.call_args.args[1]
    assert written.scope is TemplateScope.SERVER
    assert written.owner is None


def test_admin_install_persists_caller_as_source_owner_for_personal_source(
    alice_client, headers, mock_db, mock_marketplace
):
    """Even on the admin path, source_owner reflects WHERE the source
    lives (caller's personal namespace), not WHO the installed-template
    row belongs to (server scope, owner=None)."""
    mock_db.get_template = AsyncMock(return_value=None)
    mock_db.create_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-1"))
    resp = alice_client.post(
        "/ext/hindclaw/admin/templates/backend-python/install",
        json={"source_name": "my-hub", "source_scope": "personal"},
        headers=headers,
    )
    assert resp.status_code == 200
    written = mock_db.create_template.call_args.args[1]
    assert written.scope is TemplateScope.SERVER  # installed-row scope
    assert written.owner is None
    assert written.source_owner == "alice"  # source-side owner
    assert written.source_scope is TemplateScope.PERSONAL


def test_admin_update_uses_existing_source_owner_from_row(bob_client, headers, mock_db, mock_marketplace):
    """The admin /update path also reads source_owner from the row."""
    persisted = _record(
        scope=TemplateScope.SERVER,
        owner=None,
        source_scope=TemplateScope.PERSONAL,
        source_owner="alice",
    )
    mock_db.get_template = AsyncMock(return_value=persisted)
    mock_db.update_template = AsyncMock()
    mock_marketplace.fetch_and_resolve_template = AsyncMock(return_value=(_catalog_entry(), __manifest(), "etag-new"))
    resp = bob_client.post(
        "/ext/hindclaw/admin/templates/backend-python/update",
        headers=headers,
    )
    assert resp.status_code == 200
    fetch_kwargs = mock_marketplace.fetch_and_resolve_template.call_args.kwargs
    assert fetch_kwargs["source_owner"] == "alice"


# --- POST /banks (findings #3 + #6) ----------------------------------- #


def test_create_bank_from_template_returns_bank_created_true_for_new_bank(alice_app, alice_client, headers, mock_db):
    """Plan B finding #6: POST /banks returns BankCreationResponse with
    bank_created=True when the bank did NOT pre-exist."""
    mock_db.fetch_installed_template_for_apply = AsyncMock(
        return_value=_record(scope=TemplateScope.PERSONAL, owner="alice")
    )
    memory = alice_app.state._memory
    memory.list_banks = AsyncMock(return_value=[])  # no pre-existing
    memory.get_bank_profile = AsyncMock(return_value={"bank_id": "yoda"})
    memory.update_bank = AsyncMock()
    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=_import_response_dict()),
    ):
        resp = alice_client.post(
            "/ext/hindclaw/banks",
            json={"bank_id": "yoda", "template": "personal/backend-python"},
            headers=headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bank_id"] == "yoda"
    assert body["template"] == "personal/backend-python"
    assert body["bank_created"] is True


def test_create_bank_from_template_returns_bank_created_false_for_existing_bank(
    alice_app, alice_client, headers, mock_db
):
    mock_db.fetch_installed_template_for_apply = AsyncMock(
        return_value=_record(scope=TemplateScope.PERSONAL, owner="alice")
    )
    memory = alice_app.state._memory
    memory.list_banks = AsyncMock(return_value=[{"bank_id": "yoda", "name": "yoda"}])
    memory.get_bank_profile = AsyncMock(return_value={"bank_id": "yoda"})
    memory.update_bank = AsyncMock()
    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=_import_response_dict()),
    ):
        resp = alice_client.post(
            "/ext/hindclaw/banks",
            json={"bank_id": "yoda", "template": "personal/backend-python"},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["bank_created"] is False


def test_create_bank_from_template_no_name_does_not_call_update_bank(alice_app, alice_client, headers, mock_db):
    """Plan B finding #3: omitting `name` must NOT clobber an existing
    bank's user-set display name with a derived default."""
    mock_db.fetch_installed_template_for_apply = AsyncMock(
        return_value=_record(scope=TemplateScope.PERSONAL, owner="alice")
    )
    memory = alice_app.state._memory
    memory.list_banks = AsyncMock(return_value=[{"bank_id": "yoda", "name": "Yoda"}])
    memory.get_bank_profile = AsyncMock(return_value={"bank_id": "yoda"})
    memory.update_bank = AsyncMock()
    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=_import_response_dict()),
    ):
        resp = alice_client.post(
            "/ext/hindclaw/banks",
            json={"bank_id": "yoda", "template": "personal/backend-python"},
            headers=headers,
        )
    assert resp.status_code == 200
    memory.update_bank.assert_not_called()


def test_create_bank_from_template_with_explicit_name_calls_update_bank(alice_app, alice_client, headers, mock_db):
    mock_db.fetch_installed_template_for_apply = AsyncMock(
        return_value=_record(scope=TemplateScope.PERSONAL, owner="alice")
    )
    memory = alice_app.state._memory
    memory.list_banks = AsyncMock(return_value=[])
    memory.get_bank_profile = AsyncMock(return_value={"bank_id": "yoda"})
    memory.update_bank = AsyncMock()
    with patch(
        "hindclaw_ext.bank_bootstrap.apply_bank_template_manifest",
        new=AsyncMock(return_value=_import_response_dict()),
    ):
        resp = alice_client.post(
            "/ext/hindclaw/banks",
            json={"bank_id": "yoda", "template": "personal/backend-python", "name": "Yoda Master"},
            headers=headers,
        )
    assert resp.status_code == 200
    memory.update_bank.assert_awaited_once()
    call_kwargs = memory.update_bank.call_args.kwargs
    assert call_kwargs["name"] == "Yoda Master"
    # Mission must NEVER be set directly — apply_bank_template_manifest
    # routes manifest.bank.reflect_mission through the config layer.
    assert "mission" not in call_kwargs


def test_create_bank_from_template_template_not_found_returns_404(alice_client, headers, mock_db):
    mock_db.fetch_installed_template_for_apply = AsyncMock(return_value=None)
    resp = alice_client.post(
        "/ext/hindclaw/banks",
        json={"bank_id": "yoda", "template": "personal/missing"},
        headers=headers,
    )
    assert resp.status_code == 404


# --- helper that needs the real upstream type ------------------------- #


def __manifest():
    """Return a parsed BankTemplateManifest matching ``_valid_manifest_dict``."""
    from hindsight_api.api.http import BankTemplateManifest  # type: ignore[attr-defined]

    return BankTemplateManifest.model_validate(_valid_manifest_dict())

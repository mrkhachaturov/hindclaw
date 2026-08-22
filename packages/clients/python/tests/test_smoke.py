"""End-to-end smoke tests for the HindclawClient wrapper.

These tests drive the wrapper through the generated aiohttp client
against the uvicorn stub server defined in ``conftest.py``. They
exercise the conversion layer in both directions:

* request side — an upstream ``BankTemplateManifest`` is passed into
  the wrapper, normalised via ``model_dump()``, rebuilt as the local
  generated ``CreateTemplateRequest``, and serialised to JSON by the
  aiohttp client. The stub captures the body and the test asserts the
  conversion produced the expected on-wire shape.
* response side — the stub returns a canned ``BankCreationResponse``
  and the wrapper rebuilds its nested ``import_result`` as the
  upstream ``BankTemplateImportResponse`` class, returning a
  wrapper-owned ``CreateBankFromTemplateResult`` dataclass.

Both personal and admin template paths are covered symmetrically to
guard against the tag-split regression Plan B introduced (without
explicit admin coverage the wrapper could route admin calls to the
personal endpoint without any test catching it).
"""
from __future__ import annotations

import hindsight_client_api.models as upstream

import hindclaw_client
from hindclaw_client.client import CreateBankFromTemplateResult


def _upstream_manifest_literal() -> upstream.BankTemplateManifest:
    """Build a minimal upstream manifest instance.

    Uses ``mental_models=[]`` and ``directives=[]`` so the test does
    not have to pick between ``MentalModelTriggerInput`` and
    ``MentalModelTriggerOutput`` on the request side. The ``bank``
    field is omitted entirely — any configurable fields would trigger
    the pre-#1044/post-#1044 drift described in the Plan D spec.
    """
    return upstream.BankTemplateManifest(
        version="1",
        bank=None,
        mental_models=[],
        directives=[],
    )


async def test_create_my_template_roundtrip(stub_server) -> None:
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        response = await client.create_my_template(
            id="tmpl-smoke",
            name="Smoke Template",
            manifest=_upstream_manifest_literal(),
            description="from test",
            category="test",
            integrations=["openclaw"],
            tags=["smoke"],
        )

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "POST"
    assert captured["path"] == "/ext/hindclaw/me/templates"
    assert captured["body"]["id"] == "tmpl-smoke"
    assert captured["body"]["name"] == "Smoke Template"
    assert captured["body"]["description"] == "from test"
    assert captured["body"]["category"] == "test"
    assert captured["body"]["integrations"] == ["openclaw"]
    assert captured["body"]["tags"] == ["smoke"]
    assert captured["body"]["manifest"] == {
        "version": "1",
        "bank": None,
        "mental_models": [],
        "directives": [],
    }

    assert response.id == "tmpl-smoke"
    assert response.name == "Smoke Template"


async def test_patch_my_template_with_manifest(stub_server) -> None:
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        await client.patch_my_template(
            "tmpl-smoke",
            name="Smoke Renamed",
            manifest=_upstream_manifest_literal(),
        )

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/ext/hindclaw/me/templates/tmpl-smoke"
    assert captured["body"]["name"] == "Smoke Renamed"
    assert captured["body"]["manifest"] == {
        "version": "1",
        "bank": None,
        "mental_models": [],
        "directives": [],
    }


async def test_patch_my_template_without_manifest(stub_server) -> None:
    """Calling patch without a manifest must not raise or send one.

    This is the regression guard for the PATCH-clobber bug: the wrapper
    must omit every unset field from the wire payload so the server's
    ``model_dump(exclude_unset=True)`` cannot treat ``None`` as an
    explicit clear. Sending ``manifest: null`` (or any other null field
    the caller did not pass) would overwrite the stored value on the
    server.
    """
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        await client.patch_my_template("tmpl-smoke", name="Just a rename")

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "PATCH"
    assert captured["body"]["name"] == "Just a rename"
    # Unset fields must be ABSENT from the wire payload, not null. The
    # HindClaw PATCH handler uses model_dump(exclude_unset=True), so any
    # field that appears in the wire body — even as null — is treated as
    # an explicit clear and clobbers the stored value.
    assert "manifest" not in captured["body"], (
        f"manifest key must be absent (not null) on PATCH without manifest — "
        f"sending null would clobber the stored manifest on the server "
        f"because the PATCH handler uses exclude_unset=True. Got: {captured['body']}"
    )
    for field in ("description", "category", "integrations", "tags"):
        assert field not in captured["body"], (
            f"{field} must be absent from PATCH body when caller did not pass it — "
            f"sending null would clobber the stored value. Got: {captured['body']}"
        )


async def test_create_admin_template_roundtrip(stub_server) -> None:
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        response = await client.create_admin_template(
            id="tmpl-admin",
            name="Admin Template",
            manifest=_upstream_manifest_literal(),
        )

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "POST"
    assert captured["path"] == "/ext/hindclaw/admin/templates"
    assert captured["body"]["id"] == "tmpl-admin"
    assert captured["body"]["name"] == "Admin Template"
    assert captured["body"]["manifest"]["version"] == "1"

    assert response.id == "tmpl-admin"


async def test_patch_admin_template(stub_server) -> None:
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        await client.patch_admin_template(
            "tmpl-admin",
            name="Admin Renamed",
            manifest=_upstream_manifest_literal(),
        )

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/ext/hindclaw/admin/templates/tmpl-admin"
    assert captured["body"]["name"] == "Admin Renamed"
    assert captured["body"]["manifest"]["version"] == "1"


async def test_create_bank_from_template_returns_wrapper_dataclass(stub_server) -> None:
    base_url, state = stub_server
    async with hindclaw_client.HindclawClient(base_url, api_key="test-token") as client:
        result = await client.create_bank_from_template(
            bank_id="bank-smoke",
            template="tmpl-smoke",
            name="Smoke Bank",
        )

    assert isinstance(result, CreateBankFromTemplateResult)
    assert result.bank_id == "bank-smoke"
    assert result.template == "tmpl-smoke"
    assert result.bank_created is True
    # The key correctness check: import_result must be an instance of
    # the UPSTREAM BankTemplateImportResponse class, not the local
    # hindclaw_client_api copy. Plan D's wrapper explicitly rebuilds
    # this at the public boundary.
    assert isinstance(result.import_result, upstream.BankTemplateImportResponse)
    assert result.import_result.bank_id == "bank-smoke"
    assert result.import_result.config_applied is False

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "POST"
    assert captured["path"] == "/ext/hindclaw/banks"
    assert captured["body"] == {
        "bank_id": "bank-smoke",
        "template": "tmpl-smoke",
        "name": "Smoke Bank",
    }

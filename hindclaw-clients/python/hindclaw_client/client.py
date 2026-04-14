"""Hindclaw Python client — convenience wrapper around generated API client.

Usage:
    from hindclaw_client import HindclawClient

    client = HindclawClient("https://hindsight.home.local", api_key="hc_admin_xxxxx")
    users = await client.list_users()
"""
from dataclasses import dataclass
from typing import Any

import hindclaw_client_api.models as _local_models
import hindsight_client_api.models as _upstream_models
from hindclaw_client_api import ApiClient, Configuration
from hindclaw_client_api.api import BanksApi, DefaultApi, TemplatesApi


def _local_manifest_from_upstream(
    upstream_obj: _upstream_models.BankTemplateManifest,
) -> _local_models.BankTemplateManifest:
    """Rebuild an upstream BankTemplateManifest as the local generated class.

    Called on the REQUEST side. The aiohttp-based generated client only knows
    how to serialize its own local classes; an upstream instance passed in
    would raise at request time. This dumps the upstream instance and
    re-validates through the local class so aiohttp can serialize it.
    """
    return _local_models.BankTemplateManifest.model_validate(
        upstream_obj.model_dump(mode="json", by_alias=True)
    )


def _upstream_import_response_from_local(
    local_obj: _local_models.BankTemplateImportResponse,
) -> _upstream_models.BankTemplateImportResponse:
    """Rebuild a local BankTemplateImportResponse as the upstream class.

    Called on the RESPONSE side for the nested `import_result` field of
    `BankCreationResponse`. Used to build `CreateBankFromTemplateResult`
    from the generated local response.
    """
    return _upstream_models.BankTemplateImportResponse.model_validate(
        local_obj.model_dump(mode="json", by_alias=True)
    )


@dataclass
class CreateBankFromTemplateResult:
    """Wrapper-owned response type for create_bank_from_template.

    Why a dataclass and not the generated BankCreationResponse: openapi-
    generator's Python Pydantic template sets ConfigDict(validate_assignment=True)
    on every generated model. That means any attempt to mutate
    `raw.import_result = <upstream instance>` on the local
    BankCreationResponse would be rejected or coerced back to the local
    class by Pydantic's assignment-validation hook, defeating the
    conversion. The wrapper sidesteps the problem by returning its own
    dataclass whose `import_result` field is typed as the upstream class
    directly. Outer fields (bank_id, template, bank_created) are copied
    verbatim from the generated response.
    """

    bank_id: str
    template: str
    bank_created: bool
    import_result: _upstream_models.BankTemplateImportResponse


class HindclawClient:
    """Convenience wrapper around the generated Hindclaw API client.

    Template-CRUD wrapper methods take individual kwargs (id, name, manifest,
    etc.) rather than pre-built CreateTemplateRequest / PatchTemplateRequest
    instances. This is deliberate: consumers working with HindClaw pass an
    upstream BankTemplateManifest (from hindsight_client_api.models) as the
    manifest kwarg, and the wrapper normalizes it through model_dump() before
    building the local generated request model. If the caller built a local
    CreateTemplateRequest directly with manifest=<upstream instance>, Pydantic
    validate_assignment would either reject the upstream instance or coerce
    it back to the local class at construction time — hiding the conversion
    boundary from tests. Accepting kwargs keeps the conversion explicit.

    Args:
        base_url: Hindsight server URL.
        api_key: Hindclaw API key or JWT token.
    """

    def __init__(self, base_url: str, api_key: str):
        config = Configuration(host=base_url)
        config.api_key["HTTPBearer"] = api_key
        self._client = ApiClient(config)
        # Plan B added OpenAPI tags to the HindClaw HTTP routes, so the
        # generator now splits methods across tagged API classes (DefaultApi
        # for untagged, TemplatesApi for Templates, BanksApi for Banks,
        # AdminApi for Admin). DefaultApi still hosts the untagged surface
        # (users, groups, policies, etc.) and the wrapper keeps `self.api`
        # pointing at it for backwards compatibility with the Task 4 layout.
        self.api = DefaultApi(self._client)
        self._templates_api = TemplatesApi(self._client)
        self._banks_api = BanksApi(self._client)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _coerce_manifest(
        self,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Normalize a manifest kwarg to a dict payload.

        Accepts upstream BankTemplateManifest instances, plain dicts, or None.
        Dumps upstream instances via model_dump(mode="json", by_alias=True) so
        the aiohttp-based generated client can serialize the payload directly.
        """
        if manifest is None:
            return None
        if isinstance(manifest, _upstream_models.BankTemplateManifest):
            return manifest.model_dump(mode="json", by_alias=True)
        return manifest

    async def _do_create_template(
        self,
        *,
        scope: str,
        id: str,
        name: str,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any],
        description: str | None,
        category: str | None,
        integrations: list[str] | None,
        tags: list[str] | None,
    ):
        """Shared create path for personal and admin templates.

        scope is "my" or "admin" and chooses which generated API method the
        request is routed to. The public create_* methods are one-line
        delegations so each stays discoverable in IDE autocompletion while
        the construction logic lives in one place.
        """
        manifest_payload = self._coerce_manifest(manifest)
        request = _local_models.CreateTemplateRequest(
            id=id,
            name=name,
            description=description,
            category=category,
            integrations=integrations or [],
            tags=tags or [],
            manifest=manifest_payload,
        )
        if scope == "my":
            return await self._templates_api.create_my_template(
                create_template_request=request,
            )
        return await self._templates_api.create_admin_template(
            create_template_request=request,
        )

    async def _do_patch_template(
        self,
        template_id: str,
        *,
        scope: str,
        name: str | None,
        description: str | None,
        category: str | None,
        integrations: list[str] | None,
        tags: list[str] | None,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any] | None,
    ):
        """Shared patch path for personal and admin templates.

        Builds a PatchTemplateRequest containing only fields the caller
        explicitly passed. PATCH semantics matter on the server side: the
        handler uses model_dump(exclude_unset=True) to distinguish "field
        not sent" from "field explicitly null", so passing manifest=None
        (or any other field set to None) unconditionally would add the
        field to model_fields_set and clobber the stored value.
        """
        patch_kwargs: dict[str, Any] = {}
        if name is not None:
            patch_kwargs["name"] = name
        if description is not None:
            patch_kwargs["description"] = description
        if category is not None:
            patch_kwargs["category"] = category
        if integrations is not None:
            patch_kwargs["integrations"] = integrations
        if tags is not None:
            patch_kwargs["tags"] = tags
        if manifest is not None:
            patch_kwargs["manifest"] = self._coerce_manifest(manifest)

        patch = _local_models.PatchTemplateRequest(**patch_kwargs)
        if scope == "my":
            return await self._templates_api.patch_my_template(
                template_id=template_id,
                patch_template_request=patch,
            )
        return await self._templates_api.patch_admin_template(
            template_id=template_id,
            patch_template_request=patch,
        )

    async def create_my_template(
        self,
        *,
        id: str,
        name: str,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any],
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
    ):
        """Create a personal template.

        The manifest kwarg accepts either an upstream BankTemplateManifest
        instance or a dict in that shape. Upstream instances are normalized
        via model_dump() before the local generated request model is built.
        """
        return await self._do_create_template(
            scope="my",
            id=id,
            name=name,
            manifest=manifest,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
        )

    async def patch_my_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any] | None = None,
    ):
        """Partial update of a personal template. Every kwarg is optional;
        only provided fields are sent to the server.
        """
        return await self._do_patch_template(
            template_id,
            scope="my",
            name=name,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
            manifest=manifest,
        )

    async def create_admin_template(
        self,
        *,
        id: str,
        name: str,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any],
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
    ):
        """Create an admin (server-scope) template.

        Same conversion rule as create_my_template. Admin templates are
        server-visible to all users; personal templates are scoped to the
        caller.
        """
        return await self._do_create_template(
            scope="admin",
            id=id,
            name=name,
            manifest=manifest,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
        )

    async def patch_admin_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
        manifest: _upstream_models.BankTemplateManifest | dict[str, Any] | None = None,
    ):
        """Partial update of an admin template."""
        return await self._do_patch_template(
            template_id,
            scope="admin",
            name=name,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
            manifest=manifest,
        )

    async def create_bank_from_template(
        self,
        *,
        bank_id: str,
        template: str,
        name: str | None = None,
    ) -> CreateBankFromTemplateResult:
        """Create a bank by installing a template. Returns a wrapper-owned
        dataclass whose `import_result` field is the upstream
        BankTemplateImportResponse class. Do NOT mutate the generated local
        response in place — Pydantic validate_assignment would coerce the
        upstream instance back to the local class.
        """
        request = _local_models.CreateBankFromTemplateRequest(
            bank_id=bank_id,
            template=template,
            name=name,
        )
        raw = await self._banks_api.create_bank_from_template(
            create_bank_from_template_request=request,
        )
        return CreateBankFromTemplateResult(
            bank_id=raw.bank_id,
            template=raw.template,
            bank_created=raw.bank_created,
            import_result=_upstream_import_response_from_local(raw.import_result),
        )

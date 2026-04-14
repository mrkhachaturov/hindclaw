"""Hindclaw Python client — convenience wrapper around generated API client.

Usage:
    from hindclaw_client import HindclawClient

    client = HindclawClient("https://hindsight.home.local", api_key="hc_admin_xxxxx")
    users = await client.list_users()
"""
from hindclaw_client_api import ApiClient, Configuration
from hindclaw_client_api.api import DefaultApi

from dataclasses import dataclass
from typing import Any

import hindsight_client_api.models as _upstream_models
import hindclaw_client_api.models as _local_models


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

    Args:
        base_url: Hindsight server URL.
        api_key: Hindclaw API key or JWT token.
    """

    def __init__(self, base_url: str, api_key: str):
        config = Configuration(host=base_url)
        config.api_key["HTTPBearer"] = api_key
        self._client = ApiClient(config)
        self.api = DefaultApi(self._client)

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def create_my_template(
        self,
        *,
        id: str,
        name: str,
        manifest: _upstream_models.BankTemplateManifest | dict,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
    ):
        """Create a personal template.

        The manifest kwarg accepts either an upstream BankTemplateManifest
        instance or a dict in that shape. The wrapper converts upstream
        instances via model_dump() before constructing the local generated
        request model.
        """
        if isinstance(manifest, _upstream_models.BankTemplateManifest):
            manifest_payload = manifest.model_dump(mode="json", by_alias=True)
        else:
            manifest_payload = manifest
        request = _local_models.CreateTemplateRequest(
            id=id,
            name=name,
            description=description,
            category=category,
            integrations=integrations or [],
            tags=tags or [],
            manifest=manifest_payload,
        )
        return await self.api.create_my_template(create_template_request=request)

    async def patch_my_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
        manifest: _upstream_models.BankTemplateManifest | dict | None = None,
    ):
        """Partial update of a personal template. Every kwarg is optional;
        only provided fields are sent to the server.
        """
        if isinstance(manifest, _upstream_models.BankTemplateManifest):
            manifest_payload: dict | None = manifest.model_dump(mode="json", by_alias=True)
        else:
            manifest_payload = manifest
        patch = _local_models.PatchTemplateRequest(
            name=name,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
            manifest=manifest_payload,
        )
        return await self.api.patch_my_template(
            template_id=template_id,
            patch_template_request=patch,
        )

    async def create_admin_template(
        self,
        *,
        id: str,
        name: str,
        manifest: _upstream_models.BankTemplateManifest | dict,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
    ):
        """Create an admin (server-scope) template. Same conversion rule as create_my_template."""
        if isinstance(manifest, _upstream_models.BankTemplateManifest):
            manifest_payload = manifest.model_dump(mode="json", by_alias=True)
        else:
            manifest_payload = manifest
        request = _local_models.CreateTemplateRequest(
            id=id,
            name=name,
            description=description,
            category=category,
            integrations=integrations or [],
            tags=tags or [],
            manifest=manifest_payload,
        )
        return await self.api.create_admin_template(create_template_request=request)

    async def patch_admin_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        integrations: list[str] | None = None,
        tags: list[str] | None = None,
        manifest: _upstream_models.BankTemplateManifest | dict | None = None,
    ):
        """Partial update of an admin template."""
        if isinstance(manifest, _upstream_models.BankTemplateManifest):
            manifest_payload: dict | None = manifest.model_dump(mode="json", by_alias=True)
        else:
            manifest_payload = manifest
        patch = _local_models.PatchTemplateRequest(
            name=name,
            description=description,
            category=category,
            integrations=integrations,
            tags=tags,
            manifest=manifest_payload,
        )
        return await self.api.patch_admin_template(
            template_id=template_id,
            patch_template_request=patch,
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
        raw = await self.api.create_bank_from_template(
            create_bank_from_template_request=request,
        )
        return CreateBankFromTemplateResult(
            bank_id=raw.bank_id,
            template=raw.template,
            bank_created=raw.bank_created,
            import_result=_upstream_import_response_from_local(raw.import_result),
        )

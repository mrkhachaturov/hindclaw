"""Smoke test for the raw generated ``hindclaw_client_api`` client.

This test sidesteps the HindclawClient wrapper and drives the
generated aiohttp client (``TemplatesApi``) directly. It guards
against regressions in the generator output that would break
consumers who import ``hindclaw_client_api`` directly (e.g. the
Terraform provider build step which reuses the Go generator but
also cross-checks against Python shape).

A manifest dict (no upstream type involved) is passed through
``CreateTemplateRequest`` so this test does NOT exercise the
conversion layer — only the raw generated surface.
"""
from __future__ import annotations

import hindclaw_client_api
from hindclaw_client_api.models.create_template_request import CreateTemplateRequest


async def test_raw_generated_create_my_template(stub_server) -> None:
    base_url, state = stub_server
    configuration = hindclaw_client_api.Configuration(host=base_url)
    configuration.api_key["HTTPBearer"] = "test-token"

    async with hindclaw_client_api.ApiClient(configuration) as api_client:
        templates_api = hindclaw_client_api.TemplatesApi(api_client)
        request = CreateTemplateRequest(
            id="tmpl-raw",
            name="Raw Template",
            description=None,
            category=None,
            integrations=[],
            tags=[],
            manifest={"version": "1"},
        )
        response = await templates_api.create_my_template(create_template_request=request)

    assert response.id == "tmpl-raw"
    assert response.name == "Raw Template"
    assert response.scope == "personal"

    assert len(state.captured_requests) == 1
    captured = state.captured_requests[0]
    assert captured["method"] == "POST"
    assert captured["path"] == "/ext/hindclaw/me/templates"
    assert captured["body"]["id"] == "tmpl-raw"
    assert captured["body"]["manifest"] == {"version": "1"}

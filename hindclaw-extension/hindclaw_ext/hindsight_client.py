"""Hindsight Python SDK client factory for hindclaw-extension.

The extension runs inside the Hindsight server process but calls Hindsight's
REST API over HTTP (localhost) to create banks, directives, and mental models.
This keeps the extension boundary clean — it only adds HTTP endpoints, it
does not reach into Hindsight internals.

Configuration:
    HINDSIGHT_API_BASE_URL: Full base URL (e.g., http://127.0.0.1:8301).
        Takes precedence over port-based construction.
    HINDSIGHT_API_PORT: Port number (default 8301). Used when base URL is
        not explicitly set.
    HINDCLAW_HINDSIGHT_API_KEY: Optional API key for authenticating to the
        Hindsight API. If set, included as Authorization header.
"""

import logging
import os

from hindsight_client_api.api.banks_api import BanksApi
from hindsight_client_api.api.directives_api import DirectivesApi
from hindsight_client_api.api.mental_models_api import MentalModelsApi
from hindsight_client_api.api_client import ApiClient
from hindsight_client_api.configuration import Configuration

logger = logging.getLogger(__name__)

_DEFAULT_PORT = "8301"


def get_hindsight_base_url() -> str:
    """Resolve the Hindsight API base URL from environment.

    Checks HINDSIGHT_API_BASE_URL first, then constructs from
    HINDSIGHT_API_PORT (default 8301).

    Returns:
        Base URL string (e.g., "http://127.0.0.1:8301").
    """
    base_url = os.environ.get("HINDSIGHT_API_BASE_URL")
    if base_url:
        return base_url
    port = os.environ.get("HINDSIGHT_API_PORT", _DEFAULT_PORT)
    return f"http://127.0.0.1:{port}"


def _make_client() -> ApiClient:
    """Create a configured Hindsight API client.

    Returns:
        ApiClient configured with base URL and optional auth.
    """
    base_url = get_hindsight_base_url()
    config = Configuration(host=f"{base_url}/v1/default")
    client = ApiClient(configuration=config)
    api_key = os.environ.get("HINDCLAW_HINDSIGHT_API_KEY")
    if api_key:
        client.default_headers["Authorization"] = f"Bearer {api_key}"
    return client


def get_banks_api() -> BanksApi:
    """Get a BanksApi instance configured for localhost.

    Returns:
        BanksApi ready to call create_or_update_bank, update_bank_config, etc.
    """
    return BanksApi(api_client=_make_client())


def get_directives_api() -> DirectivesApi:
    """Get a DirectivesApi instance configured for localhost.

    Returns:
        DirectivesApi ready to call create_directive.
    """
    return DirectivesApi(api_client=_make_client())


def get_mental_models_api() -> MentalModelsApi:
    """Get a MentalModelsApi instance configured for localhost.

    Returns:
        MentalModelsApi ready to call create_mental_model.
    """
    return MentalModelsApi(api_client=_make_client())

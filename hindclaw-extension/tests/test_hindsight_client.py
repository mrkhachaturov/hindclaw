"""Tests for Hindsight client factory."""

import os
from unittest.mock import patch

import pytest

from hindclaw_ext.hindsight_client import (
    get_banks_api,
    get_directives_api,
    get_hindsight_base_url,
    get_mental_models_api,
)


class TestGetHindsightBaseUrl:
    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            url = get_hindsight_base_url()
        assert url == "http://127.0.0.1:8301"

    def test_custom_port(self):
        with patch.dict(os.environ, {"HINDSIGHT_API_PORT": "9999"}, clear=True):
            url = get_hindsight_base_url()
        assert url == "http://127.0.0.1:9999"

    def test_custom_base_url(self):
        with patch.dict(
            os.environ, {"HINDSIGHT_API_BASE_URL": "http://hindsight:8080"}, clear=True
        ):
            url = get_hindsight_base_url()
        assert url == "http://hindsight:8080"

    def test_base_url_takes_precedence_over_port(self):
        with patch.dict(
            os.environ,
            {"HINDSIGHT_API_BASE_URL": "http://custom:1234", "HINDSIGHT_API_PORT": "9999"},
            clear=True,
        ):
            url = get_hindsight_base_url()
        assert url == "http://custom:1234"


class TestGetApis:
    def test_get_banks_api(self):
        with patch.dict(os.environ, {"HINDSIGHT_API_PORT": "8301"}, clear=True):
            api = get_banks_api()
        assert api is not None

    def test_get_directives_api(self):
        with patch.dict(os.environ, {"HINDSIGHT_API_PORT": "8301"}, clear=True):
            api = get_directives_api()
        assert api is not None

    def test_get_mental_models_api(self):
        with patch.dict(os.environ, {"HINDSIGHT_API_PORT": "8301"}, clear=True):
            api = get_mental_models_api()
        assert api is not None

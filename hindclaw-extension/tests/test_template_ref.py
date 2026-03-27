"""Tests for template reference parsing."""

import pytest

from hindclaw_ext.template_ref import TemplateRef, parse_template_ref


class TestParseTemplateRef:
    def test_server_sourced(self):
        ref = parse_template_ref("server/hindclaw/backend-python")
        assert ref.scope == "server"
        assert ref.source == "hindclaw"
        assert ref.name == "backend-python"

    def test_personal_sourced(self):
        ref = parse_template_ref("personal/astrateam/backend-python")
        assert ref.scope == "personal"
        assert ref.source == "astrateam"
        assert ref.name == "backend-python"

    def test_server_custom(self):
        ref = parse_template_ref("server/backend-python")
        assert ref.scope == "server"
        assert ref.source is None
        assert ref.name == "backend-python"

    def test_personal_custom(self):
        ref = parse_template_ref("personal/my-template")
        assert ref.scope == "personal"
        assert ref.source is None
        assert ref.name == "my-template"

    def test_invalid_no_scope(self):
        with pytest.raises(ValueError, match="scope"):
            parse_template_ref("backend-python")

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="empty"):
            parse_template_ref("")

    def test_invalid_scope(self):
        with pytest.raises(ValueError, match="scope"):
            parse_template_ref("global/hindclaw/backend-python")

    def test_too_many_parts(self):
        with pytest.raises(ValueError, match="format"):
            parse_template_ref("server/hindclaw/sub/backend-python")

    def test_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            parse_template_ref("server/")

    def test_empty_source_and_name(self):
        with pytest.raises(ValueError, match="name"):
            parse_template_ref("server//")

    def test_name_with_hyphens_and_numbers(self):
        ref = parse_template_ref("server/hindclaw/backend-python-3")
        assert ref.name == "backend-python-3"

    def test_source_with_hyphens(self):
        ref = parse_template_ref("server/my-org/my-template")
        assert ref.source == "my-org"
        assert ref.name == "my-template"


class TestTemplateRefStr:
    def test_sourced_str(self):
        ref = TemplateRef(scope="server", source="hindclaw", name="backend-python")
        assert str(ref) == "server/hindclaw/backend-python"

    def test_custom_str(self):
        ref = TemplateRef(scope="personal", source=None, name="my-template")
        assert str(ref) == "personal/my-template"

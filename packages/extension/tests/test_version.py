"""Tests for version constants and semver comparison."""

from hindclaw_ext.version import (
    HINDCLAW_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    is_version_compatible,
)


class TestVersionConstants:
    def test_hindclaw_version_is_string(self):
        assert isinstance(HINDCLAW_VERSION, str)
        assert HINDCLAW_VERSION  # not empty

    def test_hindclaw_version_matches_pyproject(self):
        import importlib.metadata

        pkg_version = importlib.metadata.version("hindclaw-extension")
        assert HINDCLAW_VERSION == pkg_version

    def test_supported_schema_versions_contains_1(self):
        assert 1 in SUPPORTED_SCHEMA_VERSIONS


class TestIsVersionCompatible:
    def test_equal_versions(self):
        assert is_version_compatible("0.2.0", "0.2.0") is True

    def test_installed_newer(self):
        assert is_version_compatible("0.3.0", "0.2.0") is True

    def test_installed_older(self):
        assert is_version_compatible("0.1.0", "0.2.0") is False

    def test_patch_difference(self):
        assert is_version_compatible("0.2.1", "0.2.0") is True

    def test_major_difference(self):
        assert is_version_compatible("1.0.0", "0.9.0") is True

    def test_major_too_old(self):
        assert is_version_compatible("0.9.0", "1.0.0") is False

    def test_two_segment_versions(self):
        assert is_version_compatible("0.2", "0.2") is True

    def test_none_required_always_compatible(self):
        assert is_version_compatible("0.2.0", None) is True

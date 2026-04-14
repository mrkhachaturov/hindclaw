"""Tests for hindclaw_ext.models."""

from datetime import datetime, timezone

from hindclaw_ext.models import TemplateRecord
from hindclaw_ext.template_models import TemplateScope


def test_template_record_stores_manifest_as_opaque_dict():
    now = datetime.now(timezone.utc)
    manifest = {
        "version": "1",
        "bank": {"reflect_mission": "m"},
    }
    record = TemplateRecord(
        id="backend-python",
        scope=TemplateScope.PERSONAL,
        owner="user-1",
        source_name="hindclaw-official",
        source_scope=TemplateScope.SERVER,
        source_owner=None,
        source_template_id="backend-python",
        source_url="https://example.com/raw",
        source_revision="etag-abc",
        name="Backend Python",
        description="Backend patterns",
        category="coding",
        integrations=["claude-code"],
        tags=["python"],
        manifest=manifest,
        installed_at=now,
        updated_at=now,
    )
    assert record.manifest is manifest
    assert record.scope is TemplateScope.PERSONAL


def test_template_record_is_a_dataclass_with_expected_field_count():
    """The new TemplateRecord has exactly 17 fields: no template-content
    fields are materialized onto the record — everything lives inside the
    opaque manifest dict. ``source_owner`` is persisted alongside
    ``source_name``/``source_scope`` so /update can resolve the original
    source even when a different admin makes the call."""
    from dataclasses import fields

    field_names = {f.name for f in fields(TemplateRecord)}
    expected = {
        "id",
        "scope",
        "owner",
        "source_name",
        "source_scope",
        "source_owner",
        "source_template_id",
        "source_url",
        "source_revision",
        "name",
        "description",
        "category",
        "integrations",
        "tags",
        "manifest",
        "installed_at",
        "updated_at",
    }
    assert field_names == expected


def test_template_record_does_not_carry_legacy_fields():
    """Regression: make sure none of the deleted seed fields appear
    on the dataclass after the refactor."""
    from dataclasses import fields

    field_names = {f.name for f in fields(TemplateRecord)}
    legacy = {
        "directive_seeds",
        "mental_model_seeds",
        "entity_labels",
        "schema_version",
        "min_hindclaw_version",
        "min_hindsight_version",
        "reflect_mission",
        "retain_mission",
        "retain_extraction_mode",
        "observations_mission",
        "enable_observations",
    }
    assert field_names.isdisjoint(legacy), f"TemplateRecord still carries legacy fields: {field_names & legacy}"


def test_policy_record():
    """PolicyRecord from DB row."""
    from hindclaw_ext.models import PolicyRecord

    r = PolicyRecord(
        id="fleet-access",
        display_name="Fleet Access",
        is_builtin=False,
        document_json={"version": "2026-03-24", "statements": []},
    )
    assert r.id == "fleet-access"
    assert r.is_builtin is False


def test_policy_attachment_record():
    """PolicyAttachmentRecord from DB row."""
    from hindclaw_ext.models import PolicyAttachmentRecord

    r = PolicyAttachmentRecord(
        policy_id="fleet-access",
        principal_type="group",
        principal_id="default",
        priority=10,
    )
    assert r.priority == 10


def test_service_account_record():
    """ServiceAccountRecord from DB row."""
    from hindclaw_ext.models import ServiceAccountRecord

    r = ServiceAccountRecord(
        id="ceo-claude",
        owner_user_id="ceo@astrateam.net",
        display_name="CEO Claude",
        is_active=True,
        scoping_policy_id=None,
    )
    assert r.scoping_policy_id is None


def test_service_account_key_record():
    """ServiceAccountKeyRecord from DB row."""
    from hindclaw_ext.models import ServiceAccountKeyRecord

    r = ServiceAccountKeyRecord(
        id="key-1",
        service_account_id="ceo-claude",
        api_key="hc_sa_xxx",
        description="Test key",
    )
    assert r.api_key.startswith("hc_sa_")


def test_bank_policy_record():
    """BankPolicyRecord from DB row."""
    from hindclaw_ext.models import BankPolicyRecord

    r = BankPolicyRecord(
        bank_id="yoda",
        document_json={"version": "2026-03-24", "default_strategy": "yoda-default"},
    )
    assert r.bank_id == "yoda"


def test_user_record_is_active():
    """UserRecord has is_active field defaulting to True."""
    from hindclaw_ext.models import UserRecord

    r = UserRecord(id="alice", display_name="Alice")
    assert r.is_active is True


def test_template_source_record_with_scope():
    """TemplateSourceRecord accepts scope and owner fields."""
    from hindclaw_ext.models import TemplateSourceRecord

    rec = TemplateSourceRecord(
        name="hindclaw",
        url="https://github.com/hindclaw/templates",
        scope="server",
        owner=None,
    )
    assert rec.scope == "server"
    assert rec.owner is None

    personal = TemplateSourceRecord(
        name="hindclaw",
        url="https://github.com/alice/templates",
        scope="personal",
        owner="alice",
    )
    assert personal.scope == "personal"
    assert personal.owner == "alice"

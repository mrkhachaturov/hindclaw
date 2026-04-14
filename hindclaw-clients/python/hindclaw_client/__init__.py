"""HindClaw Python client — public surface.

Re-exports upstream Hindsight types where HindClaw inherits them from the
upstream API surface (manifest format, mental models, directives). HindClaw-
specific types and methods come from hindclaw_client_api through the
HindclawClient wrapper in client.py.

Runtime identity caveat: re-exports here expose the upstream classes at the
import boundary, but the generated hindclaw_client_api code still constructs
local classes when deserializing responses. The HindclawClient wrapper in
client.py performs explicit model_dump/model_validate conversion at the
public boundary so consumers calling wrapper methods always see upstream
instances. See the Architecture / Python section of the Plan D spec for
full rationale.
"""

from hindsight_client_api.models import (
    BankTemplateConfig,
    BankTemplateDirective,
    BankTemplateImportResponse,
    BankTemplateManifest,
    BankTemplateMentalModel,
    MentalModelTriggerInput,
    MentalModelTriggerOutput,
)

from .client import HindclawClient

__all__ = [
    "BankTemplateConfig",
    "BankTemplateDirective",
    "BankTemplateImportResponse",
    "BankTemplateManifest",
    "BankTemplateMentalModel",
    "HindclawClient",
    "MentalModelTriggerInput",
    "MentalModelTriggerOutput",
]

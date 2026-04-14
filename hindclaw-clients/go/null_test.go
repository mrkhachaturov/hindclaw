// JSON round-trip test for BankTemplateManifest with its nullable Bank
// field explicitly set to null.
//
// openapi-generator's Go target encodes OpenAPI "nullable: true" fields
// as NullableT wrappers (not Go pointers). The wrapper marshals to
// `null` when unset and `{...}` when set. This test guards against a
// regression where the generator stops honouring the nullable marker
// (in which case the Bank field would disappear instead of serialising
// as `null`) and against a regression where the unmarshal path fails
// to populate the wrapper from a `null` JSON value.
package hindclaw_test

import (
	"encoding/json"
	"testing"

	hindclaw "github.com/mrkhachaturov/hindclaw/hindclaw-clients/go/hindclaw"
)

func TestBankTemplateManifestNullBank(t *testing.T) {
	raw := []byte(`{"version":"1","bank":null,"mental_models":[],"directives":[]}`)

	var manifest hindclaw.BankTemplateManifest
	if err := json.Unmarshal(raw, &manifest); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if manifest.Version != "1" {
		t.Errorf("expected version '1', got %q", manifest.Version)
	}
	if manifest.Bank.IsSet() {
		// IsSet returns true if either a value was provided or an
		// explicit null was sent. We rely on Get() returning nil to
		// distinguish "not present" from "explicit null".
		if manifest.Bank.Get() != nil {
			t.Errorf("expected Bank.Get() == nil for null JSON, got %+v", manifest.Bank.Get())
		}
	}

	// Round-trip back to JSON. The Bank field must survive as
	// `null` — not be dropped entirely — so the server can
	// distinguish "no change" from "clear the bank config".
	out, err := json.Marshal(&manifest)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(out, &decoded); err != nil {
		t.Fatalf("decode round-tripped json: %v", err)
	}
	if _, present := decoded["version"]; !present {
		t.Errorf("expected version in round-tripped json, got %s", string(out))
	}
}

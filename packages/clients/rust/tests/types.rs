//! serde_json round-trip test for the progenitor-generated
//! BankTemplateManifest type.
//!
//! Progenitor emits all types inline into a single .rs file under
//! OUT_DIR, accessible via `hindclaw_client::types::*`. This test
//! guards against regressions in the generator or in the upstream
//! schema that would break serde_json deserialisation of a manifest
//! literal with an explicit `bank: null`.

use hindclaw_client::types::BankTemplateManifest;

#[test]
fn bank_template_manifest_roundtrip() {
    let raw = serde_json::json!({
        "version": "1",
        "bank": null,
        "mental_models": [],
        "directives": []
    });

    let manifest: BankTemplateManifest =
        serde_json::from_value(raw.clone()).expect("deserialize manifest");
    assert_eq!(manifest.version, "1");
    assert!(manifest.bank.is_none());
    assert!(manifest.mental_models.as_ref().map(|m| m.is_empty()).unwrap_or(true));
    assert!(manifest.directives.as_ref().map(|d| d.is_empty()).unwrap_or(true));

    // Round-trip back to JSON and deserialise again — the second
    // deserialise exercises any Default/skip_serializing quirks in
    // the generated struct.
    let reserialised = serde_json::to_value(&manifest).expect("serialize manifest");
    let manifest2: BankTemplateManifest =
        serde_json::from_value(reserialised).expect("deserialize round-tripped manifest");
    assert_eq!(manifest2.version, "1");
}

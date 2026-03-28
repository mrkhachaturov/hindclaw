use std::env;
use std::fs;
use std::path::PathBuf;

/// Convert OpenAPI 3.1 spec to 3.0 for progenitor compatibility
fn convert_31_to_30(spec: &mut serde_json::Value) {
    if let Some(obj) = spec.as_object_mut() {
        obj.insert("openapi".to_string(), serde_json::json!("3.0.3"));
    }
    convert_anyof_to_nullable(spec);
}

/// Remove paths with multipart/form-data content type (not supported by progenitor)
fn filter_multipart_endpoints(spec: &mut serde_json::Value) {
    if let Some(paths) = spec.get_mut("paths").and_then(|v| v.as_object_mut()) {
        let mut paths_to_remove = Vec::new();

        for (path_name, path_item) in paths.iter() {
            if let Some(operations) = path_item.as_object() {
                for (_method, operation) in operations.iter() {
                    if let Some(request_body) = operation.get("requestBody") {
                        if let Some(content) = request_body.get("content") {
                            if let Some(content_obj) = content.as_object() {
                                if content_obj.contains_key("multipart/form-data") {
                                    eprintln!(
                                        "Filtering out endpoint with multipart/form-data: {}",
                                        path_name
                                    );
                                    paths_to_remove.push(path_name.clone());
                                    break;
                                }
                            }
                        }
                    }
                }
            }
        }

        for path in paths_to_remove {
            paths.remove(&path);
        }
    }
}

fn convert_anyof_to_nullable(value: &mut serde_json::Value) {
    match value {
        serde_json::Value::Object(obj) => {
            let has_null_in_anyof = obj
                .get("anyOf")
                .and_then(|v| v.as_array())
                .map(|array| {
                    array.iter().any(|v| {
                        v.get("type")
                            .and_then(|t| t.as_str())
                            .map(|s| s == "null")
                            .unwrap_or(false)
                    })
                })
                .unwrap_or(false);

            if has_null_in_anyof {
                if let Some(any_of) = obj.get("anyOf").cloned() {
                    if let Some(array) = any_of.as_array() {
                        let non_null_schemas: Vec<_> = array
                            .iter()
                            .filter(|v| {
                                v.get("type")
                                    .and_then(|t| t.as_str())
                                    .map(|s| s != "null")
                                    .unwrap_or(true)
                            })
                            .cloned()
                            .collect();

                        obj.remove("anyOf");
                        if non_null_schemas.len() == 1 {
                            if let Some(non_null_obj) = non_null_schemas[0].as_object() {
                                for (k, v) in non_null_obj.iter() {
                                    obj.insert(k.clone(), v.clone());
                                }
                            }
                        } else {
                            obj.insert(
                                "anyOf".to_string(),
                                serde_json::json!(non_null_schemas),
                            );
                        }
                        obj.insert("nullable".to_string(), serde_json::json!(true));
                    }
                }
            }

            for (_key, val) in obj.iter_mut() {
                convert_anyof_to_nullable(val);
            }
        }
        serde_json::Value::Array(arr) => {
            for item in arr.iter_mut() {
                convert_anyof_to_nullable(item);
            }
        }
        _ => {}
    }
}

fn main() {
    // Look for openapi.json in the crate directory first (for crates.io),
    // then fall back to parent directory (for monorepo development).
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let openapi_path = {
        let local = manifest_dir.join("openapi.json");
        if local.exists() {
            local
        } else {
            manifest_dir.parent().unwrap().join("openapi.json")
        }
    };

    println!("cargo:rerun-if-changed={}", openapi_path.display());

    let spec_content = fs::read_to_string(&openapi_path)
        .expect("Failed to read openapi.json. Run extract-openapi.py first.");

    let mut spec_json: serde_json::Value =
        serde_json::from_str(&spec_content).expect("Failed to parse openapi.json");

    // Convert OpenAPI 3.1.0 to 3.0.3 for progenitor compatibility
    if let Some(version) = spec_json.get("openapi").and_then(|v| v.as_str()) {
        if version.starts_with("3.1") {
            eprintln!("Converting OpenAPI 3.1 to 3.0 for compatibility...");
            convert_31_to_30(&mut spec_json);
        }
    }

    filter_multipart_endpoints(&mut spec_json);

    let spec: openapiv3::OpenAPI =
        serde_json::from_value(spec_json).expect("Failed to parse converted OpenAPI spec");

    let mut generator = progenitor::Generator::default();

    let tokens = generator
        .generate_tokens(&spec)
        .expect("Failed to generate client code from OpenAPI spec");

    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let dest_path = out_dir.join("hindclaw_client_generated.rs");

    let syntax_tree = syn::parse2(tokens).expect("Failed to parse generated tokens");
    let mut formatted = prettyplease::unparse(&syntax_tree);

    formatted = fix_optional_header_params(&formatted);

    fs::write(&dest_path, formatted).expect("Failed to write generated client code");

    println!("Generated client at: {}", dest_path.display());
}

/// Fix progenitor's generated code for optional header parameters.
/// All 39 hindclaw endpoints use HTTPBearer, so this fix is required.
fn fix_optional_header_params(code: &str) -> String {
    use regex::Regex;

    let re = Regex::new(
        r#"header_map\.append\("authorization", value\.to_string\(\)\.try_into\(\)\?\)"#,
    )
    .expect("Invalid regex");

    re.replace_all(
        code,
        r#"header_map.append("authorization", value.unwrap_or_default().to_string().try_into()?)"#,
    )
    .to_string()
}

package hindclaw

// PERMANENT WORKAROUND: HindClaw's Go client duplicates upstream-owned
// types (BankTemplateManifest, BankTemplateConfig, BankTemplateMentalModel,
// BankTemplateDirective, MentalModelTrigger, BankTemplateImportResponse)
// because openapi-generator's Go target writes generated types into the
// same package as the hand-maintained wrapper, so Go type aliases to the
// upstream types would collide with the generated structs. Consumers
// wanting type unity between @hindclaw/go and @hindsight/go must copy
// between them explicitly at the boundary.
// Long-term resolution: a subpackage restructure for generated code
// could enable type aliasing, but the work would require updating every
// call site in terraform-provider-hindclaw. Deferred unless a concrete
// consumer needs type unity between @hindclaw/go and @hindsight/go.

import (
	"net/http"
	"time"
)

// NewAPIClientWithToken creates a new Hindclaw API client configured
// with a base URL and API token (JWT or API key).
//
// The token is sent as a Bearer token in the Authorization header.
// Use this for Terraform providers, CLI tools, or any client that
// manages hindclaw access control resources.
//
// Example:
//
//	client := hindclaw.NewAPIClientWithToken("https://hindsight.home.local", "hc_terraform_xxxxx")
//	resp, _, err := client.ExtensionAPI.ListUsers(ctx).Execute()
func NewAPIClientWithToken(baseURL, token string) *APIClient {
	cfg := NewConfiguration()
	cfg.Servers = ServerConfigurations{
		{URL: baseURL},
	}
	cfg.AddDefaultHeader("Authorization", "Bearer "+token)
	return NewAPIClient(cfg)
}

// NewAPIClientWithTimeout creates a new Hindclaw API client with a request timeout.
//
// Example:
//
//	client := hindclaw.NewAPIClientWithTimeout("https://hindsight.home.local", "hc_terraform_xxxxx", 30*time.Second)
func NewAPIClientWithTimeout(baseURL, token string, timeout time.Duration) *APIClient {
	cfg := NewConfiguration()
	cfg.Servers = ServerConfigurations{
		{URL: baseURL},
	}
	cfg.AddDefaultHeader("Authorization", "Bearer "+token)
	cfg.HTTPClient = &http.Client{Timeout: timeout}
	return NewAPIClient(cfg)
}

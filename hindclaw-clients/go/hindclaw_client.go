package hindclaw

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

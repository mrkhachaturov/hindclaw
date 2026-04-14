// HTTP integration smoke test for the generated Go client.
//
// Uses httptest.NewServer to stand up a real HTTP listener with a
// single handler that asserts the request shape and returns a canned
// JSON body. The test verifies that client.DefaultAPI.CreateGroup
// serialises a CreateGroupRequest to the expected wire format and
// parses the server's GroupSummaryResponse correctly.
package hindclaw_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	hindclaw "github.com/mrkhachaturov/hindclaw/hindclaw-clients/go/hindclaw"
)

func TestCreateGroupIntegration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/ext/hindclaw/groups" {
			t.Errorf("expected /ext/hindclaw/groups, got %s", r.URL.Path)
		}

		var payload hindclaw.CreateGroupRequest
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if payload.Id != "grp-1" {
			t.Errorf("expected Id grp-1, got %s", payload.Id)
		}
		if payload.DisplayName != "Engineering" {
			t.Errorf("expected DisplayName Engineering, got %s", payload.DisplayName)
		}

		// The Go generator produces GroupSummaryResponse (not
		// GroupResponse) for the /groups endpoints. This mirrors the
		// Python/TS output and matches model_group_summary_response.go.
		resp := hindclaw.GroupSummaryResponse{
			Id:          payload.Id,
			DisplayName: payload.DisplayName,
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := hindclaw.NewAPIClientWithToken(server.URL, "test-token")

	req := hindclaw.CreateGroupRequest{Id: "grp-1", DisplayName: "Engineering"}
	resp, httpResp, err := client.DefaultAPI.CreateGroup(context.Background()).CreateGroupRequest(req).Execute()
	if err != nil {
		t.Fatalf("CreateGroup returned error: %v", err)
	}
	if httpResp.StatusCode != http.StatusOK {
		t.Errorf("expected 200 OK, got %d", httpResp.StatusCode)
	}
	if resp.Id != "grp-1" {
		t.Errorf("expected response Id grp-1, got %s", resp.Id)
	}
	if resp.DisplayName != "Engineering" {
		t.Errorf("expected response DisplayName Engineering, got %s", resp.DisplayName)
	}
}

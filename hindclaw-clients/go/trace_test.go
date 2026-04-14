// httptrace hook test — verifies the generated Go client honours the
// ctx's ClientTrace so consumers (e.g. terraform-provider-hindclaw)
// can attach tracing/metrics to outbound requests without forking the
// client.
package hindclaw_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/http/httptrace"
	"testing"

	hindclaw "github.com/mrkhachaturov/hindclaw/hindclaw-clients/go/hindclaw"
)

func TestClientHonoursHTTPTrace(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[]`))
	}))
	defer server.Close()

	client := hindclaw.NewAPIClientWithToken(server.URL, "test-token")

	var gotStart, gotGotConn bool
	trace := &httptrace.ClientTrace{
		GetConn:  func(hostPort string) { gotStart = true },
		GotConn:  func(info httptrace.GotConnInfo) { gotGotConn = true },
	}
	ctx := httptrace.WithClientTrace(context.Background(), trace)

	_, httpResp, err := client.DefaultAPI.ListUsers(ctx).Execute()
	if err != nil {
		t.Fatalf("ListUsers returned error: %v", err)
	}
	if httpResp.StatusCode != http.StatusOK {
		t.Errorf("expected 200 OK, got %d", httpResp.StatusCode)
	}
	if !gotStart {
		t.Error("expected httptrace GetConn hook to fire")
	}
	if !gotGotConn {
		t.Error("expected httptrace GotConn hook to fire")
	}
}

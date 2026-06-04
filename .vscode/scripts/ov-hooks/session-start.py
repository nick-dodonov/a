#!/usr/bin/env python3
"""
SessionStart hook — VS Code Copilot ↔ OpenViking.

Injects two independently-gated blocks via additionalContext:
  1. Profile: viking://user/memories/profile.md (always, unless server down)
  2. Recent context: semantic search across user + agent memories
     scoped to the current project.

Equivalent to the Claude Code memory plugin session-start.mjs.
Timeout budget: 60s (set in ov-session-start.json).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from lib import (
    load_config,
    http_get,
    http_post,
    read_uri,
    search,
    read_stdin,
    hook_continue,
    session_start_output,
    print_json,
    project_from_cwd,
    truncate,
    derive_session_id,
    create_session,
)


PROFILE_URI = "viking://user/memories/profile.md"
PROFILE_TOKEN_BUDGET = 3000  # chars
SEARCH_LIMIT = 5
SEARCH_TIMEOUT = 10.0
READ_TIMEOUT = 8.0
# Session-start uses a lower threshold — context is "cold", broad recall preferred
SESSION_SCORE_THRESHOLD = 0.1


def main():
    inp = read_stdin()
    cwd = inp.get("cwd") or os.getcwd()
    project = project_from_cwd(cwd)
    
    # Get Copilot session ID for OV session creation
    copilot_session_id = inp.get("sessionId") or inp.get("session_id") or ""

    cfg = load_config()

    # Create OV session early (but don't fail if it fails)
    if copilot_session_id:
        ov_session_id = derive_session_id(copilot_session_id)
        create_result = create_session(cfg, ov_session_id, title=f"Copilot: {project}", timeout=10.0)
        # Silently ignore if it already exists or fails

    # Health check — fast fail
    health = http_get(cfg, "/health", timeout=5.0)
    if not health["ok"]:
        print_json(hook_continue())
        return

    sections = []

    # 1. Profile injection
    profile_content = read_uri(cfg, PROFILE_URI, timeout=READ_TIMEOUT)
    if profile_content and profile_content.strip():
        capped = profile_content.strip()
        if len(capped) > PROFILE_TOKEN_BUDGET:
            capped = capped[:PROFILE_TOKEN_BUDGET] + "\n... [truncated]"
        sections.append(f"<profile>\n{capped}\n</profile>")

    # 2. Semantic search — user memories + agent memories scoped to project
    queries = [
        f"{project} recent work context",
        f"{project} decisions architecture",
    ]
    seen_uris: set = set()
    result_lines = []

    for query in queries:
        for target in ("viking://user/memories", "viking://agent/memories"):
            items = search(cfg, query, target, limit=SEARCH_LIMIT, timeout=SEARCH_TIMEOUT)
            for item in items:
                uri = item.get("uri", "")
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)
                score = item.get("score", 0)
                if score < SESSION_SCORE_THRESHOLD:
                    continue
                abstract = (item.get("abstract") or item.get("overview") or "").strip()
                if not abstract:
                    continue
                abstract = truncate(abstract, 300)
                result_lines.append(f"- {abstract} [{uri}] (score {score:.2f})")

    if result_lines:
        block = "\n".join(result_lines[:8])
        sections.append(f"<memories>\n{block}\n</memories>")

    if not sections:
        print_json(hook_continue())
        return

    context = (
        "<openviking-context source=\"session-start\">\n"
        + "\n\n".join(sections)
        + "\n</openviking-context>"
    )

    print_json(session_start_output(context))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print_json(hook_continue())

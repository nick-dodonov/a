#!/usr/bin/env python3
"""
PostToolUse hook — VS Code Copilot ↔ OpenViking.

Captures significant tool events as messages in the persistent OV session.
This augments the Stop-time transcript capture for tools whose outcomes
benefit from being recorded immediately (file edits, terminal commands).

Captured tool names: create_file, apply_patch, replace_string_in_file,
  insert_edit_into_file, run_in_terminal, multi_replace_string_in_file.

Fire-and-forget: always returns continue immediately; OV write is async.
Timeout budget: 8s (set in ov-post-tool-use.json).
"""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(__file__))
from lib import (
    load_config,
    add_message,
    derive_session_id,
    read_stdin,
    hook_continue,
    print_json,
    truncate,
    project_from_cwd,
)

CAPTURE_TOOLS = {
    "create_file",
    "apply_patch",
    "replace_string_in_file",
    "insert_edit_into_file",
    "multi_replace_string_in_file",
    "run_in_terminal",
    "delete_file",
}

MAX_INPUT_CHARS = 600
MAX_RESPONSE_CHARS = 300


def _capture_async(cfg: dict, ov_session_id: str, content: str) -> None:
    try:
        add_message(cfg, ov_session_id, "assistant", content, timeout=7.0)
    except Exception:
        pass


def main():
    # Always return immediately — write is fire-and-forget in background thread
    inp = read_stdin()

    tool_name = str(inp.get("tool_name") or "")
    if tool_name not in CAPTURE_TOOLS:
        print_json(hook_continue())
        return

    session_id = str(inp.get("sessionId") or inp.get("session_id") or "")
    if not session_id:
        print_json(hook_continue())
        return

    cwd = inp.get("cwd") or os.getcwd()
    tool_input = inp.get("tool_input") or inp.get("input") or {}
    tool_response = inp.get("tool_response") or inp.get("response") or ""

    # Format input
    if isinstance(tool_input, dict):
        input_text = truncate(
            "; ".join(f"{k}={v}" for k, v in tool_input.items() if v), MAX_INPUT_CHARS
        )
    else:
        input_text = truncate(str(tool_input), MAX_INPUT_CHARS)

    response_text = truncate(str(tool_response), MAX_RESPONSE_CHARS)

    parts = [f"Copilot tool event: {tool_name}."]
    if input_text:
        parts.append(f"Input: {input_text}.")
    if response_text:
        parts.append(f"Result: {response_text}.")
    content = " ".join(parts)

    if len(content) < 32:
        print_json(hook_continue())
        return

    cfg = load_config()
    ov_session_id = derive_session_id(session_id)

    t = threading.Thread(target=_capture_async, args=(cfg, ov_session_id, content), daemon=True)
    t.start()
    # Give it a moment but don't block the hook
    t.join(timeout=0.1)

    print_json(hook_continue())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print_json(hook_continue())

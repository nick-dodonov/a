#!/usr/bin/env python3
"""
UserPromptSubmit hook — Capture incremental turns to OpenViking.

Fires before each user prompt submission. Reads the session transcript,
extracts new turns since last capture, filters for signal, and commits to
OpenViking session.

Key difference from auto-capture.py (Stop hook): this one actually fires
in VS Code Copilot agent mode.

Capture state persisted per session in .states/ to prevent re-sending.
After pushing new turns, immediately calls commit() to archive them
(Phase 2 memory extraction runs async in background).

Timeout budget: 8s (set in ov-user-prompt-capture.json).
"""

import sys
import os
import json
import re
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from lib import (
    load_config,
    add_message,
    derive_session_id,
    read_stdin,
    hook_continue,
    print_json,
    truncate,
)

STATE_DIR = Path(__file__).parent / ".states"
MAX_TURNS = 15          # max turns to push per UserPromptSubmit
MAX_CONTENT_CHARS = 800

# Strip our own injected context blocks before storing
_CTX_BLOCK_RE = re.compile(
    r"<openviking-context[\s\S]*?</openviking-context>|"
    r"<relevant-memories[\s\S]*?</relevant-memories>",
    re.IGNORECASE,
)

# Memory trigger patterns from OpenViking design guidelines
TRIGGERS = {
    "decision": re.compile(
        r"\bdecid(ed|ing)|I'll|let's|we should|I think we (should|need)|conclusion|going forward",
        re.IGNORECASE
    ),
    "error": re.compile(
        r"\b(bug|error|failed?|issue|problem|crash|broke|broken|fix(ed)?|resolved?|workaround|didn't work)",
        re.IGNORECASE
    ),
    "learning": re.compile(
        r"\b(learned?|realized|understand|discovered|turns out|didn't know|new pattern|aha|insight)",
        re.IGNORECASE
    ),
    "implementation": re.compile(
        r"\b(implement(ed)?|add(ed)?|refactor(ed)?|refine|clean up|improve|optimize|restructure)",
        re.IGNORECASE
    ),
    "important": re.compile(
        r"\b(important|critical|must|remember|never forget|always|never|architecture|principle|constraint|requirement)",
        re.IGNORECASE
    ),
    "preference": re.compile(
        r"\b(prefer|preference|want|like|don't like|style|convention|pattern|approach)",
        re.IGNORECASE
    ),
}

# Manual override markers
FORCE_REMEMBER = re.compile(r"#remember|❤️", re.IGNORECASE)
FORCE_SKIP = re.compile(r"#skip|#ignore", re.IGNORECASE)


def log_error(msg: str, exc: Exception = None) -> None:
    """Log error to both stderr and a local file for debugging."""
    try:
        log_dir = Path(__file__).parent / ".logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"user-prompt-capture.log"
        full_msg = f"{msg}\n"
        if exc:
            full_msg += f"  {type(exc).__name__}: {exc}\n{traceback.format_exc()}\n"
        existing = log_file.read_text("utf-8") if log_file.exists() else ""
        log_file.write_text(existing + full_msg)
        print(f"[user-prompt-capture] {msg}", file=sys.stderr)
    except Exception:
        pass


def load_state(session_id: str) -> dict:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    f = STATE_DIR / f"{safe}.json"
    try:
        return json.loads(f.read_text("utf-8"))
    except Exception:
        return {"captured_turn_count": 0}


def save_state(session_id: str, state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
        state_file = STATE_DIR / f"{safe}.json"
        state_file.write_text(json.dumps(state), "utf-8")
    except Exception as e:
        log_error(f"Failed to save state", e)


def parse_transcript(content: str) -> list[dict]:
    """Parse transcript: JSON array or JSONL."""
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    messages = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except Exception:
            pass
    return messages


def _get_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return str(value or "")


def extract_turns(messages: list[dict]) -> list[dict]:
    """Extract user/assistant message pairs from raw transcript.
    
    VS Code Copilot format:
      type: "user.message" or "assistant.message"
      data.content: string (not blocks)
    """
    turns = []
    for msg in messages:
        msg_type = str(msg.get("type") or "")
        data = msg.get("data") or {}
        
        # Determine role from type
        if msg_type == "user.message":
            role = "user"
        elif msg_type == "assistant.message":
            role = "assistant"
        else:
            continue
        
        # Extract text from data.content (VS Code stores as plain string)
        content_raw = data.get("content", "")
        text = _get_text(content_raw)
        
        # Strip our injected context blocks
        text = _CTX_BLOCK_RE.sub("", text).strip()
        text = re.sub(r"\s+", " ", text).strip()
        
        if not text or len(text) < 8:
            continue
        
        turns.append({"role": role, "content": text})
    return turns


def should_capture_turn(turn: dict) -> bool:
    """Filter turns using OpenViking's smart heuristics.
    
    Criteria:
    1. Manual override: #remember (force), #skip (suppress)
    2. Block spam: Copilot tool events, metadata
    3. Assistant messages: capture (high signal) unless spam
    4. User messages: capture if trigger found OR length > 60
    5. Minimum length: >= 12 chars (metadata filter)
    """
    text = turn["content"]
    
    # Minimum length check
    if len(text) < 12:
        return False
    
    # Spam filter: block low-signal messages
    if "Copilot tool event" in text or "Copilot tool execution" in text:
        return False
    if text.startswith("[tool:") or text.startswith("Tool: "):
        return False
    
    # Manual overrides take precedence
    if FORCE_REMEMBER.search(text):
        return True
    if FORCE_SKIP.search(text):
        return False
    
    # Always capture assistant responses (they have high signal)
    if turn["role"] == "assistant":
        return True
    
    # User messages: capture if meaningful
    # Check for trigger keywords
    for category, pattern in TRIGGERS.items():
        if pattern.search(text):
            return True
    
    # Or if longer (likely substantial)
    if len(text) > 60:
        return True
    
    return False


def main():
    inp = read_stdin()
    session_id = str(inp.get("sessionId") or inp.get("session_id") or "")
    transcript_path = str(inp.get("transcript_path") or "")

    # UserPromptSubmit might not always have these; that's ok
    if not session_id or not transcript_path:
        print_json(hook_continue())
        return

    try:
        raw = Path(transcript_path).read_text("utf-8")
    except Exception as e:
        log_error(f"Failed to read transcript", e)
        print_json(hook_continue())
        return

    messages = parse_transcript(raw)
    all_turns = extract_turns(messages)

    if not all_turns:
        print_json(hook_continue())
        return

    state = load_state(session_id)
    already_captured = state.get("captured_turn_count", 0)
    new_turns = all_turns[already_captured:]

    if not new_turns:
        print_json(hook_continue())
        return

    # Filter and cap
    filtered_turns = [t for t in new_turns if should_capture_turn(t)][:MAX_TURNS]
    
    log_error(f"Filtering: {len(new_turns)} new → {len(filtered_turns)} after filter")
    
    if not filtered_turns:
        print_json(hook_continue())
        return

    cfg = load_config()
    ov_session_id = derive_session_id(session_id)

    # Push incremental turns (OpenViking archives automatically, we don't commit)
    pushed_count = 0
    for turn in filtered_turns:
        content = truncate(turn["content"], MAX_CONTENT_CHARS)
        result = add_message(cfg, ov_session_id, turn["role"], content, timeout=6.0)
        if result["ok"]:
            pushed_count += 1

    # Save state to prevent re-sending duplicates on next UserPromptSubmit
    save_state(session_id, {"captured_turn_count": len(all_turns)})

    print_json(hook_continue())



if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("Unhandled exception", e)
        print_json(hook_continue())

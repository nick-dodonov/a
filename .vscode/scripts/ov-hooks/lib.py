"""
Shared utilities for VS Code Copilot ↔ OpenViking lifecycle hooks.

Auth resolution priority:
  1. OPENVIKING_URL / OPENVIKING_API_KEY env vars
  2. ~/.openviking/ovcli.conf  (fields: url, api_key, root_api_key)
  3. ~/.openviking/ov.conf     (field: server.host / server.port)
  4. Built-in default: http://localhost:1933, no auth
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_URL = "http://localhost:1933"
_OVCLI_CONF = Path.home() / ".openviking" / "ovcli.conf"
_OV_CONF = Path.home() / ".openviking" / "ov.conf"


def _try_load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def load_config() -> dict:
    ovcli = _try_load_json(_OVCLI_CONF)
    ov = _try_load_json(_OV_CONF)

    url = (
        os.environ.get("OPENVIKING_URL")
        or os.environ.get("OPENVIKING_BASE_URL")
        or ovcli.get("url")
        or _DEFAULT_URL
    )
    api_key = (
        os.environ.get("OPENVIKING_API_KEY")
        or os.environ.get("OPENVIKING_BEARER_TOKEN")
        or ovcli.get("api_key")
        or ovcli.get("root_api_key")
        or None
    )
    account = os.environ.get("OPENVIKING_ACCOUNT") or ovcli.get("account") or None
    user = os.environ.get("OPENVIKING_USER") or ovcli.get("user") or None
    agent_id = os.environ.get("OPENVIKING_AGENT_ID") or ovcli.get("agent_id") or None

    return {
        "url": url.rstrip("/"),
        "api_key": api_key,
        "account": account,
        "user": user,
        "agent_id": agent_id,
        "timeout": float(ovcli.get("timeout", 30.0)),
    }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _build_headers(cfg: dict) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    if cfg.get("account"):
        headers["X-OpenViking-Account"] = cfg["account"]
    if cfg.get("user"):
        headers["X-OpenViking-User"] = cfg["user"]
    if cfg.get("agent_id"):
        headers["X-OpenViking-Agent"] = cfg["agent_id"]
    return headers


def http_get(cfg: dict, path: str, timeout: float = 8.0) -> dict:
    url = cfg["url"] + path
    req = urllib.request.Request(url, headers=_build_headers(cfg), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": resp.status, "body": body}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)}


def http_post(cfg: dict, path: str, data: dict, timeout: float = 8.0) -> dict:
    url = cfg["url"] + path
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=_build_headers(cfg), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = str(e)
        return {"ok": False, "status": e.code, "body": body}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)}


# ---------------------------------------------------------------------------
# Session API helpers
# ---------------------------------------------------------------------------

def derive_session_id(copilot_session_id: str) -> str:
    """Stable OV session ID from a VS Code Copilot session_id."""
    return f"copilot-{copilot_session_id}"


def add_message(cfg: dict, ov_session_id: str, role: str, content: str, timeout: float = 15.0) -> dict:
    return http_post(
        cfg,
        f"/api/v1/sessions/{ov_session_id}/messages",
        {"role": role, "content": content},
        timeout=timeout,
    )


def create_session(cfg: dict, ov_session_id: str, title: str = "", timeout: float = 15.0) -> dict:
    """Create a new session if it doesn't exist."""
    return http_post(
        cfg,
        "/api/v1/sessions",
        {"sessionId": ov_session_id, "title": title or ov_session_id},
        timeout=timeout,
    )


def commit_session(cfg: dict, ov_session_id: str, timeout: float = 20.0) -> dict:
    return http_post(cfg, f"/api/v1/sessions/{ov_session_id}/commit", {}, timeout=timeout)


# ---------------------------------------------------------------------------
# URI resolution (mirrors claude-code-memory-plugin/scripts/auto-recall.mjs
# resolveTargetUri / resolveScopeSpace)
# ---------------------------------------------------------------------------

_space_cache: dict = {}

_USER_RESERVED = frozenset(["memories"])
_AGENT_RESERVED = frozenset(["memories", "skills", "instructions", "workspaces"])


def resolve_scope_space(cfg: dict, scope: str, timeout: float = 5.0) -> str:
    """Return the real space name for 'user' or 'agent' scope.

    Queries /api/v1/system/status for the current user, then lists
    viking://{scope} to confirm the space exists. Result is cached for the
    process lifetime (hooks are short-lived, so this is fine).
    """
    cache_key = (cfg.get("url", ""), scope)
    if cache_key in _space_cache:
        return _space_cache[cache_key]

    fallback = "default"

    # Get server-reported user
    status = http_get(cfg, "/api/v1/system/status", timeout=timeout)
    if status["ok"]:
        reported_user = (status["body"].get("result") or {}).get("user", "")
        if reported_user:
            fallback = reported_user.strip()

    # Confirm space exists in listing
    encoded = urllib.parse.quote(f"viking://{scope}", safe="")
    ls = http_get(cfg, f"/api/v1/fs/ls?uri={encoded}&output=original", timeout=timeout)
    if ls["ok"] and isinstance(ls["body"].get("result"), list):
        reserved = _USER_RESERVED if scope == "user" else _AGENT_RESERVED
        spaces = [
            e["name"] for e in ls["body"]["result"]
            if e.get("isDir") and e.get("name")
            and not e["name"].startswith(".")
            and e["name"] not in reserved
        ]
        if spaces:
            if fallback in spaces:
                _space_cache[cache_key] = fallback
                return fallback
            if scope == "user" and "default" in spaces:
                _space_cache[cache_key] = "default"
                return "default"
            if len(spaces) == 1:
                _space_cache[cache_key] = spaces[0]
                return spaces[0]

    _space_cache[cache_key] = fallback
    return fallback


def resolve_target_uri(cfg: dict, target_uri: str) -> str:
    """Resolve a short viking:// URI to its fully qualified form.

    viking://user/memories  →  viking://user/default/memories
    viking://agent/memories →  viking://agent/default/memories
    Already-qualified URIs are returned unchanged.
    """
    import re as _re
    trimmed = target_uri.strip().rstrip("/")
    m = _re.match(r"^viking://(user|agent)(?:/(.*))?$", trimmed)
    if not m:
        return trimmed
    scope = m.group(1)
    rest = (m.group(2) or "").strip()
    if not rest:
        return trimmed
    parts = [p for p in rest.split("/") if p]
    if not parts:
        return trimmed
    reserved = _USER_RESERVED if scope == "user" else _AGENT_RESERVED
    # If first part is NOT a reserved dir, the URI is already qualified
    if parts[0] not in reserved:
        return trimmed
    space = resolve_scope_space(cfg, scope)
    return f"viking://{scope}/{space}/{'/'.join(parts)}"


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def search(cfg: dict, query: str, target_uri: str, limit: int = 6, timeout: float = 8.0, score_threshold: float = 0.0) -> list:
    resolved = resolve_target_uri(cfg, target_uri)
    res = http_post(
        cfg,
        "/api/v1/search/find",
        {"query": query, "target_uri": resolved, "limit": limit, "score_threshold": score_threshold},
        timeout=timeout,
    )
    if not res["ok"]:
        return []
    body = res["body"]
    # result may be {memories: [...], skills: [...]} or {result: {memories: [...]}}
    result = body.get("result", body)
    items = []
    for bucket in ("memories", "skills"):
        items.extend(result.get(bucket, []))
    return items


def read_uri(cfg: dict, uri: str, timeout: float = 8.0) -> str | None:
    uri = resolve_target_uri(cfg, uri)
    encoded = urllib.parse.quote(uri, safe="")
    res = http_get(cfg, f"/api/v1/content/read?uri={encoded}", timeout=timeout)
    if not res["ok"]:
        return None
    body = res["body"]
    result = body.get("result", body)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("content") or result.get("text")
    return None


# ---------------------------------------------------------------------------
# Hook output helpers
# ---------------------------------------------------------------------------

def print_json(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def hook_continue() -> dict:
    return {"continue": True}


def session_start_output(additional_context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
        }
    }


def user_prompt_output(additional_context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def truncate(text: str, max_chars: int) -> str:
    text = str(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        return text[:max_chars - 3] + "..."
    return text


def project_from_cwd(cwd: str) -> str:
    name = Path(cwd or ".").name or "workspace"
    return re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:48] or "workspace"


# lazy import guard for read_uri
import urllib.parse

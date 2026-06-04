#!/usr/bin/env python3
"""
UserPromptSubmit hook — VS Code Copilot ↔ OpenViking.

Searches OpenViking for context relevant to the current prompt and injects
an <openviking-context> block before the model processes the message.

Searches across: user/memories, agent/memories, agent/skills.
Ranked items within the token budget get full abstract; remaining items
degrade to URI + score to stay within context limits.

Timeout budget: 8s (set in ov-auto-recall.json).
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(__file__))
from lib import (
    load_config,
    http_post,
    search,
    read_stdin,
    hook_continue,
    user_prompt_output,
    print_json,
    truncate,
)

RECALL_LIMIT = 6             # total items after dedup
SCORE_THRESHOLD = 0.1        # lenient server-side filter; client-side ranking limits quality
TOKEN_BUDGET_CHARS = 2000    # ~500 tokens
MAX_CONTENT_CHARS = 400
SEARCH_TIMEOUT = 6.0

STOPWORDS = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "did", "does", "is", "are", "was", "were", "the", "and", "for", "with",
    "from", "that", "this", "your", "you", "a", "an", "be", "to", "of",
}

# Strip blocks that we injected ourselves to avoid self-referential capture
_INJECTED_BLOCK_RE = re.compile(
    r"<openviking-context[\s\S]*?</openviking-context>|"
    r"<relevant-memories[\s\S]*?</relevant-memories>",
    re.IGNORECASE,
)


def clean_prompt(text: str) -> str:
    return _INJECTED_BLOCK_RE.sub("", text).strip()


def extract_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]{2,}", text.lower())
    return [t for t in tokens if t not in STOPWORDS][:12]


SOURCES = [
    ("viking://user/memories",  "memories"),
    ("viking://agent/memories", "memories"),
    ("viking://agent/skills",   "skills"),
]


def rank_items(items: list[dict], tokens: list[str]) -> list[dict]:
    """Boost items with lexical overlap with the query tokens."""
    def score(item):
        base = float(item.get("score", 0))
        abstract = (item.get("abstract") or item.get("overview") or "").lower()
        uri = (item.get("uri") or "").lower()
        haystack = f" {uri} {abstract} "
        matched = sum(1 for t in tokens[:8] if t in haystack)
        boost = min(0.15, (matched / max(len(tokens), 1)) * 0.15) if tokens else 0
        return base + boost
    return sorted(items, key=score, reverse=True)


def dedup(items: list[dict]) -> list[dict]:
    seen: set = set()
    out = []
    for item in items:
        uri = item.get("uri", "")
        abstract = (item.get("abstract") or item.get("overview") or "").strip().lower()
        key = abstract or f"uri:{uri}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main():
    inp = read_stdin()
    raw_prompt = str(inp.get("prompt") or "")
    prompt = clean_prompt(raw_prompt)

    if len(prompt.strip()) < 6:
        print_json(hook_continue())
        return

    cfg = load_config()
    query = truncate(prompt, 300)
    tokens = extract_tokens(query)

    all_items: list[dict] = []
    for target_uri, bucket in SOURCES:
        items = search(cfg, query, target_uri, limit=4, timeout=SEARCH_TIMEOUT)
        for item in items:
            item["_bucket"] = bucket
            all_items.append(item)

    if not all_items:
        print_json(hook_continue())
        return

    items = dedup(rank_items(all_items, tokens))
    items = [i for i in items if float(i.get("score", 0)) >= SCORE_THRESHOLD]
    items = items[:RECALL_LIMIT]

    if not items:
        print_json(hook_continue())
        return

    # Build injection block with token budget
    lines = [
        "<openviking-context>",
        "Relevant context from OpenViking. Use mcp_openviking_read to expand any URI.",
    ]
    budget = TOKEN_BUDGET_CHARS

    for item in items:
        uri = item.get("uri", "")
        score = float(item.get("score", 0))
        abstract = (item.get("abstract") or item.get("overview") or "").strip()

        if budget > 0 and abstract:
            content = truncate(abstract, MAX_CONTENT_CHARS)
            line = f"- {content} [{uri}] (score {score:.2f})"
            budget -= len(line)
        else:
            line = f"- [{uri}] (score {score:.2f})"

        lines.append(line)

    lines.append("</openviking-context>")
    block = "\n".join(lines)

    print_json(user_prompt_output(block))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print_json(hook_continue())

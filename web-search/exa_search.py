#!/usr/bin/env python3
"""Exa semantic search wrapper for web-search skill.

Exa provides neural/semantic search that understands intent better than
keyword-based search. Use for discovery queries like "best standing desk
for programmers" where semantic understanding matters.

Usage:
    python3 exa_search.py --query "best ergonomic chair for back pain" --limit 10
    python3 exa_search.py --query "..." --limit 5 --format json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


def _post_json(*, url: str, headers: dict[str, str], payload: dict, timeout_s: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return json.loads(resp.read().decode(charset, errors="replace"))
    except urllib.error.HTTPError as e:
        charset = getattr(e.headers, "get_content_charset", lambda: "utf-8")() or "utf-8"
        body_text = e.read().decode(charset, errors="replace")[:800] if e.fp else ""
        return {"__error__": {"code": e.code, "body": body_text}}


def search_exa(query: str, num_results: int = 10, use_autoprompt: bool = True, include_text: bool = True) -> dict:
    """Search Exa API with neural/semantic search."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return {"__error__": {"code": 0, "body": "EXA_API_KEY not set in environment"}}

    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "type": "auto",  # neural + keyword hybrid
    }
    if include_text:
        payload["contents"] = {"text": {"maxCharacters": 3000}}

    return _post_json(
        url="https://api.exa.ai/search",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        payload=payload,
    )


def format_markdown(results: dict, start_id: int = 1) -> str:
    """Format Exa results as markdown source cards (Exx format)."""
    if "__error__" in results:
        err = results["__error__"]
        return f"**Error:** HTTP {err.get('code', '?')} — {err.get('body', 'Unknown error')}"

    lines = ["## Exa Search Results\n"]
    for i, result in enumerate(results.get("results", []), start_id):
        title = result.get("title", "Untitled")
        url = result.get("url", "N/A")
        score = result.get("score")
        text = result.get("text", "")

        lines.append(f"**E{i:02d} — {title}**")
        lines.append(f"- URL: {url}")
        if score is not None:
            lines.append(f"- Score: {score:.3f}")
        if text:
            snippet = text[:600].replace("\n", " ").strip()
            if len(text) > 600:
                snippet += "..."
            lines.append(f"- Snippet: {snippet}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exa semantic search for web-search")
    parser.add_argument("--query", required=True, help="Search query (semantic)")
    parser.add_argument("--limit", type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    parser.add_argument("--start-id", type=int, default=1, help="Starting ID for Exx numbering")
    parser.add_argument("--no-text", action="store_true", help="Skip fetching text content")
    args = parser.parse_args()

    results = search_exa(args.query, args.limit, include_text=not args.no_text)

    if "__error__" in results:
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            print(format_markdown(results))
        return 1

    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_markdown(results, args.start_id))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

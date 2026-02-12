#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"


def _request_json(*, url: str, api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "User-Agent": "WebSearchFirecrawl/1.0",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def _coerce_results(data: dict) -> list[dict]:
    if isinstance(data.get("data"), dict) and isinstance(data["data"].get("results"), list):
        return data["data"]["results"]
    if isinstance(data.get("results"), list):
        return data["results"]
    if isinstance(data.get("data"), list):
        return data["data"]
    return []


def _to_md(results: list[dict]) -> str:
    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        title = (r.get("title") or r.get("name") or "—").strip()
        url = (r.get("url") or r.get("link") or "").strip()
        snippet = (r.get("snippet") or r.get("description") or "").strip()
        if url:
            lines.append(f"{i}. {title}\n   - <{url}>")
            if snippet:
                lines.append(f"   - {snippet}")
        else:
            lines.append(f"{i}. {title}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Firecrawl-backed web search (writes markdown or JSON).")
    parser.add_argument("--query", required=True, help="Search query.")
    parser.add_argument("--limit", type=int, default=10, help="Max results (best-effort).")
    parser.add_argument("--lang", default="", help="Language hint (optional, e.g., en, ja).")
    parser.add_argument("--country", default="", help="Country hint (optional, e.g., US, JP).")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    args = parser.parse_args()

    api_key = os.getenv("FIRECRAWL_API_KEY") or ""
    if not api_key:
        print("Missing FIRECRAWL_API_KEY in environment.", file=sys.stderr)
        return 2

    payload: dict = {"query": args.query, "limit": max(1, min(args.limit, 50))}
    if args.lang:
        payload["lang"] = args.lang
    if args.country:
        payload["country"] = args.country

    try:
        data = _request_json(url=FIRECRAWL_SEARCH_URL, api_key=api_key, payload=payload)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        print(f"HTTP {e.code} from Firecrawl: {body[:500]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Firecrawl request failed: {e}", file=sys.stderr)
        return 1

    results = _coerce_results(data)
    if args.format == "json":
        json.dump({"query": args.query, "results": results}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(_to_md(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

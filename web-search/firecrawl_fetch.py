#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"


def _is_reddit_url(url: str) -> bool:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host.endswith("reddit.com") or host.endswith("redd.it")


def _post_json(*, url: str, api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "User-Agent": "WebSearchFirecrawl/1.0",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def _coerce_scrape(data: dict) -> dict:
    if isinstance(data.get("data"), dict):
        return data["data"]
    return data


def _coerce_markdown(scrape: dict) -> str:
    for key in ("markdown", "md", "content", "text"):
        val = scrape.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # Some responses nest content further (best-effort)
    meta = scrape.get("data")
    if isinstance(meta, dict):
        for key in ("markdown", "content", "text"):
            val = meta.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _coerce_title(scrape: dict) -> str:
    meta = scrape.get("metadata")
    if isinstance(meta, dict):
        title = meta.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    title = scrape.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "—"


def _truncate(text: str, n: int) -> str:
    if n <= 0:
        return text
    if len(text) <= n:
        return text
    return text[: max(0, n - 1)].rstrip() + "…"


def _read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Firecrawl-backed fetching (best-effort scrape to markdown or JSON)."
    )
    parser.add_argument("--url", action="append", default=[], help="URL to fetch (repeatable).")
    parser.add_argument("--urls-file", default="", help="Text file: one URL per line (optional).")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Max chars per page in md output (default: 6000, 0 = unlimited).",
    )
    args = parser.parse_args()

    api_key = os.getenv("FIRECRAWL_API_KEY") or ""
    if not api_key:
        print("Missing FIRECRAWL_API_KEY in environment.", file=sys.stderr)
        return 2

    urls: list[str] = []
    if args.urls_file:
        urls.extend(_read_lines(args.urls_file))
    urls.extend([u.strip() for u in args.url if u.strip()])
    urls = list(dict.fromkeys(urls))
    if not urls:
        print("Provide --url and/or --urls-file", file=sys.stderr)
        return 2

    results: list[dict] = []
    for u in urls:
        url = u.strip()
        if _is_reddit_url(url):
            results.append(
                {
                    "url": url,
                    "ok": False,
                    "error": "Skipped: reddit.com is blocked/unreliable via Firecrawl. Use reddit_search.py instead.",
                }
            )
            continue
        payload = {
            "url": url,
            "formats": ["markdown"],
        }
        try:
            raw = _post_json(url=FIRECRAWL_SCRAPE_URL, api_key=api_key, payload=payload)
            scrape = _coerce_scrape(raw if isinstance(raw, dict) else {})
            md = _coerce_markdown(scrape)
            results.append(
                {
                    "url": url,
                    "title": _coerce_title(scrape),
                    "markdown": md,
                    "ok": bool(md),
                }
            )
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            results.append({"url": url, "ok": False, "error": f"HTTP {e.code}: {body[:500]}"})
        except Exception as e:
            results.append({"url": url, "ok": False, "error": str(e)})

    if args.format == "json":
        json.dump({"results": results}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    out_lines: list[str] = []
    for i, r in enumerate(results, start=1):
        title = r.get("title") or "—"
        url = r.get("url") or "—"
        ok = bool(r.get("ok"))
        out_lines.append(f"## {i}. {title}\n- <{url}>\n- Status: {'ok' if ok else 'error'}")
        if not ok:
            err = (r.get("error") or "").strip()
            if err:
                out_lines.append(f"- Error: {err}")
            out_lines.append("")
            continue
        md = str(r.get("markdown") or "").strip()
        if args.max_chars >= 0:
            md = _truncate(md, int(args.max_chars))
        out_lines.append("")
        out_lines.append(md if md else "(empty)")
        out_lines.append("")

    sys.stdout.write("\n".join(out_lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

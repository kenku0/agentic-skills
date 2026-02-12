#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import json
import os
import sys
from typing import Optional
import urllib.parse
import urllib.request


def read_env_file(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    out: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in out:
                out[key] = value
    return out


def getenv_with_dotenv(key: str, dotenv_path: str) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return val
    dotenv = read_env_file(dotenv_path)
    val = dotenv.get(key)
    return val or None


def http_json(
    *,
    method: str,
    url: str,
    headers: Optional[dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout_s: int = 20,
) -> dict:
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset, errors="replace")
        return json.loads(body)


def get_reddit_access_token(*, client_id: str, client_secret: str, user_agent: str) -> str:
    token_url = "https://www.reddit.com/api/v1/access_token"
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    payload = http_json(method="POST", url=token_url, headers=headers, data=data)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Failed to get access token: {payload}")
    return str(token)


def search_reddit(
    *,
    token: str,
    user_agent: str,
    query: str,
    limit: int,
    sort: str,
    time_filter: str,
    subreddit: Optional[str],
) -> list[dict]:
    base = "https://oauth.reddit.com"
    path = f"/r/{subreddit}/search" if subreddit else "/search"
    params = {
        "q": query,
        "limit": str(limit),
        "sort": sort,
        "t": time_filter,
        "type": "link",
        "raw_json": "1",
    }
    if subreddit:
        params["restrict_sr"] = "1"
    url = base + path + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    headers = {"Authorization": f"bearer {token}", "User-Agent": user_agent}
    payload = http_json(method="GET", url=url, headers=headers)
    children = (payload.get("data") or {}).get("children") or []
    out: list[dict] = []
    for child in children:
        data = (child or {}).get("data") or {}
        out.append(data)
    return out


def fetch_top_comments(
    *,
    token: str,
    user_agent: str,
    post_id: str,
    limit: int,
    sort: str,
) -> list[dict]:
    url = (
        "https://oauth.reddit.com/comments/"
        + urllib.parse.quote(post_id)
        + "?"
        + urllib.parse.urlencode(
            {
                "limit": str(limit),
                "sort": sort,
                "raw_json": "1",
            },
            quote_via=urllib.parse.quote,
        )
    )
    headers = {"Authorization": f"bearer {token}", "User-Agent": user_agent}
    payload = http_json(method="GET", url=url, headers=headers, timeout_s=25)
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    comments_listing = payload[1] or {}
    children = ((comments_listing.get("data") or {}).get("children") or []) if isinstance(comments_listing, dict) else []
    out: list[dict] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("kind") != "t1":
            continue
        data = child.get("data") or {}
        if not isinstance(data, dict):
            continue
        body = (data.get("body") or "").strip()
        if not body or body in {"[deleted]", "[removed]"}:
            continue
        out.append(data)
    return out


def _truncate(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: max(0, n - 1)].rstrip() + "…"


def to_md_rows(
    posts: list[dict],
    *,
    include_comments: bool,
    token: str,
    user_agent: str,
    comments_limit: int,
    comments_sort: str,
) -> str:
    lines: list[str] = []
    for idx, p in enumerate(posts, start=1):
        title = (p.get("title") or "").strip()
        subreddit = p.get("subreddit") or "—"
        score = p.get("score")
        comments = p.get("num_comments")
        created_utc = p.get("created_utc")
        permalink = p.get("permalink") or ""
        url = "https://www.reddit.com" + permalink if permalink.startswith("/") else (p.get("url") or "")
        created = "—"
        if isinstance(created_utc, (int, float)):
            created = dt.datetime.utcfromtimestamp(created_utc).date().isoformat()
        meta = f"r/{subreddit} · score {score} · {comments} comments · {created}"
        lines.append(f"{idx}. {title}\n   - {meta}\n   - <{url}>")
        if include_comments:
            post_id = str(p.get("id") or "").strip()
            if not post_id:
                continue
            try:
                top_comments = fetch_top_comments(
                    token=token,
                    user_agent=user_agent,
                    post_id=post_id,
                    limit=comments_limit,
                    sort=comments_sort,
                )
            except Exception:
                top_comments = []
            if top_comments:
                lines.append("   - Top comments (best-effort):")
                for c in top_comments[:comments_limit]:
                    author = c.get("author") or "—"
                    c_score = c.get("score")
                    body = _truncate(str(c.get("body") or ""), 240)
                    c_permalink = c.get("permalink") or ""
                    c_url = (
                        "https://www.reddit.com" + c_permalink
                        if isinstance(c_permalink, str) and c_permalink.startswith("/")
                        else ""
                    )
                    if c_url:
                        lines.append(f"     - {c_score} · u/{author}: {body}\n       - <{c_url}>")
                    else:
                        lines.append(f"     - {c_score} · u/{author}: {body}")
    return "\n".join(lines).rstrip() + "\n"


def _to_json_with_optional_comments(
    posts: list[dict],
    *,
    include_comments: bool,
    token: str,
    user_agent: str,
    comments_limit: int,
    comments_sort: str,
) -> list[dict]:
    if not include_comments:
        return posts
    out: list[dict] = []
    for p in posts:
        if not isinstance(p, dict):
            continue
        post_id = str(p.get("id") or "").strip()
        enriched = dict(p)
        if post_id:
            try:
                top_comments = fetch_top_comments(
                    token=token,
                    user_agent=user_agent,
                    post_id=post_id,
                    limit=comments_limit,
                    sort=comments_sort,
                )
                enriched["__top_comments"] = [
                    {
                        "score": c.get("score"),
                        "author": c.get("author"),
                        "body": c.get("body"),
                        "permalink": c.get("permalink"),
                    }
                    for c in top_comments[:comments_limit]
                    if isinstance(c, dict)
                ]
            except Exception:
                enriched["__top_comments"] = []
        out.append(enriched)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Reddit via the official API (client_credentials).")
    parser.add_argument("--query", required=True, help="Search query string (e.g., 'best electric toothbrush').")
    parser.add_argument("--subreddit", action="append", help="Restrict search to a subreddit (repeatable).")
    parser.add_argument("--limit", type=int, default=15, help="Results per search (max 100).")
    parser.add_argument("--sort", default="relevance", choices=["relevance", "hot", "top", "new", "comments"])
    parser.add_argument("--time", default="all", choices=["all", "year", "month", "week", "day", "hour"])
    parser.add_argument(
        "--comments",
        action="store_true",
        help="Best-effort: also fetch top comments for each returned thread (extra network calls).",
    )
    parser.add_argument("--comments-limit", type=int, default=5, help="Top-level comments per thread (default: 5).")
    parser.add_argument(
        "--comments-sort",
        default="top",
        choices=["top", "best", "new", "controversial", "old", "qa"],
        help="Comment sort order (default: top).",
    )
    parser.add_argument("--format", default="md", choices=["md", "json"])
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Path to .env (defaults to repo-root .env). Values are used only if env vars are unset.",
    )
    args = parser.parse_args()

    dotenv_path = os.path.abspath(args.dotenv)
    client_id = getenv_with_dotenv("REDDIT_CLIENT_ID", dotenv_path)
    client_secret = getenv_with_dotenv("REDDIT_CLIENT_SECRET", dotenv_path)
    user_agent = getenv_with_dotenv("REDDIT_USER_AGENT", dotenv_path) or "WebSearchReddit/1.0 (contact: local)"

    if not client_id or not client_secret:
        print(
            "Missing REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET. Add them to your environment or .env and retry.",
            file=sys.stderr,
        )
        return 2

    limit = max(1, min(int(args.limit), 100))
    comments_limit = max(1, min(int(args.comments_limit), 25))
    token = get_reddit_access_token(client_id=client_id, client_secret=client_secret, user_agent=user_agent)

    posts: list[dict] = []
    if args.subreddit:
        for sr in args.subreddit:
            posts.extend(
                search_reddit(
                    token=token,
                    user_agent=user_agent,
                    query=args.query,
                    limit=limit,
                    sort=args.sort,
                    time_filter=args.time,
                    subreddit=sr.strip(),
                )
            )
    else:
        posts = search_reddit(
            token=token,
            user_agent=user_agent,
            query=args.query,
            limit=limit,
            sort=args.sort,
            time_filter=args.time,
            subreddit=None,
        )

    if args.format == "json":
        json.dump(
            _to_json_with_optional_comments(
                posts,
                include_comments=bool(args.comments),
                token=token,
                user_agent=user_agent,
                comments_limit=comments_limit,
                comments_sort=str(args.comments_sort),
            ),
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(
        to_md_rows(
            posts,
            include_comments=bool(args.comments),
            token=token,
            user_agent=user_agent,
            comments_limit=comments_limit,
            comments_sort=str(args.comments_sort),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

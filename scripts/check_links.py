#!/usr/bin/env python3
"""
Guard against silently-dead README assets.

Every image and link in the README is fetched and its status recorded.
This exists because free rendering services routinely disappear -- a
Vercel project hitting its billing cap starts answering 402, a Heroku
dyno stops existing -- and the profile it was embedded in keeps serving
broken images to every visitor, indefinitely, without any signal.

Exit codes:
    0  every asset resolved
    1  at least one asset is dead

Usage:
    python3 check_links.py README.md
    python3 check_links.py README.md --warn-only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; readme-link-check/1.0)"

# Markdown images/links plus raw HTML src attributes.
PATTERNS = (
    re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)"),
    re.compile(r"(?<!!)\[[^\]]*\]\((https?://[^)\s]+)"),
    re.compile(r'(?:src|srcset)="(https?://[^"\s]+)"'),
)

# Hosts that reject HEAD/robotic traffic but are known good.
SKIP = ("linkedin.com", "twitter.com", "x.com")


# A commented-out section is still full of src="..." attributes. Without this
# the checker probes assets the page does not actually reference and reports
# them as dead, which trains you to ignore its output.
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def extract(path: str) -> list[str]:
    body = COMMENT_RE.sub("", open(path, encoding="utf-8").read())
    urls: list[str] = []
    for pattern in PATTERNS:
        urls.extend(pattern.findall(body))
    seen: dict[str, None] = {}
    for u in urls:
        seen.setdefault(u.rstrip(".,);"), None)
    return list(seen)


def probe(url: str) -> tuple[str, int, str]:
    if any(host in url for host in SKIP):
        return url, 0, "skipped"
    # URLs may carry non-ASCII characters (a typographic hyphen, an emoji in
    # a query string); urllib demands they be percent-encoded first.
    safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    req = urllib.request.Request(safe, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            size = len(resp.read(2048))
            # A 200 that returns nothing is still a broken image.
            return url, resp.status, "ok" if size else "empty body"
    except urllib.error.HTTPError as exc:
        return url, exc.code, exc.reason
    except Exception as exc:  # noqa: BLE001
        return url, -1, type(exc).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("readme", nargs="?", default="README.md")
    ap.add_argument("--warn-only", action="store_true")
    args = ap.parse_args()

    urls = extract(args.readme)
    if not urls:
        print("no external assets found")
        return 0

    print(f"checking {len(urls)} assets in {args.readme}\n")
    dead: list[tuple[str, int, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for url, status, note in pool.map(probe, urls):
            healthy = status in (200, 0) and note in ("ok", "skipped")
            mark = "PASS" if healthy else "DEAD"
            print(f"  [{mark}] {status:>4}  {url[:96]}  ({note})")
            if not healthy:
                dead.append((url, status, note))

    print()
    if dead:
        print(f"{len(dead)} dead asset(s):")
        for url, status, note in dead:
            print(f"  {status} {note} -- {url}")
        if args.warn_only:
            print("\n--warn-only set; not failing the build")
            return 0
        return 1

    print("all assets healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

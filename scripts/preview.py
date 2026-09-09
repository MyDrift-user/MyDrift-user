#!/usr/bin/env python3
"""
Render README.md exactly as GitHub will, locally, without publishing anything.

Three things a generic Markdown previewer gets wrong for this file:

  1. Mermaid. GitHub's markdown API returns the diagram as syntax-highlighted
     markup, not a rendered diagram. This re-inflates it and runs mermaid.js.
  2. <picture> theme switching. Browsers honour the real OS setting, so you
     cannot see both themes. This rewires the elements from a toggle.
  3. Assets on the `output` branch do not exist until CI has run once, so every
     generated image 404s. Local files in assets/ are substituted where present.

Usage:
    python3 scripts/preview.py              # build and serve on :8000
    python3 scripts/preview.py --port 9000
    python3 scripts/preview.py --no-serve   # just write preview.html
"""

from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import os
import re
import socketserver
import sys
import urllib.error
import urllib.request
import webbrowser

OWNER = "MyDrift-user"
OUTPUT_BRANCH_RE = re.compile(
    r"https://raw\.githubusercontent\.com/[^/]+/[^/]+/output/([\w.-]+\.svg)"
)


def to_github_html(markdown: str) -> str:
    """GitHub's own renderer, so the output matches the real page.

    Mode is "markdown", not "gfm": "gfm" is the *comment* renderer, which turns
    a single newline into a <br>. Repository files reflow soft line breaks, so
    "gfm" would show every hand-wrapped paragraph broken at the source's own
    line endings -- a preview that lies about the thing it is previewing.
    """
    body = json.dumps({"text": markdown, "mode": "gfm"}).encode()
    req = urllib.request.Request(
        "https://api.github.com/markdown",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "readme-preview",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise SystemExit(
                "GitHub's markdown API rate-limited this address "
                "(60 requests/hour unauthenticated).\n"
                "Set GITHUB_TOKEN to raise the limit to 5000/hour:\n"
                "  GITHUB_TOKEN=$(gh auth token) python3 scripts/preview.py"
            ) from exc
        raise


def revive_mermaid(page: str) -> str:
    """
    Turn GitHub's highlighted mermaid markup back into a live diagram.

    The API hands back <div class="highlight highlight-source-mermaid"> with the
    source wrapped in <span> tokens. mermaid.js needs the plain text, so the
    tags come out and the entities are unescaped.
    """
    pattern = re.compile(
        r'<div class="highlight highlight-source-mermaid">.*?</div>', re.S
    )

    def replace(match: re.Match[str]) -> str:
        inner = match.group(0)
        inner = re.sub(r"<br\s*/?>", "\n", inner)
        source = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        return f'<pre class="mermaid">{html.escape(source)}</pre>'

    return pattern.sub(replace, page)


def localise_assets(page: str, assets_dir: str) -> tuple[str, list[str], list[str]]:
    """Point output-branch URLs at local files when those files exist."""
    found: list[str] = []
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if os.path.exists(os.path.join(assets_dir, name)):
            found.append(name)
            return f"{assets_dir}/{name}"
        missing.append(name)
        return match.group(0)

    return OUTPUT_BRANCH_RE.sub(replace, page), found, missing


SHELL = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Profile README preview</title>
<!-- Two fixed-theme sheets rather than the auto-switching build: the combined
     stylesheet keys off the OS preference, which the in-page toggle cannot
     override. These are enabled and disabled directly instead. -->
<link id="css-light" rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-light.min.css">
<link id="css-dark" rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-dark.min.css">
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; background: var(--bg); transition: background .15s; }}
  body[data-theme="light"] {{ --bg: #ffffff; }}
  body[data-theme="dark"]  {{ --bg: #0d1117; }}
  .bar {{
    position: sticky; top: 0; z-index: 20; display: flex; gap: 14px;
    align-items: center; padding: 10px 18px; font: 13px/1.4 ui-monospace,
    SFMono-Regular, Consolas, monospace; border-bottom: 1px solid #30363d;
    background: #161b22; color: #e6edf3;
  }}
  .bar button {{
    font: inherit; cursor: pointer; border-radius: 6px; padding: 5px 12px;
    border: 1px solid #30363d; background: #21262d; color: #e6edf3;
  }}
  .bar button[aria-pressed="true"] {{ background: #1f6feb; border-color: #1f6feb; }}
  .note {{ margin-left: auto; opacity: .75; }}
  .wrap {{ max-width: 1012px; margin: 0 auto; padding: 32px 16px 80px; }}
  .markdown-body {{ padding: 34px; border-radius: 8px; border: 1px solid #30363d; }}
  body[data-theme="dark"]  .markdown-body {{ background: #0d1117; }}
  body[data-theme="light"] .markdown-body {{ background: #ffffff; }}
  body[data-theme="light"] {{ --bg: #eaeef2; }}
</style>

<div class="bar">
  <span>preview</span>
  <button id="light" aria-pressed="false">light</button>
  <button id="dark"  aria-pressed="true">dark</button>
  <span class="note">{note}</span>
</div>
<div class="wrap"><article class="markdown-body">{body}</article></div>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

  // Snapshot each <picture> before touching it: once a <source> is removed the
  // original candidates are gone, so the other theme could not be restored.
  const pictures = [...document.querySelectorAll("picture")].map(p => ({{
    el: p,
    img: p.querySelector("img"),
    sources: [...p.querySelectorAll("source")].map(s => ({{
      media: s.getAttribute("media") || "",
      srcset: s.getAttribute("srcset") || "",
    }})),
  }}));

  function applyTheme(theme) {{
    document.body.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.getElementById("css-dark").disabled  = theme !== "dark";
    document.getElementById("css-light").disabled = theme !== "light";
    document.getElementById("dark").ariaPressed = String(theme === "dark");
    document.getElementById("light").ariaPressed = String(theme === "light");

    // <picture> resolves against the real OS preference, and a matching
    // <source> outranks the <img>'s own src -- so assigning img.src alone is
    // silently ignored. Rewrite each source's media query instead: "all" for
    // the chosen theme, "not all" for the rest, which forces re-selection.
    for (const p of pictures) {{
      const live = [...p.el.querySelectorAll("source")];
      live.forEach((node, i) => {{
        const original = p.sources[i];
        node.media = original.media.includes(theme) ? "all" : "not all";
      }});
      const hit = p.sources.find(s => s.media.includes(theme));
      if (hit && p.img) p.img.src = hit.srcset;
    }}

    mermaid.initialize({{
      startOnLoad: false,
      theme: theme === "dark" ? "dark" : "default",
    }});
    for (const node of document.querySelectorAll("pre.mermaid")) {{
      node.removeAttribute("data-processed");
      if (node.dataset.src) node.textContent = node.dataset.src;
      else node.dataset.src = node.textContent;
    }}
    mermaid.run({{ querySelector: "pre.mermaid" }});
  }}

  document.getElementById("dark").onclick  = () => applyTheme("dark");
  document.getElementById("light").onclick = () => applyTheme("light");

  // #light / #dark in the URL selects a theme up front, so a headless
  // screenshot (or a shared link) can target one without clicking.
  const requested = location.hash.replace("#", "");
  applyTheme(requested === "light" ? "light" : "dark");
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("readme", nargs="?", default="README.md")
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-serve", action="store_true")
    ap.add_argument("--out", default="preview.html")
    args = ap.parse_args()

    markdown = open(args.readme, encoding="utf-8").read()
    print(f"rendering {args.readme} through GitHub's markdown API ...")
    page = revive_mermaid(to_github_html(markdown))
    page, found, missing = localise_assets(page, args.assets)

    note = f"{len(found)} asset(s) served locally"
    if missing:
        note += f" &middot; {len(set(missing))} not generated yet"

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(SHELL.format(body=page, note=note))

    print(f"wrote {args.out}")
    for name in sorted(set(found)):
        print(f"  local   {name}")
    for name in sorted(set(missing)):
        print(f"  MISSING {name}  (run generate.yml, or gen_dashboard.py)")

    if args.no_serve:
        return 0

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=os.getcwd()
    )
    socketserver.TCPServer.allow_address_reuse = True
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/{args.out}"
        print(f"\nserving {url}   (ctrl-c to stop)")
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - headless is fine
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

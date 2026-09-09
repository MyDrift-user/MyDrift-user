#!/usr/bin/env python3
"""
Self-hosted GitHub profile dashboard renderer.

Fetches account statistics from the GitHub API and renders them as a
hand-built, animated SVG card. No third-party rendering service is
involved, so the resulting image cannot break because someone else's
free hosting tier ran out of quota.

Standard library only -- no pip install step in CI.

Usage:
    GITHUB_TOKEN=... python3 gen_dashboard.py --user MyDrift-user --out assets
    python3 gen_dashboard.py --user MyDrift-user --out assets --demo
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.error
import urllib.request
from html import escape
from typing import Any

API = "https://api.github.com"
UA = "mydrift-profile-dashboard"

# GitHub linguist colours. Only consulted when the API does not supply one
# (the REST fallback carries no colour field); GraphQL values win where present.
LANG_COLOURS: dict[str, str] = {
    "Rust": "#dea584", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Python": "#3572A5", "C#": "#178600", "C": "#555555", "C++": "#f34b7d",
    "Go": "#00ADD8", "Shell": "#89e051", "PowerShell": "#012456",
    "Nix": "#7e7eff", "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c",
    "Java": "#b07219", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "Ruby": "#701516", "PHP": "#4F5D95", "Lua": "#000080",
    "Dockerfile": "#384d54", "Makefile": "#427819", "Vue": "#41b883",
    "Svelte": "#ff3e00", "Astro": "#ff5a03", "Zig": "#ec915c",
    "Batchfile": "#C1F12E", "Inno Setup": "#264b99", "Vim Script": "#199f4b",
    "Nushell": "#4E9906", "SQL": "#e38c00", "Markdown": "#083fa1",
}

DEFAULT_LANG_COLOUR = "#8b949e"


# --------------------------------------------------------------------------
# themes
# --------------------------------------------------------------------------

THEMES: dict[str, dict[str, str]] = {
    # Chrome is monochrome on purpose. Hue is reserved for values that carry
    # information -- language proportions, contribution intensity, tech marks --
    # so colour on the page always means something. A decorative two-stop
    # gradient across every border is the fastest way to make a layout look
    # generated rather than designed.
    "dark": {
        "bg": "#0d1117",
        "panel": "#11161d",
        "line": "#21262d",
        "grid": "#161b22",
        "text": "#e6edf3",
        "muted": "#7d8590",
        "accent": "#58a6ff",
        "heat": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fa",
        "line": "#d8dee4",
        "grid": "#eef1f4",
        "text": "#1f2328",
        "muted": "#59636e",
        "accent": "#0969da",
        "heat": ["#ebedf0", "#aceebb", "#4ac26b", "#2da44e", "#116329"],
    },
}

# --------------------------------------------------------------------------
# data acquisition
# --------------------------------------------------------------------------


def _request(url: str, token: str | None, data: bytes | None = None) -> Any:
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


GQL = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    followers { totalCount }
    following { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_graphql(user: str, token: str) -> dict[str, Any]:
    """One round trip for everything, including the contribution calendar."""
    body = json.dumps({"query": GQL, "variables": {"login": user}}).encode()
    payload = _request("https://api.github.com/graphql", token, body)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]

    langs: dict[str, dict[str, Any]] = {}
    stars = forks = 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        forks += repo["forkCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            slot = langs.setdefault(
                name,
                {"size": 0,
                 "color": edge["node"]["color"]
                 or LANG_COLOURS.get(name, DEFAULT_LANG_COLOUR)},
            )
            slot["size"] += edge["size"]

    repos: list[dict[str, Any]] = []
    for repo in u["repositories"]["nodes"]:
        edges = repo["languages"]["edges"]
        top = edges[0]["node"] if edges else None
        repos.append({
            "name": repo["name"],
            "stars": repo["stargazerCount"],
            "forks": repo["forkCount"],
            "lang": top["name"] if top else "",
            "colour": (top and (top["color"] or LANG_COLOURS.get(top["name"])))
                      or DEFAULT_LANG_COLOUR,
        })

    days: list[tuple[str, int]] = []
    for week in cc["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))

    return {
        "name": u["name"] or u["login"],
        "login": u["login"],
        "created": u["createdAt"][:10],
        "followers": u["followers"]["totalCount"],
        "following": u["following"]["totalCount"],
        "commits": cc["totalCommitContributions"]
        + cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "repos": u["repositories"]["totalCount"],
        "stars": stars,
        "forks": forks,
        "langs": langs,
        "days": days,
        "repos_detail": repos,
    }


def fetch_rest(user: str, token: str | None) -> dict[str, Any]:
    """Fallback path. No calendar -- REST does not expose contributions."""
    u = _request(f"{API}/users/{user}", token)
    repos = _request(f"{API}/users/{user}/repos?per_page=100&type=owner", token)
    langs: dict[str, dict[str, Any]] = {}
    detail: list[dict[str, Any]] = []
    stars = forks = 0
    for repo in repos:
        if repo["fork"]:
            continue
        detail.append({
            "name": repo["name"],
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "lang": repo["language"] or "",
            "colour": LANG_COLOURS.get(repo["language"] or "", DEFAULT_LANG_COLOUR),
        })
        stars += repo["stargazers_count"]
        forks += repo["forks_count"]
        try:
            for name, size in _request(repo["languages_url"], token).items():
                slot = langs.setdefault(
                    name,
                    {"size": 0,
                     "color": LANG_COLOURS.get(name, DEFAULT_LANG_COLOUR)},
                )
                slot["size"] += size
        except urllib.error.HTTPError:
            pass
    return {
        "name": u["name"] or u["login"],
        "login": u["login"],
        "created": u["created_at"][:10],
        "followers": u["followers"],
        "following": u["following"],
        "commits": 0,
        "prs": 0,
        "issues": 0,
        "reviews": 0,
        "contributions": 0,
        "repos": u["public_repos"],
        "stars": stars,
        "forks": forks,
        "langs": langs,
        "days": [],
        "repos_detail": detail,
    }


def demo_data(user: str) -> dict[str, Any]:
    """Deterministic synthetic data, so layout can be verified offline."""
    rng = random.Random(1337)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    days = []
    for i in range(365):
        d = start + dt.timedelta(days=i)
        weekend = d.weekday() >= 5
        n = rng.choice([0, 0, 1, 2, 3, 5, 8, 13]) // (3 if weekend else 1)
        days.append((d.isoformat(), n))
    return {
        "name": "MyDrift",
        "login": user,
        "created": "2023-01-02",
        "followers": 76,
        "following": 27,
        "commits": 1284,
        "prs": 63,
        "issues": 41,
        "reviews": 28,
        "contributions": sum(n for _, n in days),
        "repos": 15,
        "stars": 4,
        "forks": 2,
        "langs": {
            "TypeScript": {"size": 412000, "color": "#3178c6"},
            "Rust": {"size": 288000, "color": "#dea584"},
            "C#": {"size": 201000, "color": "#178600"},
            "PowerShell": {"size": 152000, "color": "#012456"},
            "JavaScript": {"size": 121000, "color": "#f1e05a"},
            "Nix": {"size": 64000, "color": "#7e7eff"},
        },
        "days": days,
        "repos_detail": [
            {"name": "runesh", "stars": 0, "forks": 0, "lang": "Rust",
             "colour": "#dea584"},
            {"name": "ngx-dwex", "stars": 1, "forks": 0, "lang": "TypeScript",
             "colour": "#3178c6"},
            {"name": "RF-Dex", "stars": 2, "forks": 0, "lang": "C#",
             "colour": "#178600"},
            {"name": "ShadowRoute", "stars": 0, "forks": 0, "lang": "JavaScript",
             "colour": "#f1e05a"},
            {"name": "IridiumTasks", "stars": 0, "forks": 0, "lang": "JavaScript",
             "colour": "#f1e05a"},
            {"name": "NixIT", "stars": 0, "forks": 0, "lang": "Nix",
             "colour": "#7e7eff"},
        ],
    }


# --------------------------------------------------------------------------
# svg helpers
# --------------------------------------------------------------------------


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def text(x, y, s, *, fill, size=13, weight=400, anchor="start",
         family="ui-monospace, 'SFMono-Regular', 'JetBrains Mono', Consolas, monospace",
         opacity=1.0, extra=""):
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" font-family="{family}" '
        f'opacity="{opacity}"{extra}>{escape(str(s))}</text>'
    )


# --------------------------------------------------------------------------
# projects renderer
# --------------------------------------------------------------------------

# Order is editorial; stars, forks and language come from the API at build time.
# The blurbs are deliberately short -- a card grid is scanned, not read, and a
# two-line paragraph per project turns six cards back into the wall of text the
# grid was meant to replace.
FEATURED: list[tuple[str, str]] = [
    ("runesh", "type-safe bridge, Rust to Next.js"),
    ("ngx-dwex", "Angular workspace shell on Material M3"),
    ("RF-Dex", "screen-wide red filter, one keypress"),
    ("ShadowRoute", "redirects before the request leaves"),
    ("IridiumTasks", "kanban board in the browser sidebar"),
    ("NixIT", "declarative machines, rebuild as docs"),
]

PW = 900


def clip(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "\u2026"


def render_projects(d: dict[str, Any], theme_name: str) -> str:
    """A scannable card grid: three columns, two rows, live repository stats."""
    t = THEMES[theme_name]
    o: list[str] = []
    add = o.append

    by_name = {r["name"].lower(): r for r in d.get("repos_detail", [])}

    pad, gap = 26, 12
    cols, card_h = 3, 92
    card_w = (PW - pad * 2 - gap * (cols - 1)) / cols
    rows = (len(FEATURED) + cols - 1) // cols
    top = pad + 24
    height = top + rows * card_h + (rows - 1) * gap + pad

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PW}" height="{height:.0f}" '
        f'viewBox="0 0 {PW} {height:.0f}" role="img" aria-label="Selected projects">'
    )
    add("<defs>")
    add(
        f'<pattern id="pgrid" width="30" height="30" patternUnits="userSpaceOnUse">'
        f'<path d="M30 0H0V30" fill="none" stroke="{t["grid"]}" stroke-width="1"/>'
        f"</pattern>"
    )
    add("</defs>")
    add(
        "<style>"
        "@keyframes pin{from{opacity:0;transform:translateY(8px)}"
        "to{opacity:1;transform:translateY(0)}}"
        ".p{animation:pin .5s cubic-bezier(.22,1,.36,1) both}"
        "@media(prefers-reduced-motion:reduce){.p{animation:none;opacity:1;"
        "transform:none}}"
        "</style>"
    )
    add(f'<rect width="{PW}" height="{height:.0f}" rx="10" fill="{t["bg"]}"/>')
    add(
        f'<rect width="{PW}" height="{height:.0f}" rx="10" fill="url(#pgrid)" '
        f'opacity="0.45"/>'
    )
    add(
        f'<rect x="0.5" y="0.5" width="{PW - 1}" height="{height - 1:.0f}" rx="10" '
        f'fill="none" stroke="{t["line"]}" stroke-width="1"/>'
    )
    add(text(pad, pad + 6, "// SELECTED WORK", fill=t["muted"], size=9.5,
             weight=600))

    for i, (name, blurb) in enumerate(FEATURED):
        col, row = i % cols, i // cols
        x = pad + col * (card_w + gap)
        y = top + row * (card_h + gap)
        meta = by_name.get(name.lower(), {})
        colour = meta.get("colour", DEFAULT_LANG_COLOUR)
        lang = meta.get("lang", "")
        stars = meta.get("stars", 0)

        card = [
            f'<g class="p" style="animation-delay:{0.05 + i * 0.06:.2f}s">',
            f'<rect x="{x:.1f}" y="{y}" width="{card_w:.1f}" height="{card_h}" '
            f'rx="8" fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1"/>',
            # language spine: the card's only colour, and it means something
            f'<rect x="{x:.1f}" y="{y}" width="2.5" height="{card_h}" '
            f'fill="{colour}"/>',
            text(x + 16, y + 27, name, fill=t["text"], size=13.5, weight=700),
            text(x + 16, y + 50, clip(blurb, 40), fill=t["muted"], size=10.75),
            f'<line x1="{x + 16:.1f}" y1="{y + 64}" x2="{x + card_w - 16:.1f}" '
            f'y2="{y + 64}" stroke="{t["line"]}" stroke-width="1"/>',
            f'<circle cx="{x + 20:.1f}" cy="{y + 79}" r="3.5" fill="{colour}"/>',
            text(x + 30, y + 83, lang, fill=t["muted"], size=10),
        ]
        if stars:
            card.append(
                f'<path transform="translate({x + card_w - 46:.1f},{y + 74}) '
                f'scale(0.62)" fill="{t["muted"]}" d="M8 0l2.35 5.1 5.65.6-4.2 '
                f'3.8 1.15 5.5L8 12.2 2.9 15l1.15-5.5L0 5.7l5.65-.6z"/>'
            )
            card.append(
                text(x + card_w - 16, y + 83, str(stars), fill=t["muted"],
                     size=10, anchor="end")
            )
        card.append("</g>")
        add("".join(card))

    add("</svg>")
    return "\n".join(o)


# --------------------------------------------------------------------------
# stack renderer
# --------------------------------------------------------------------------

# Grouped, hand-curated, and rendered in the same visual language as the rest
# of the page. Icon sheets from an external service look fine on their own but
# drag a second design system onto the page; a page that mixes three vendors'
# styling reads as assembled rather than authored.
STACK: list[tuple[str, list[tuple[str, str]]]] = [
    ("LANGUAGES", [
        ("Rust", "#dea584"), ("C#", "#178600"), ("TypeScript", "#3178c6"),
        ("JavaScript", "#f1e05a"), ("Python", "#3572A5"),
        ("PowerShell", "#5391FE"), ("Bash", "#89e051"), ("Nix", "#7e7eff"),
    ]),
    ("FRAMEWORKS & RUNTIME", [
        (".NET", "#512BD4"), ("Angular", "#DD0031"), ("Next.js", "#e6edf3"),
        ("React", "#61DAFB"), ("Tailwind", "#38BDF8"), ("Node.js", "#5FA04E"),
        ("Bun", "#FBF0DF"), ("Vite", "#A855F7"),
    ]),
    ("INFRASTRUCTURE", [
        ("Docker", "#2496ED"), ("Proxmox", "#E57000"), ("Linux", "#FCC624"),
        ("Windows Server", "#0078D4"), ("Nginx", "#009639"),
        ("Cloudflare", "#F38020"), ("GitHub Actions", "#2088FF"),
    ]),
    ("TOOLING", [
        ("Git", "#F05033"), ("Neovim", "#57A143"), ("VS Code", "#007ACC"),
        ("PostgreSQL", "#4169E1"), ("SQLite", "#003B57"), ("Redis", "#FF4438"),
    ]),
]

SW = 900


def render_stack(theme_name: str) -> str:
    """Grouped capability chips, wrapped to the panel width."""
    t = THEMES[theme_name]
    o: list[str] = []
    add = o.append

    pad = 32
    usable = SW - pad * 2
    char_w = 7.05                      # ui-monospace advance at 11.75px
    chip_h, chip_gap, row_gap = 27, 7, 9

    # measure first so the canvas height fits the content exactly
    layout: list[tuple[str, list[list[tuple[str, str, float, float]]]]] = []
    for group, items in STACK:
        rows: list[list[tuple[str, str, float, float]]] = [[]]
        x = 0.0
        for name, colour in items:
            w = 30 + char_w * len(name)
            if x + w > usable and rows[-1]:
                rows.append([])
                x = 0.0
            rows[-1].append((name, colour, x, w))
            x += w + chip_gap
        layout.append((group, rows))

    height = pad
    for _, rows in layout:
        height += 16 + len(rows) * chip_h + (len(rows) - 1) * row_gap + 22
    height = height - 22 + pad

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SW}" height="{height:.0f}" '
        f'viewBox="0 0 {SW} {height:.0f}" role="img" aria-label="Technology stack">'
    )
    add("<defs>")
    add(
        f'<pattern id="sgrid" width="30" height="30" patternUnits="userSpaceOnUse">'
        f'<path d="M30 0H0V30" fill="none" stroke="{t["grid"]}" stroke-width="1"/>'
        f"</pattern>"
    )
    add("</defs>")
    add(
        "<style>"
        "@keyframes sin{from{opacity:0;transform:translateY(6px)}"
        "to{opacity:1;transform:translateY(0)}}"
        ".s{animation:sin .45s cubic-bezier(.22,1,.36,1) both}"
        "@media(prefers-reduced-motion:reduce){.s{animation:none;opacity:1;"
        "transform:none}}"
        "</style>"
    )

    add(f'<rect width="{SW}" height="{height:.0f}" rx="10" fill="{t["bg"]}"/>')
    add(
        f'<rect width="{SW}" height="{height:.0f}" rx="12" fill="url(#sgrid)" '
        f'opacity="0.5"/>'
    )
    add(
        f'<rect x="0.75" y="0.75" width="{SW - 1.5}" height="{height - 1.5:.0f}" '
        f'rx="10" fill="none" stroke="{t["line"]}" stroke-width="1"/>'
    )

    y = pad + 4
    index = 0
    for group, rows in layout:
        add(text(pad, y, f"// {group}", fill=t["muted"], size=9.5, weight=600))
        y += 14
        for row in rows:
            for name, colour, x, w in row:
                cx = pad + x
                add(
                    f'<g class="s" style="animation-delay:{0.04 * index:.2f}s">'
                    f'<rect x="{cx:.1f}" y="{y}" width="{w:.1f}" height="{chip_h}" '
                    f'rx="6" fill="{t["panel"]}" stroke="{t["line"]}" '
                    f'stroke-width="1"/>'
                    f'<circle cx="{cx + 14:.1f}" cy="{y + chip_h / 2:.1f}" r="4" '
                    f'fill="{colour}"/>'
                    + text(cx + 24, y + chip_h / 2 + 4, name, fill=t["text"],
                           size=11.75)
                    + "</g>"
                )
                index += 1
            y += chip_h + row_gap
        y += 22 - row_gap

    add("</svg>")
    return "\n".join(o)


# --------------------------------------------------------------------------
# header renderer
# --------------------------------------------------------------------------

HW = 900
HH = 242


def render_header(d: dict[str, Any], theme_name: str) -> str:
    """
    The hero card.

    This deliberately replaces the usual stack of a gradient banner, a typing
    SVG and a row of shields. Those come from three different projects with
    three different visual languages, and pasted together they read as
    assembled rather than designed. One card, one type scale, one palette.
    """
    t = THEMES[theme_name]
    o: list[str] = []
    add = o.append

    tagline = "if it runs twice, it should run itself"
    char_w = 8.4                       # ui-monospace advance at 14px
    tag_w = char_w * len(tagline)
    tag_x, tag_y = 44, 202

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{HW}" height="{HH}" '
        f'viewBox="0 0 {HW} {HH}" role="img" '
        f'aria-label="{escape(d["name"])} -- {escape(tagline)}">'
    )

    add("<defs>")
    add(
        f'<pattern id="hgrid" width="30" height="30" patternUnits="userSpaceOnUse">'
        f'<path d="M30 0H0V30" fill="none" stroke="{t["grid"]}" stroke-width="1"/>'
        f"</pattern>"
    )
    # Reveals the tagline left-to-right; the caret rides the same edge.
    add(
        f'<clipPath id="typeclip">'
        f'<rect class="type" x="{tag_x}" y="{tag_y - 14}" '
        f'width="{tag_w:.0f}" height="20"/>'
        f"</clipPath>"
    )
    add("</defs>")

    add(
        "<style>"
        "@keyframes hrise{from{opacity:0;transform:translateY(10px)}"
        "to{opacity:1;transform:translateY(0)}}"
        "@keyframes hfade{from{opacity:0}to{opacity:1}}"
        f"@keyframes typein{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        # Rides from left to right, but expressed as a negative start offset so
        # the caret's *resting* position is the end of the line. A renderer that
        # ignores CSS animation (rsvg, a thumbnailer) then draws it correctly
        # rather than parking it on top of the first character.
        f"@keyframes ride{{from{{transform:translateX(-{tag_w:.0f}px)}}"
        f"to{{transform:translateX(0)}}}}"
        "@keyframes wink{0%,45%{opacity:1}50%,100%{opacity:0}}"
        ".hr{animation:hrise .6s cubic-bezier(.22,1,.36,1) both}"
        ".hf{animation:hfade .8s ease-out both}"
        f".type{{animation:typein 1.9s steps({len(tagline)}) .55s both;"
        "transform-origin:left center}"
        f".caret{{animation:ride 1.9s steps({len(tagline)}) .55s both,"
        "wink 1s steps(1) 2.45s infinite}"
        "@media(prefers-reduced-motion:reduce){"
        ".hr,.hf,.type,.caret{animation:none;opacity:1;transform:none}}"
        "</style>"
    )

    # frame
    add(f'<rect width="{HW}" height="{HH}" rx="10" fill="{t["bg"]}"/>')
    add(f'<rect width="{HW}" height="{HH}" rx="10" fill="url(#hgrid)" opacity="0.45"/>')
    add(
        f'<rect x="0.5" y="0.5" width="{HW - 1}" height="{HH - 1}" rx="10" '
        f'fill="none" stroke="{t["line"]}" stroke-width="1"/>'
    )

    # identity
    add(
        '<g class="hr" style="animation-delay:.05s">'
        + text(44, 100, d["name"], fill=t["text"], size=52, weight=800,
               family="ui-sans-serif, -apple-system, 'Segoe UI', Inter, sans-serif")
        + "</g>"
    )
    add(
        f'<rect class="hr" style="animation-delay:.14s" x="46" y="118" '
        f'width="46" height="2" fill="{t["accent"]}"/>'
    )
    add(
        '<g class="hr" style="animation-delay:.2s">'
        + text(44, 146, "ICT System Engineer  ·  Automation  ·  Self-hosting",
               fill=t["text"], size=14.5,
               family="ui-sans-serif, -apple-system, 'Segoe UI', Inter, sans-serif")
        + "</g>"
    )

    # The facts that used to live in a separate prose block. Folded in here so
    # the page opens with one panel instead of a panel plus a paragraph nobody
    # scrolling a README is going to read.
    add(
        '<g class="hr" style="animation-delay:.26s">'
        + text(44, 170,
               "Switzerland  ·  Federal Vocational Baccalaureate  ·  "
               "learning Rust + Nix",
               fill=t["muted"], size=12.5,
               family="ui-sans-serif, -apple-system, 'Segoe UI', Inter, "
                      "sans-serif")
        + "</g>"
    )

    # typed tagline
    add(
        f'<g clip-path="url(#typeclip)">'
        + text(tag_x, tag_y, tagline, fill=t["muted"], size=14)
        + "</g>"
    )
    add(
        f'<rect class="caret" x="{tag_x + tag_w:.0f}" y="{tag_y - 12}" width="8" '
        f'height="16" fill="{t["accent"]}"/>'
    )

    # divider + stat chips
    add(
        f'<line class="hf" style="animation-delay:.3s" x1="566" y1="52" '
        f'x2="566" y2="194" stroke="{t["line"]}" stroke-width="1"/>'
    )
    chips = [
        ("FOLLOWERS", human(d["followers"])),
        ("REPOSITORIES", human(d["repos"])),
        ("STARS EARNED", human(d["stars"])),
        ("SINCE", d["created"][:4]),
    ]
    for i, (label, value) in enumerate(chips):
        col, row = i % 2, i // 2
        cx = 616 + col * 140
        cy = 98 + row * 64
        add(
            f'<g class="hr" style="animation-delay:{0.3 + i * 0.07:.2f}s">'
            + text(cx, cy - 16, label, fill=t["muted"], size=9, weight=600)
            + text(cx, cy + 8, value, fill=t["text"], size=24, weight=700)
            + "</g>"
        )

    add("</svg>")
    return "\n".join(o)


# --------------------------------------------------------------------------
# renderer
# --------------------------------------------------------------------------

W = 900
H = 496
PAD = 26


def render(d: dict[str, Any], theme_name: str) -> str:
    t = THEMES[theme_name]
    o: list[str] = []
    add = o.append

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="GitHub statistics for {escape(d["login"])}">'
    )

    # ---- defs: gradients, glow filter, scanline pattern -------------------
    add("<defs>")
    add(
        f'<pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">'
        f'<path d="M26 0H0V26" fill="none" stroke="{t["grid"]}" stroke-width="1"/>'
        f"</pattern>"
    )
    add("</defs>")

    # ---- animation stylesheet --------------------------------------------
    add(
        "<style>"
        "@keyframes fade{from{opacity:0}to{opacity:1}}"
        "@keyframes rise{from{opacity:0;transform:translateY(9px)}"
        "to{opacity:1;transform:translateY(0)}}"
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        "@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}"
        "@keyframes blink{0%,45%{opacity:1}50%,100%{opacity:0}}"
        ".r{animation:rise .55s cubic-bezier(.22,1,.36,1) both}"
        ".g{animation:grow 1.05s cubic-bezier(.22,1,.36,1) both;transform-origin:left center}"
        ".c{animation:pop .34s ease-out both}"
        ".cursor{animation:blink 1.1s steps(1) infinite}"
        "@media(prefers-reduced-motion:reduce){"
        ".r,.g,.c,.cursor{animation:none;opacity:1;transform:none}}"
        "</style>"
    )

    # ---- frame ------------------------------------------------------------
    add(f'<rect width="{W}" height="{H}" rx="10" fill="{t["bg"]}"/>')
    add(f'<rect width="{W}" height="{H}" rx="10" fill="url(#grid)" opacity="0.45"/>')
    add(
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" '
        f'fill="none" stroke="{t["line"]}" stroke-width="1"/>'
    )

    # ---- title bar --------------------------------------------------------
    add(f'<rect x="1" y="1" width="{W - 2}" height="40" rx="9" fill="{t["panel"]}"/>')
    add(f'<rect x="1" y="30" width="{W - 2}" height="11" fill="{t["panel"]}"/>')
    add(f'<line x1="0" y1="41" x2="{W}" y2="41" stroke="{t["line"]}" stroke-width="1"/>')
    add(
        text(PAD, 26, f"{d['login']}@github ~ ./dashboard --live",
             fill=t["muted"], size=12)
    )
    add(
        text(
            W - PAD, 26,
            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
            fill=t["muted"], size=11, anchor="end",
        )
    )

    # ---- identity line ----------------------------------------------------
    y = 74
    prompt = f"whoami --name '{d['name']}'"
    # ui-monospace advance width is ~0.6em; used to park the caret after the text
    caret_x = PAD + 18 + 9.0 * len(prompt)
    add(text(PAD, y, "$", fill=t["accent"], size=15, weight=700))
    add(text(PAD + 18, y, prompt, fill=t["text"], size=15, weight=600))
    add(
        f'<rect class="cursor" x="{caret_x:.1f}" y="{y - 12}" width="9" '
        f'height="15" fill="{t["accent"]}"/>'
    )

    # ---- stat tiles -------------------------------------------------------
    # Deliberately unaccented. Six tiles in six colours is decoration; the
    # numbers are the content and the panel already separates them.
    tiles = [
        ("COMMITS", d["commits"]),
        ("PULL REQS", d["prs"]),
        ("ISSUES", d["issues"]),
        ("REVIEWS", d["reviews"]),
        ("STARS", d["stars"]),
        ("FOLLOWERS", d["followers"]),
    ]
    tw, gap, ty = 132, 8, 92
    for i, (label, value) in enumerate(tiles):
        tx = PAD + i * (tw + gap)
        add(
            f'<g class="r" style="animation-delay:{0.05 + i * 0.06:.2f}s">'
            f'<rect x="{tx}" y="{ty}" width="{tw}" height="62" rx="8" '
            f'fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1"/>'
            + text(tx + 14, ty + 24, label, fill=t["muted"], size=9.5, weight=600)
            + text(tx + 14, ty + 48, human(value), fill=t["text"], size=21,
                   weight=700)
            + "</g>"
        )

    # ---- language bars ----------------------------------------------------
    ly = 182
    add(text(PAD, ly, "// LANGUAGE DISTRIBUTION", fill=t["muted"], size=10.5, weight=600))

    ranked = sorted(d["langs"].items(), key=lambda kv: -kv[1]["size"])[:6]
    total = sum(v["size"] for _, v in ranked) or 1

    # single stacked bar
    bx, by, bw = PAD, ly + 12, W - PAD * 2
    add(f'<clipPath id="barclip"><rect x="{bx}" y="{by}" width="{bw}" height="12" rx="6"/></clipPath>')
    add(f'<g clip-path="url(#barclip)">')
    add(f'<rect x="{bx}" y="{by}" width="{bw}" height="12" fill="{t["grid"]}"/>')
    cursor = bx
    for i, (name, meta) in enumerate(ranked):
        seg = bw * meta["size"] / total
        add(
            f'<rect class="g" style="animation-delay:{0.25 + i * 0.09:.2f}s" '
            f'x="{cursor:.2f}" y="{by}" width="{seg:.2f}" height="12" '
            f'fill="{meta["color"]}"/>'
        )
        cursor += seg
    add("</g>")

    # legend, two rows of three
    for i, (name, meta) in enumerate(ranked):
        col, row = i % 3, i // 3
        lx = PAD + col * 282
        lyy = by + 36 + row * 22
        pct = 100 * meta["size"] / total
        add(
            f'<g class="r" style="animation-delay:{0.35 + i * 0.07:.2f}s">'
            f'<circle cx="{lx + 5}" cy="{lyy - 4}" r="5" fill="{meta["color"]}"/>'
            + text(lx + 17, lyy, name, fill=t["text"], size=11.5)
            + text(lx + 258, lyy, f"{pct:.1f}%", fill=t["muted"], size=11.5, anchor="end")
            + "</g>"
        )

    # ---- contribution heatmap --------------------------------------------
    hy = 306
    add(
        text(PAD, hy, "// CONTRIBUTION CALENDAR", fill=t["muted"], size=10.5, weight=600)
    )
    add(
        text(
            W - PAD, hy,
            f"{human(d['contributions'])} contributions in the last year",
            fill=t["muted"], size=10.5, anchor="end",
        )
    )

    cell, cgap = 12, 3
    step = cell + cgap
    gx, gy = PAD + 26, hy + 26

    days = d["days"]
    if days:
        first = dt.date.fromisoformat(days[0][0])
        # pad so column 0 starts on Sunday, matching GitHub's grid
        lead = (first.weekday() + 1) % 7
        cells: list[tuple[int, int, int, str]] = []
        for idx, (date_s, count) in enumerate(days):
            pos = idx + lead
            col, row = divmod(pos, 7)
            cells.append((col, row, count, date_s))

        peak = max((c for _, _, c, _ in cells), default=0) or 1

        def level(n: int) -> int:
            if n <= 0:
                return 0
            return min(4, 1 + int(3 * (n / peak) ** 0.45))

        ncols = max(c for c, _, _, _ in cells) + 1
        for col, row, count, date_s in cells:
            add(
                f'<rect class="c" style="animation-delay:{0.4 + col * 0.012:.2f}s" '
                f'x="{gx + col * step}" y="{gy + row * step}" width="{cell}" '
                f'height="{cell}" rx="2.5" fill="{t["heat"][level(count)]}">'
                f"<title>{date_s}: {count} contributions</title></rect>"
            )

        # month ruler
        seen: set[str] = set()
        for col, row, _, date_s in cells:
            if row != 0:
                continue
            date = dt.date.fromisoformat(date_s)
            key = date.strftime("%Y-%m")
            if key in seen or date.day > 7:
                continue
            seen.add(key)
            add(
                text(gx + col * step, gy - 8, date.strftime("%b"),
                     fill=t["muted"], size=9.5)
            )
        for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            add(
                text(gx - 8, gy + row * step + 9.5, label, fill=t["muted"],
                     size=9, anchor="end")
            )
    else:
        ncols = 53
        add(
            text(W / 2, gy + 46, "calendar unavailable -- run with GITHUB_TOKEN",
                 fill=t["muted"], size=11.5, anchor="middle")
        )

    # heat legend
    lx = gx + ncols * step - 132
    ly2 = gy + 7 * step + 16
    add(text(lx - 6, ly2 + 9, "Less", fill=t["muted"], size=9, anchor="end"))
    for i, c in enumerate(t["heat"]):
        add(
            f'<rect x="{lx + i * 15}" y="{ly2}" width="11" height="11" rx="2.5" fill="{c}"/>'
        )
    add(text(lx + 5 * 15 + 4, ly2 + 9, "More", fill=t["muted"], size=9))

    # ---- footer -----------------------------------------------------------
    add(f'<line x1="{PAD}" y1="{H - 34}" x2="{W - PAD}" y2="{H - 34}" '
        f'stroke="{t["line"]}" stroke-width="1"/>')
    add(
        text(PAD, H - 15,
             f"repos {d['repos']}  |  forks {d['forks']}  |  member since {d['created']}",
             fill=t["muted"], size=10.5)
    )
    add(
        text(W - PAD, H - 15, "rendered in-repo by GitHub Actions -- no external service",
             fill=t["muted"], size=10.5, anchor="end")
    )

    add("</svg>")
    return "\n".join(o)


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", default="assets")
    ap.add_argument("--demo", action="store_true",
                    help="render from synthetic data, for offline layout checks")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    if args.demo:
        data = demo_data(args.user)
        print("source: synthetic demo data")
    elif token:
        try:
            data = fetch_graphql(args.user, token)
            print("source: GraphQL (full calendar)")
        except Exception as exc:  # noqa: BLE001 - degrade, never fail the build
            print(f"graphql failed ({exc}); falling back to REST", file=sys.stderr)
            data = fetch_rest(args.user, token)
    else:
        print("source: REST (no token; calendar unavailable)", file=sys.stderr)
        data = fetch_rest(args.user, None)

    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        for name, fn in (("header", render_header), ("dashboard", render),
                         ("projects", render_projects)):
            path = os.path.join(args.out, f"{name}-{theme}.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(fn(data, theme))
            print(f"wrote {path}")
        # The stack is curated, not derived from the API.
        path = os.path.join(args.out, f"stack-{theme}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_stack(theme))
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

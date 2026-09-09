# Project overview

This folder is the deployable source for the **GitHub profile README** of
[`MyDrift-user`](https://github.com/MyDrift-user). Push it to the repository
`MyDrift-user/MyDrift-user` and its root `README.md` becomes the profile page.

The root `README.md` is therefore the *product*, not documentation about the
product. Everything explaining the build lives here in `docs/`.

---

## Layout

```
github-profile/
├── README.md                     the profile page itself -- deploys to the repo root
├── .github/workflows/
│   ├── generate.yml              renders all dynamic assets daily -> `output` branch
│   ├── link-health.yml           probes every embedded URL weekly, opens an issue on rot
│   └── metrics.yml               optional lowlighter/metrics run (needs a PAT)
├── scripts/
│   ├── gen_dashboard.py          renders the hero, dashboard, stack and project SVGs
│   ├── check_links.py            asset health prober used by CI
│   └── preview.py                local GitHub-fidelity preview, publishes nothing
├── assets/                       local previews (regenerable, git-ignored)
└── docs/
    ├── README.md                 this file
    ├── RESEARCH.md               findings: what works, what is dead, and why
    ├── CATALOG.md                copy-paste widget reference with live status
    └── DEPLOY.md                 step-by-step publish and troubleshooting
```

---

## The visual system

Every panel on the page -- hero, statistics dashboard, technology stack -- is
rendered by `gen_dashboard.py` from one palette, one type scale and one frame
treatment. That is a design decision, not just an availability one.

The conventional profile stacks a gradient banner from one project, a typing
SVG from a second, and a row of shields from a third. Each is well made in
isolation, but together they carry three different visual languages onto one
page, and the result reads as assembled rather than authored. Replacing them
with panels that share a system is what separates a profile that looks designed
from one that looks templated.

Only two external images survive on the page: the contribution snake, whose
GitHub-native palette already matches, and one CI status badge inside a
collapsed section.

## The design constraint

An audit of the current live profile found **four dead embedded images**: two
`503`s from `github-readme-stats.vercel.app` and two `402 Payment Required`
from Vercel-hosted forks that had exhausted their free tier.

Nothing had signalled this. Markdown with a dead image URL is still valid
Markdown, GitHub still serves the page, and the profile had been showing broken
images to visitors indefinitely.

So the whole build follows one rule: **anything load-bearing is rendered by CI
in this repository and committed as a file.** Third-party services are used
only where they are institutionally durable, and a weekly job verifies even
those. See [RESEARCH.md](RESEARCH.md) for the tier model and the measurements.

---

## How it runs

| Workflow | Trigger | Does |
|---|---|---|
| `generate.yml` | daily 03:17 UTC, push to `scripts/`, manual | Renders the hero, dashboard and stack panels, plus the snake and 3D calendar; publishes twelve SVGs to the `output` branch |
| `link-health.yml` | Mondays 06:00 UTC, PRs touching `README.md` | Probes every embedded URL; opens or updates one rolling issue when an asset dies |
| `metrics.yml` | manual | Optional richer infographic; skips itself cleanly when `PROFILE_TOKEN` is unset |

Generated assets go to a dedicated `output` branch so that daily regeneration
does not bury `main` under a wall of "generated" commits.

---

## Previewing before you publish

```bash
python3 scripts/preview.py          # builds preview.html and serves it on :8000
```

It renders `README.md` through **GitHub's own markdown API**, so the output
matches the real page — including the camo image proxy. Three things it fixes
that a generic Markdown viewer gets wrong:

- **Mermaid.** The API returns a diagram as syntax-highlighted markup rather
  than a rendered one; the previewer re-inflates it and runs mermaid.js. The
  profile does not currently use a diagram, but the support is there if you
  add one.
- **Theme switching.** Browsers resolve `<picture>` against the real OS setting,
  so you cannot normally see both. The light/dark toggle rewrites each
  `<source>`'s media query to force the choice. `#light` / `#dark` in the URL
  selects one up front.
- **Missing assets.** Anything on the `output` branch 404s until CI has run
  once, so local files in `assets/` are substituted where they exist, and the
  header reports what is still missing.

Screenshotting the preview is a trap worth knowing about. The panels animate in
over about a second, and a headless capture fires before they settle, so the
page photographs as a set of empty boxes. Force the reduced-motion path
instead -- the SVGs honour it, so every panel renders in its settled state:

```bash
chromium --headless --force-prefers-reduced-motion \
  --window-size=1180,2900 --screenshot=/tmp/page.png \
  "file://$PWD/preview.html#dark"
```

That doubles as a check that the accessibility path actually works.

## Working on the dashboard

```bash
# deterministic synthetic data -- no token, no API quota
python3 scripts/gen_dashboard.py --user MyDrift-user --out assets --demo

# real data; add GITHUB_TOKEN for the contribution calendar
GITHUB_TOKEN=ghp_... python3 scripts/gen_dashboard.py --user MyDrift-user --out assets

# rasterise to check it visually
rsvg-convert -w 900 assets/dashboard-dark.svg -o /tmp/preview.png
```

Both scripts are standard library only, so CI needs no `pip install` step and
cannot break on a transitive dependency.

---

## Before you publish

Read [DEPLOY.md](DEPLOY.md) §1. The short version: keep real host names,
domains and VM identifiers off a public profile page.

# Research: what actually works in a GitHub profile README

Measured 2026-09-09. Every status code below came from probing the live
endpoint, not from documentation.

---

## 1. The finding that shaped everything else

The live `MyDrift-user` profile README was audited before anything was written.
Four of its embedded images were dead:

| Asset | Status | Meaning |
|---|---|---|
| `github-readme-stats.vercel.app/api` (stats card) | `503` | Service Unavailable |
| `github-readme-stats.vercel.app/api/top-langs` | `503` | Service Unavailable |
| `nirzak-streak-stats.vercel.app` (streak card) | `402` | Payment Required |
| `github-readme-activity-graph.vercel.app` (activity graph) | `402` | Payment Required |

`402 Payment Required` is Vercel's response when a hobby project exceeds its
free allowance. The profile had been serving broken images to visitors for an
unknown period, because **nothing in the GitHub ecosystem alerts you when an
embedded image dies.** The Markdown stays valid. The page still renders. The
images simply do not.

The projects behind those URLs are all healthy and actively maintained —
`github-readme-stats` has 79.8k stars and was pushed to 2026-08-31. The failure
is not the software; it is the economics of a free public instance absorbing
traffic from millions of profile READMEs.

**Conclusion: treat any third-party rendering service as a liability with a
half-life.** Rank assets by who pays for the hosting.

---

## 2. The durability tiers

### Tier 1 — Self-generated, committed to your own repository

CI renders an SVG, commits it, GitHub serves it. Cannot rate-limit, cannot
expire, cannot bill anyone. This is the only tier with no external dependency
at runtime.

- `scripts/gen_dashboard.py` in this repo (statistics card)
- `Platane/snk@v3` (contribution snake) — runs *as an action*, output committed
- `yoshi389111/github-profile-3d-contrib` (3D calendar) — same model
- `lowlighter/metrics@v3.34` (rich infographic) — same model

The distinction matters and is widely missed: `github-readme-stats` used as a
hosted URL is Tier 3, but the *same project* consumed as a GitHub Action that
commits its output is Tier 1.

### Tier 2 — Third-party, but institutionally durable

Funded, cached at CDN edge, or backed by an organisation rather than one
person's hobby budget. Verified 200 on 2026-09-09:

| Service | Status | Notes |
|---|---|---|
| `img.shields.io` | `200` | Backed by an org, on the CDN, extremely stable |
| `skillicons.dev` | `200` | Purpose-built icon sheets, own domain |
| `streak-stats.demolab.com` | `200` | DenverCoder1's own domain, not a Vercel subdomain |
| `readme-typing-svg.demolab.com` | `200` | Same; the `.herokuapp.com` host redirects but should not be relied on |
| `capsule-render.vercel.app` | `200` | Vercel-hosted, so structurally Tier 3, but long-lived |
| `komarev.com/ghpvc` | `200` | View counter, own domain |

### Tier 3 — Avoid for anything load-bearing

Free `*.vercel.app` subdomains carrying ecosystem-wide traffic. Confirmed
failing: `github-readme-stats.vercel.app`, `nirzak-streak-stats.vercel.app`,
`github-readme-activity-graph.vercel.app`, `github-profile-trophy.vercel.app`
(all `402`/`503` on 2026-09-09).

If you want one of these cards, self-host the project or run it as an action.

---

## 3. What GitHub's Markdown renderer actually supports

Verified capabilities, and the constraints people trip over:

**Supported**
- A useful HTML subset: `<div>`, `<table>`, `<img>`, `<picture>`, `<details>`,
  `<summary>`, `<sub>`, `<a>`, alignment attributes.
- `<picture>` + `<source media="(prefers-color-scheme: dark)">` for theme-aware
  images. This is the official, documented mechanism.
- **Mermaid diagrams natively**, via a ```` ```mermaid ```` fence. No image, no
  build step, and it re-themes with the viewer. Badly underused, and one of the
  strongest technical signals available.
- Animated SVG. Both CSS `@keyframes` and SMIL animate normally inside an
  `<img>`, which is how the typing and wave banners work.
- Collapsible sections via `<details>`, which keep a long profile scannable.
- LaTeX via `$...$` and ```` ```math ````.

**Not supported**
- `<script>` — stripped. No JavaScript, ever.
- External CSS and `<style>` blocks in the Markdown itself — stripped. Styling
  must live *inside* the SVG file.
- `style=` attributes on Markdown-level HTML — stripped. (Inside an SVG they
  are fine, because the browser renders that file as an image.)
- Custom fonts in SVG. Images are loaded by the browser without your font
  files, so an SVG must use a generic stack such as
  `ui-monospace, SFMono-Regular, Consolas, monospace`.

**Camo proxying.** All external images are proxied through GitHub's camo
service, which rewrites the URL and caches. Two consequences: your visitors'
IPs are never exposed to the third party, and a regenerated asset at an
unchanged URL may serve stale for a short window.

---

## 4. Techniques ranked by signal-to-effort

What separates a memorable technical profile from a badge wall:

1. **A self-rendered dashboard.** Anyone can paste a stats URL. Committing an
   SVG your own code produced demonstrates API work, rendering, and CI in one
   artifact. Highest signal available.
2. **A Mermaid architecture diagram.** Shows systems thinking rather than a
   list of logos, and costs nothing to maintain. Built for this profile and
   then cut: it is the right technique on a page someone reads, and the wrong
   one on a page someone skims. Weigh it against how much reading the rest of
   the page already asks for.
3. **CI that guards the README.** A link-health job that opens an issue when an
   asset dies is the direct answer to the failure documented in §1, and almost
   nobody does it.
4. **Theme-aware assets throughout.** Roughly half of visitors are in light
   mode; a dark-only card looks broken to them.
5. **A structured `whoami` block.** A fenced YAML/TOML identity block reads as
   deliberate where a prose paragraph reads as filler.
6. **Curated project cards** in a two-column table, each with one sentence of
   *why it exists* — not an auto-generated pinned-repo dump.
7. **Collapsible detail sections.** Depth for whoever wants it, brevity for
   everyone else.
8. Snake animation and 3D calendar — genuinely well-executed eye candy, cheap
   because both run as actions.
9. Badge walls — the lowest signal per pixel. Four grouped icon rows beat
   twenty individual shields.

---

## 5. Maintenance status of the ecosystem (2026-09-09)

All actively maintained; none archived:

| Project | Stars | Last push |
|---|---|---|
| `anuraghazra/github-readme-stats` | 79.8k | 2026-08-31 |
| `lowlighter/metrics` | 17.2k | 2026-05-29 |
| `Ileriayo/markdown-badges` | 17.0k | 2026-08-11 |
| `tandpfun/skill-icons` | 13.1k | 2026-02-27 |
| `rzashakeri/beautify-github-profile` | 12.5k | 2026-08-13 |
| `DenverCoder1/readme-typing-svg` | 9.3k | 2026-08-31 |
| `DenverCoder1/github-readme-streak-stats` | 7.1k | 2026-08-31 |
| `ryo-ma/github-profile-trophy` | 6.6k | 2026-07-25 |
| `Platane/snk` | 6.1k | 2026-04-29 |
| `gautamkrishnar/blog-post-workflow` | 3.4k | 2026-08-10 |
| `kyechan99/capsule-render` | 1.8k | 2026-09-09 |
| `yoshi389111/github-profile-3d-contrib` | 1.7k | 2026-09-06 |

Note the action versions. Most tutorials still show `actions/checkout@v3`; the
current major is **v7**, and `actions/setup-python` is at **v7**.

---

## Sources

- [How to make your images in Markdown on GitHub adjust for dark mode and light mode — GitHub Blog](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/)
- [Specify theme context for images — GitHub community discussion #16910](https://github.com/orgs/community/discussions/16910)
- [anuraghazra/github-readme-stats](https://github.com/anuraghazra/github-readme-stats)
- [Self-hosted alternative: GitHub Actions deployment — issue #4747](https://github.com/anuraghazra/github-readme-stats/issues/4747)
- [utkuozdemir/github-readme-stats-selfhosted](https://github.com/utkuozdemir/github-readme-stats-selfhosted)
- [lowlighter/metrics](https://github.com/lowlighter/metrics)
- [Platane/snk](https://github.com/Platane/snk)
- [yoshi389111/github-profile-3d-contrib](https://github.com/yoshi389111/github-profile-3d-contrib)
- [rzashakeri/beautify-github-profile](https://github.com/rzashakeri/beautify-github-profile)
- [Your GitHub Profile README Is Boring — DEV Community](https://dev.to/flyingsquirrel0419/your-github-profile-readme-is-boring-heres-how-to-fix-it-with-svg-and-github-actions-3pim)
- [Top GitHub Profile Tools and Stats Generators (2026) — DEV Community](https://dev.to/_d7eb1c1703182e3ce1782/top-github-profile-tools-and-stats-generators-2026-2h3h)
- [GitHub README Templates in 2026 — UniLink](https://app.unilink.us/blog/github-readme-templates-2026)

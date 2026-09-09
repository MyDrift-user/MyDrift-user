# Widget catalogue

Copy-paste blocks for everything worth embedding, with the durability tier from
[RESEARCH.md](RESEARCH.md) and a status verified on 2026-09-09.

Replace `MyDrift-user` if you reuse these elsewhere.

---

## Tier 1 — generated in your own repository

### Statistics dashboard (this repo)

```html
<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="https://raw.githubusercontent.com/MyDrift-user/MyDrift-user/output/dashboard-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/MyDrift-user/MyDrift-user/output/dashboard-light.svg" />
  <img alt="GitHub statistics" src="https://raw.githubusercontent.com/MyDrift-user/MyDrift-user/output/dashboard-dark.svg" width="100%" />
</picture>
```

Customise by editing `THEMES` and the `render()` function in
`scripts/gen_dashboard.py`. Preview without touching the network:

```bash
python3 scripts/gen_dashboard.py --user MyDrift-user --out assets --demo
```

### Contribution snake — `Platane/snk@v3`

Outputs accept query parameters: `palette` (`github-dark`, `github-light`),
`color_snake`, `color_dots` (five comma-separated colours), `color_background`
(GIF only). Use `Platane/snk/svg-only@v3` to skip GIF encoding and halve the
runtime.

### 3D contribution calendar — `yoshi389111/github-profile-3d-contrib@latest`

Writes eleven variants to `profile-3d-contrib/`:
`profile-green.svg`, `profile-green-animate.svg`, `profile-season.svg`,
`profile-season-animate.svg`, `profile-south-season.svg`,
`profile-south-season-animate.svg`, `profile-night-view.svg`,
`profile-night-green.svg`, `profile-night-rainbow.svg`, `profile-gitblock.svg`,
and `profile-customize.svg` when `SETTING_JSON` is set.

Env: `GITHUB_TOKEN` (required), `USERNAME` (required), `MAX_REPOS`,
`SETTING_JSON`, `YEAR`.

### Rich infographic — `lowlighter/metrics@v3.34`

30+ plugins. Needs a classic PAT. Wired up but opt-in in
`.github/workflows/metrics.yml`. Worth enabling for `plugin_isocalendar` and
`plugin_habits` alone.

---

## Tier 2 — third-party, durable

> **Not currently used on the profile.** These all work, and they are documented
> here because they are the right fallback if you ever stop generating your own.
> They were removed from the page for a design reason rather than a reliability
> one: each carries its own visual language, and stacking three vendors' styling
> on one page reads as assembled rather than designed. The hero, dashboard and
> stack panels replaced them.

### Shields.io badges — `200`

```markdown
![Followers](https://img.shields.io/github/followers/MyDrift-user?style=for-the-badge&color=1f6feb&labelColor=0d1117&logo=github)
![Stars](https://img.shields.io/github/stars/MyDrift-user?style=for-the-badge&color=e3b341&labelColor=0d1117)
![Workflow](https://img.shields.io/github/actions/workflow/status/MyDrift-user/MyDrift-user/link-health.yml?style=for-the-badge&labelColor=0d1117)
```

Styles: `flat`, `flat-square`, `plastic`, `for-the-badge`, `social`.
Any [Simple Icons](https://simpleicons.org) slug works as `logo=`.

### Skill icons — `200`

```markdown
![Stack](https://skillicons.dev/icons?i=rust,ts,cs,docker,linux,nix&theme=dark)
```

`theme=dark|light`, `perline=N` to wrap. Full slug list at
[skillicons.dev](https://skillicons.dev). Four grouped rows read far better
than twenty separate shields.

### Typing SVG — `200`

```markdown
![Typing](https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=20&pause=1200&color=39D353&center=true&vCenter=true&width=620&lines=First+line;Second+line)
```

Use the `demolab.com` host. The `herokuapp.com` host still redirects, but it
outlived the platform it was named after and should not be trusted.

### Streak stats — `200`

```markdown
![Streak](https://streak-stats.demolab.com?user=MyDrift-user&theme=github-dark-blue&hide_border=true&border_radius=10)
```

Again `demolab.com`, **not** the various `*.vercel.app` forks — those are the
ones currently returning `402`.

### Capsule render banner — `200`

```markdown
![Banner](https://capsule-render.vercel.app/api?type=waving&height=190&color=0:0d1117,50:1f6feb,100:39d353&text=MyDrift&fontColor=ffffff&fontSize=64&animation=fadeIn)
```

`type`: `waving`, `wave`, `rect`, `slice`, `egg`, `soft`, `cylinder`,
`shark`, `blur`, `transparent`. Vercel-hosted, so mirror it into `assets/` if
you want a guarantee.

### Profile view counter — `200`

```markdown
![Views](https://komarev.com/ghpvc/?username=MyDrift-user&style=for-the-badge&color=1f6feb)
```

---

## Native GitHub features — zero dependencies

### Mermaid

Fence with ```` ```mermaid ````. Supports `flowchart`, `sequenceDiagram`,
`classDiagram`, `stateDiagram-v2`, `erDiagram`, `gantt`, `gitGraph`,
`mindmap`, `timeline`, `quadrantChart`. Style with `classDef` so it holds up in
both colour themes.

### Theme-aware images

```html
<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="light.svg" />
  <img alt="Description" src="dark.svg" />
</picture>
```

### Collapsible sections

```html
<details>
<summary><b>Click to expand</b></summary>

Content. Leave a blank line after the summary or Markdown will not render.

</details>
```

### Two-column layout

`<table>` with `<td width="50%" valign="top">`. The only reliable multi-column
mechanism, since CSS is stripped.

### Maths

Inline `$E = mc^2$`, or a ```` ```math ```` block.

---

## Tier 3 — currently failing, listed so you do not reach for them

Verified 2026-09-09:

| URL | Status |
|---|---|
| `github-readme-stats.vercel.app` | `503` |
| `nirzak-streak-stats.vercel.app` | `402` |
| `github-readme-activity-graph.vercel.app` | `402` |
| `github-profile-trophy.vercel.app` | `402` |

Each has a healthy upstream project. Self-host, or run it as an action and
commit the output.

---

## Worth adding later

- **`gautamkrishnar/blog-post-workflow`** — injects RSS items between
  `<!-- BLOG-POST-LIST:START -->` markers. Useful the moment you write anywhere.
- **`jamesgeorge007/github-activity-readme`** — recent public events, same
  marker mechanism.
- **WakaTime** — real coding-time-per-language. The one statistic on a profile
  that is genuinely hard to game, but it requires the editor plugin.
- **Now-playing / currently-reading cards** — personality, at the cost of
  another external dependency. Mirror into `assets/` if you add one.

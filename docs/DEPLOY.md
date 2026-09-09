# Deploying this profile

The repository whose name equals your username is special: its `README.md`
renders on your profile page. For you that is
[`MyDrift-user/MyDrift-user`](https://github.com/MyDrift-user/MyDrift-user),
which already exists and already contains a README.

---

## 1. Review before publishing

This is a public page. Two things to settle first.

**Personal detail.** The `whoami` block states role, education track and
country. Trim whatever you would rather not publish.

**Infrastructure.** Keep host names, domains and VM identifiers off the page.
An architecture diagram of the homelab was built and then cut, partly for
layout and partly for this: a public profile that names real infrastructure
hands an attacker a free reconnaissance pass. If you add one back, keep it
generic -- "reverse proxy", "SSO provider", "git forge" -- which communicates
competence without naming a target.

---

## 2. Preview it first

Nothing below needs to touch GitHub.

```bash
python3 scripts/gen_dashboard.py --user MyDrift-user --out assets --demo
python3 scripts/preview.py
```

Opens `http://127.0.0.1:8000/preview.html`, rendered through GitHub's own
markdown API with a light/dark toggle. Two expected warnings before the first
CI run: the `output`-branch assets are missing, and the README-health badge
shows *repo or workflow not found* because the workflow does not exist upstream
yet. Both clear once step 5 has run.

If you want true end-to-end fidelity without touching your profile, push to a
**non-default branch** instead:

```bash
git push origin main:preview
```

Your profile renders only the **default branch**, so a `preview` branch is
inert. Open it at
`github.com/MyDrift-user/MyDrift-user/blob/preview/README.md`. A throwaway
private repo works too, though the `output`-branch image URLs stay pinned to
`MyDrift-user/MyDrift-user` and will 404 there.

---

## 3. Push it

```bash
cd ~/Projects/github-profile
git init -b main
git remote add origin git@github.com:MyDrift-user/MyDrift-user.git
git fetch origin

# Keep the old README recoverable.
git checkout -b backup origin/main && git checkout main

git add .
git commit -m "feat: rebuild profile around self-hosted, CI-verified assets"
git push -u origin main --force-with-lease
```

`--force-with-lease` rather than `--force`: it refuses if the remote moved
since your fetch.

---

## 4. Enable Actions write access

Settings → Actions → General → Workflow permissions →
**Read and write permissions** → Save.

Without this, `generate.yml` cannot publish the `output` branch and every run
fails on the final step.

---

## 5. First run

Actions → *generate profile assets* → **Run workflow**.

It renders the dashboard, the snake and the 3D calendar, then pushes all six
SVGs to the `output` branch. The `404`s in the README resolve the moment
that branch exists. Afterwards it runs itself daily at 03:17 UTC.

Verify:

```bash
python3 scripts/check_links.py README.md
```

Exit code 0 means every embedded asset resolves.

---

## 6. Optional: a token for private contributions

The built-in `GITHUB_TOKEN` sees public activity only. If much of your work
lives in private repositories, the dashboard will undercount badly.

1. [github.com/settings/tokens](https://github.com/settings/tokens) → classic →
   scopes `public_repo` and `read:user`.
2. Repository → Settings → Secrets and variables → Actions → new secret
   `PROFILE_TOKEN`.

`generate.yml` prefers it automatically and falls back when absent. The same
secret unlocks `metrics.yml`.

---

## 7. Iterating on the dashboard

```bash
python3 scripts/gen_dashboard.py --user MyDrift-user --out assets --demo
rsvg-convert -w 900 assets/dashboard-dark.svg -o /tmp/preview.png
xdg-open /tmp/preview.png
```

`--demo` uses deterministic synthetic data, so layout work costs no API quota
and needs no token. Colours live in `THEMES`; layout lives in `render()`.

---

## Troubleshooting

**Images still 404 after a green run.** Confirm the `output` branch exists and
holds the twelve SVGs. Check the *Publish to output branch* step actually ran.

**Dashboard shows zeros.** GraphQL fell back to REST, which has no
contributions endpoint. Read the step log; the script prints its data source.
Usually a token scope problem.

**An updated image looks stale.** GitHub's camo cache. It clears on its own;
a hard reload usually beats it.

**`link health` opens an issue.** Working as designed — an embedded asset died.
Consult [CATALOG.md](CATALOG.md) for a Tier 1 or Tier 2 replacement. It reuses
one rolling issue rather than filing a new one each week.

**Scheduled runs stop after 60 days of no repository activity.** GitHub
disables cron on dormant repositories and emails you. Any push re-enables it.

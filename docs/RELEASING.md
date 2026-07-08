# Releasing Hearth

How releases and the container package are published. Applies to humans and agents alike.

## What a release produces

1. **A GitHub Release** at `github.com/RadekalOne/hearth/releases` — tagged snapshot + notes.
2. **A container image** at `ghcr.io/radekalone/hearth-memory` — the memory service, built by CI ([.github/workflows/publish.yml](../.github/workflows/publish.yml)) on every `v*` tag, tagged both `<version>` (e.g. `0.1.0`) and `latest`. Public repo → public image; users can `docker compose pull memory` instead of building locally.

The Conduit/Element images are upstream and pinned in `docker-compose.yml` — they are not part of our publish pipeline.

## Cutting a release

```bash
# 1. Make sure main is green and pushed, and version pins/docs are current.
# 2. Tag and push — this alone triggers the image build:
git tag v0.2.0
git push origin v0.2.0

# 3. Create the release with notes (what changed, what's verified, known limitations):
gh release create v0.2.0 --title "Hearth v0.2.0 — <summary>" --notes "<notes>"

# 4. Verify:
gh run list --workflow publish.yml --limit 1        # expect success
# public pull check (anonymous token — proves users can pull without auth):
TOK=$(curl -s "https://ghcr.io/token?scope=repository:radekalone/hearth-memory:pull" | jq -r .token)
curl -s -H "Authorization: Bearer $TOK" https://ghcr.io/v2/radekalone/hearth-memory/tags/list
```

## Gotchas (learned the hard way)

- **Pushing workflow files needs the `workflow` OAuth scope.** If a push touching `.github/workflows/` is rejected, run `gh auth refresh -h github.com -s workflow` (interactive, browser device-code flow — a human must do it).
- **The tag must contain the workflow file** for the versioned build to trigger. Tagging a commit that predates the workflow builds nothing.
- **Package visibility**: images published from Actions with `GITHUB_TOKEN` inherit the repo's public visibility automatically — no manual settings click needed. Verify with the anonymous pull check above, not the packages API (our token lacks `read:packages`).
- **Release notes style**: state what's e2e-verified vs. beta explicitly — the README Status section and PROJECT.md known-issues list must stay consistent with the notes.
- Current non-blocking warning: the workflow's actions target Node 20 (deprecated on GitHub runners); bump action versions on next workflow edit.

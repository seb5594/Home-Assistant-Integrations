# Release catalog maintenance

`scripts/sync_catalog.py` discovers public, active repositories owned by **seb5594**, named
`hass-<project>-integration` or `Home-Assistant-<project>-Integration`. It uses public GitHub APIs and release
assets; the private workflow engine and its token are not needed.

## Release selection

Use `GET /repos/<owner>/<repo>/releases/latest`, excluding drafts and prereleases. A source needs an uploaded
integration ZIP named by its tagged `hacs.json` or `<domain>.zip`. Never fall back to the default branch, an
arbitrary commit, an unpublished Git tag, or an older release when the latest release package is absent.
Resolve the release tag itself to a commit; `target_commitish` can be a moving branch and is not a pin.

Friendly names and versions come from the actual uploaded ZIP. The packaged manifest must match the release
tag (apart from `v`). Verify the asset's digest where supplied. Logos are copied from the same ZIP. Source
README/changelog metadata comes from the release commit. Failed requests stop the run instead of pruning
an incomplete discovery result. Sources with no eligible release package are skipped.

Generated output:

- `.gitmodules` and `integrations/<domain>` gitlinks, pinned to release commits;
- `.github/catalog.json`, preserving the repository/commit format;
- `custom_components/integration_catalog/catalog.json`, with release tags, exact URLs and package checksums;
- `catalog-feed.json` (schema 2), a small release-only feed for installed hubs;
- `assets/brands/` logos and attribution;
- `README.md`, from `templates/README.md`.

Run `python scripts/sync_catalog.py --from-lock` to regenerate presentation and feed offline. A full sync also
stages submodule pins with `git update-index`; use a dedicated clean checkout. The workflow runs hourly at
minute 17 UTC, on demand, and on `update-integrations` dispatches. Unchanged output produces no commit.

## Hub releases

Changed release metadata bumps the hub's calendar version, with a monotonic counter for the same day.
Increment `manifest.json` when changing hub behavior too. `scripts/build_release.py` builds
`dist/integration_catalog.zip` with component files at the ZIP root and a `SHA256SUMS.txt` file.

`.github/workflows/release.yml` checks the main branch and publishes `v<manifest version>` with those assets
only after lint, catalog and real Home Assistant tests pass. It runs on relevant main-branch changes and
after successful catalog synchronizations. The latter trigger is needed because GITHUB_TOKEN-created
catalog commits do not trigger ordinary push workflows. Existing releases are skipped, never overwritten.
HACS uses the uploaded ZIP and hides the default branch from the normal download selector.

## Runtime boundary

HACS alone installs, updates and removes integrations. The hub contains no installer and never writes child
component files. The adapter only registers repositories through HACS' runtime API, preserving validation
and skip policies. This API is internal: keep it isolated in `hacs_bridge.py`, surface errors and retain manual links.
The hub's own Store tracks seen repositories; it never directly edits HACS storage.

## Checks

Run `python -m unittest discover -s tests -p 'test_*.py'` for release selection, metadata and package checks.
CI also runs Ruff, builds the HACS ZIP, verifies generated files, and runs the HA tests on 2025.1.0 and 2026.10.4.

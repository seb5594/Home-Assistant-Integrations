# Catalog maintenance

The catalog owns its generator: `scripts/sync_catalog.py`. It uses public GitHub APIs and archives.
The private workflow engine and `ORCHESTRATION_PAT` checkout are no longer needed here.

## What gets listed

Public, active repositories owned by **[seb5594](https://github.com/seb5594)** named
`hass-<project>-integration` or `Home-Assistant-<project>-Integration` that contain `custom_components/<domain>/manifest.json`.
Private, archived and disabled repositories are skipped entirely, so they are neither listed nor
pinned; a repository that turns private is removed on the next run.

## Updates

| Trigger | Behavior |
| --- | --- |
| Schedule | Every hour at minute 17, UTC |
| Manual | **Actions → Synchronize integration catalog → Run workflow** |
| integration release | The integration pipeline sends an `update-integrations` dispatch |
| Edit of `update.yml` | For example a new engine pin |

Each run reads metadata at the default-branch commit and records it in `.github/catalog.json`.
Unchanged results produce no commit. Requests failing partway stop the run instead of pruning a partial catalog.
Duplicate domains also stop discovery. The synchronizer generates:

- `.gitmodules` and `integrations/<domain>` gitlinks, pinned to source commits;
- `.github/catalog.json`, retaining the repository/commit format;
- `custom_components/integration_catalog/catalog.json`, with friendly names, minimum HA versions and a per-file SHA-256 allowlist;
- `assets/brands/` source logos and attribution;
- `README.md`, from the editable `templates/README.md` template.

Edit templates and generator code instead of generated output. `python scripts/sync_catalog.py --from-lock`
renders the README offline without altering pins or the Git index. A full `python scripts/sync_catalog.py`
stages gitlinks with `git update-index`; run it in a clean dedicated branch/checkout.
The workflow stages only catalog paths, serializes runs and never force-pushes.

## Versions

Changed metadata bumps the installer's calendar version. HACS can install the default branch without
a GitHub release. Increment `custom_components/integration_catalog/manifest.json`'s version when changing
installer behavior too. Each source keeps its independent releases, licenses and CI.
Root license and notice files are preserved under `.source-license/` when installing a component.

## Checks

Run `python -m unittest discover -s tests -p "test_*.py"` for filesystem/archive and generator checks.
CI also runs Ruff and tests the config/options flows with Home Assistant on Linux. The Windows
checkout can run the standard-library tests without installing Home Assistant.

## Design boundaries

The installer is an experimental opt-in filesystem manager. It must not edit HACS storage, import source
code while installing, overwrite a directory it does not own, or mutate child components on HA startup.

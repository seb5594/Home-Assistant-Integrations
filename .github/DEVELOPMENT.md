# Catalog maintenance

This repository is generated. `.github/workflows/update.yml` runs the shared catalog action from
the private `hass-workflows` engine; the README and `.github/catalog.json` are rewritten by it and should not be edited by hand.

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

Integrations are only described, never cloned: each run reads their metadata at the current default-branch commit and records that commit in `.github/catalog.json`.
Unchanged results produce no commit. The workflow needs the Actions secret `ORCHESTRATION_PAT`
with **Contents: Read** on `seb5594/hass-workflows`.

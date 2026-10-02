# Catalog maintenance

This repository is generated. `.github/workflows/update.yml` runs the shared catalog action from
the private `hass-workflows` engine; the README is rewritten by it and should not be edited by hand.

## What gets listed

Public, active repositories owned by **[seb5594](https://github.com/seb5594)** named
`hass-<project>-integration` or `Home-Assistant-<project>-Integration` that contain
`custom_components/<domain>/manifest.json`. Private, archived and disabled repositories are
skipped entirely, so they are neither listed nor pinned; a repository that turns private is
removed on the next run.

## Updates

| Trigger | Behavior |
| --- | --- |
| Schedule | Every hour at minute 17, UTC |
| Manual | **Actions → Synchronize integration catalog → Run workflow** |
| Integration release | The integration pipeline sends an `update-integrations` dispatch |
| Edit of `update.yml` | For example a new engine pin |

Each run pins the latest default-branch commit of every listed integration as a Git submodule.
Unchanged results produce no commit. The workflow needs the Actions secret `ORCHESTRATION_PAT`
with **Contents: Read** on `seb5594/hass-workflows`.

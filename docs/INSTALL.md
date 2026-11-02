# seb5594's Integration Hub

## What this workaround does

HACS supports one integration per repository. This repository contains **seb5594's Integration Hub**
(`integration_catalog`). The hub registers the individual catalog repositories in HACS, where you choose
what to download and configure. HACS then manages each source integration's normal releases and updates.
Adding a repository does not install its integration or change its configuration.

Automatic registration is an **experimental HACS adapter**. It calls the runtime registration and persistence
functions used by HACS itself, with normal validation enabled. These are internal APIs, not a stable public
extension contract. The hub never edits HACS storage files directly, disables validation, or patches HACS.

## First installation

1. In **HACS → ⋮ → Custom repositories**, add `https://github.com/seb5594/Home-Assistant-Integrations`, category **Integration**.
2. Download **seb5594's Integration Hub**.
3. Restart Home Assistant.
4. In **Settings → Devices & services → Add integration**, search for **seb5594's Integration Hub**.
5. Leave automatic HACS registration and new-integration notifications enabled, or change these settings.
6. Open HACS. The catalog's individual repositories are added automatically; choose the integrations to download.
7. Follow HACS' restart instructions and each integration's own configuration documentation.

The hub requires Home Assistant **2025.1.0 or newer** and an existing configured HACS installation for
automatic registration. It reuses HACS' GitHub connection; no additional token, Git client, Supervisor or
shell access is required. The public discovery feed is fetched from `raw.githubusercontent.com`.
If HACS is unavailable, discovery notifications and direct add links still work. Failed registrations
are retried, with a notification for unavailable/incompatible APIs. The hub checks again one minute
after startup to accommodate HACS' startup tasks, then hourly. You can press **Refresh catalog** immediately.

## New integration notifications

The hub checks the public `catalog-feed.json` hourly. The repository synchronizer refreshes that feed
hourly and after an integration's release dispatch. New public catalog projects produce a Home Assistant
persistent notification with their friendly names, versions and direct HACS links. Registration happens
before the notification when HACS is available. Notifications do not mean a component was installed.

The first successful check (or bundled fallback when offline) establishes a baseline. Seen repository
IDs are persisted across restarts, so unchanged catalogs and new versions of an existing project do not
repeat the notification. Updates of downloaded integrations remain HACS' responsibility. If the feed cannot
be read or validated, the hub retains its last known catalog; it does not infer removals or uninstall anything.

Use **Configure → Hub settings** to disable registration and/or new-project notifications. Disabling
registration does not remove repositories already added. Removing the hub leaves those repositories in HACS.

## Optional snapshot installer (advanced)

The original direct-file installer remains under **Configure → Install snapshots (advanced)**. It downloads
the exact component commits and SHA-256 allowlists shipped with the installed hub version. It is independent
of HACS' component management. Do not download the same integration using both systems.

1. Update the catalog in HACS when a new catalog version is available.
2. Restart Home Assistant so the new catalog code and snapshot list are loaded.
3. Open **Settings → Devices & services → seb5594's Integration Hub → Configure → Install snapshots (advanced)**.
4. Select the components to install/update and submit. An unchanged snapshot is skipped.
5. Restart Home Assistant if anything changed.

Snapshot updates are applied only when requested in this dialog. Normal startup never modifies component files.
Selecting fewer integrations does **not** uninstall the others. Components not selected remain at their installed versions.
The catalog follows the default branch of each public source repository, so snapshots can include unreleased changes.
The normal automatic-registration mode provides each project's independent HACS release selection and update entities.
The snapshot installer checks the source's minimum HA version before downloading and requires internet access to
`codeload.github.com`. The remaining sections describe its ownership checks, backups and removal.

## Existing installations and local changes

The installer refuses an existing `custom_components/<domain>` unless that directory has a valid catalog
ownership marker and all its managed files are unchanged. It never silently adopts a manual installation
or a separately installed HACS integration. Do not manage a component with both systems.

To migrate, make a Home Assistant backup, stop Home Assistant, move the existing component directory
outside `custom_components/`, remove that project's separate HACS download if applicable, then start
Home Assistant and install it through the catalog. Keep the original component's configuration entry;
the domain stays the same. Restart after installation. To return to direct HACS management, stop Home
Assistant and move the catalog-managed folder outside `custom_components/`, then install the individual
repository. Keep the moved folder until you have verified the migration.

## Backups, failures and rollback

Every replacement moves the complete old directory, including its ownership marker, to
`<config>/.integration_catalog_backups/<domain>-<UTC timestamp>/`. Backups are retained until you remove
them yourself. The installer does not alter Home Assistant configuration entries or entity registries.

If download, checksum, compatibility or initial ownership validation fails, no selected component is changed.
If a filesystem failure occurs while applying a batch, earlier components may already have been installed;
the error lists them. A failed folder swap restores that folder from its backup when possible.

To roll back, stop Home Assistant, move the current `custom_components/<domain>/` elsewhere, and move
the corresponding backup directory back to `custom_components/<domain>/`. Start Home Assistant.
Dependency changes and configuration migrations performed by the source integration may require a full
Home Assistant backup restore instead; folder backups are not a substitute for that backup.

If a process crash interrupts the two folder renames, restore the retained backup before restarting.
An interrupted process can leave `<config>/.integration-catalog.lock`; remove it **only after confirming
no installation is running**, normally with Home Assistant stopped. A cancelled UI flow can leave its
executor download running briefly; the lock prevents a second installation from writing concurrently.

## Removal

Removing the catalog config entry or uninstalling the catalog through HACS leaves child integrations and
their backups in place. To remove a child, remove its integration/configuration in Home Assistant,
stop Home Assistant, remove its `custom_components/<domain>/` directory, then start Home Assistant.
For YAML integrations, remove the corresponding YAML configuration as directed by the source project.

## Validation status

The repository tests the installer filesystem behavior, archive checks and catalog generation.
Its CI also tests the config/options flows with Home Assistant. This does not establish compatibility
with every device or validate the behavior of the source integrations on a real installation.

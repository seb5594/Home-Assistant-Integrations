# Install from one catalog

## What this workaround does

HACS supports one integration per repository. This repository contains one HACS integration,
**Home Assistant Integration Catalog** (`integration_catalog`). Its setup dialog downloads
only the components you select, at the commits and file checksums shipped with the catalog.
They retain their original domains, names, configuration and requirements.

This is an **experimental custom installer**, not a native HACS multi-integration repository.
HACS tracks only the catalog, not the versions of the child components. No HACS internals,
storage files, monkey patches, symlinks or archive traversal tricks are used.

## First installation

1. In **HACS → ⋮ → Custom repositories**, add `https://github.com/seb5594/Home-Assistant-Integrations`, category **Integration**.
2. Download **Home Assistant Integration Catalog (experimental installer)**.
3. Restart Home Assistant.
4. In **Settings → Devices & services → Add integration**, search for **Home Assistant Integration Catalog**.
5. Select one or more integrations and acknowledge the installer behavior. The dialog shows each friendly name, snapshot version and minimum Home Assistant version.
6. Wait for the result. Downloads and checks finish before any component is installed.
7. Restart Home Assistant after an installation or update.
8. Add/configure the installed integrations under their original names, following their own documentation. Integrations that require YAML still require YAML.

The catalog requires Home Assistant **2025.1.0 or newer**. Each selected component can require a later version;
the installer checks the minimum declared by its source repository before downloading.
Internet access to `codeload.github.com` is required during installation. No GitHub token, Git client,
Supervisor or shell access is needed for normal installation.

## Updates and adding more integrations

1. Update the catalog in HACS when a new catalog version is available.
2. Restart Home Assistant so the new catalog code and snapshot list are loaded.
3. Open **Settings → Devices & services → Home Assistant Integration Catalog → Configure**.
4. Select the components to install/update and submit. An unchanged snapshot is skipped.
5. Restart Home Assistant if anything changed.

Updates are applied only when requested in this dialog. Normal startup never modifies component files.
Selecting fewer integrations does **not** uninstall the others. Components not selected remain at their installed versions.
The catalog follows the default branch of each public source repository, so snapshots can include unreleased changes.
Use the individual HACS repositories if you want each project's independent release selection and update entities.

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

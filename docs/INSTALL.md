# seb5594's Integration Hub

The hub discovers released projects, adds their repositories to HACS, and notifies you about new integrations.
**HACS alone installs, updates and removes integration files.** The hub has no component installer.

## Setup

1. Add `https://github.com/seb5594/Home-Assistant-Integrations` under **HACS → ⋮ → Custom repositories**, category **Integration**.
2. Download the latest release of **seb5594's Integration Hub**, then restart Home Assistant.
3. Under **Settings → Devices & services**, select **Configure** on the discovered **seb5594's Integration Hub** card. If it is missing, use **Add integration** and search for the hub.
4. Leave automatic HACS registration and new-integration notifications enabled, or adjust them.
5. Open HACS and download the individual integrations you want. Follow HACS' restart instructions and their own setup guides.

The hub requires Home Assistant **2025.1.0 or newer**. Automatic registration requires a configured HACS
installation and reuses its GitHub connection. No additional token, shell, Supervisor or Git client is needed.
The discovery feed is fetched from `raw.githubusercontent.com`.

Automatic discovery uses this Home Assistant instance's own mDNS announcement. Zeroconf is enabled
by default. A restart after installation is required. Configured or ignored hubs are not suggested
again. If Zeroconf is disabled or mDNS is blocked, add the hub manually.

The hub's integration domain is `seb5594_integration_catalog`. Existing installations using the old
`integration_catalog` domain need the old hub configuration entry removed, the hub updated/redownloaded
through HACS, a Home Assistant restart, and the hub added again. Reapply the two hub settings afterward.
The individual integrations and their HACS repositories are retained.

## Published releases only

The catalog uses GitHub's **latest published release**, excluding drafts and releases marked as prereleases.
It reads the uploaded integration ZIP, verifies the package digest when GitHub provides one, and checks that
its manifest version matches the release tag (allowing the usual `v` prefix). The tag is resolved to its exact
commit for the source submodule; a release's moving `target_commitish` is never used as a source pin.

Projects with no eligible release or no uploaded integration ZIP are not offered. There is no default-branch
or arbitrary-commit fallback. The displayed version, release page, package download and notification links all
refer to that latest release. HACS keeps its normal release management; the hub does not override existing
user choices, pin a HACS integration permanently to an old release, or download its files.

The hub itself is distributed as `seb5594_integration_catalog.zip` on a versioned `v<manifest version>` release.
Its HACS manifest uses release ZIPs and hides the default branch from the normal download selector.
Catalog-only changes never bump the hub version or publish a hub release; they arrive through the live feed.
Maintainers bump the manifest version deliberately when the integration itself changes.

## New integration notifications

The hub checks the public release feed hourly. The repository synchronizer refreshes it hourly and after
release dispatches. A newly listed project produces a Home Assistant notification with its friendly name,
release tag, release ZIP and direct HACS link. Its repository is added to HACS first when available.

The first check establishes a baseline. Seen repository identities are saved across restarts; version changes
of an existing project are left to HACS' normal update handling. A failed feed request retains the last known
release catalog. It never implies an uninstall or a branch fallback.

Automatic registration uses an **experimental adapter to HACS' internal runtime API**, with normal validation
enabled. It never directly edits HACS storage files or patches HACS. If HACS is missing, disabled or incompatible,
the hub reports the problem and retries. Manual HACS links remain available.

Use **Configure** to disable registration and/or notifications. **Refresh catalog** checks immediately.
An extra check runs one minute after startup, allowing HACS' own startup work to finish.

## Removal and existing installations

Disabling or removing the hub leaves HACS repositories and installed integrations in place. Manage and remove
them in HACS and Home Assistant as usual. The hub does not adopt, overwrite or remove manually installed files.

The earlier branch-only snapshot installer was removed. If you tested it, back up any manually installed
components and follow the usual migration to HACS; the hub does not silently transfer ownership of those files.

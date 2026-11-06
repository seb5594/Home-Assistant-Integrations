"""Capability-checked adapter to HACS and the built-in Marketplace registry.

Neither store promises a stable integration API for this operation. Keep internal
runtime calls here; never modify .storage files or bypass repository validation.
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass, field

from awesomeversion import AwesomeVersion, AwesomeVersionException
from homeassistant import const as ha_const
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState

MARKETPLACE_FROM = "2026.11.0"
SIGNATURE_OPTIONS = {}
if sys.version_info >= (3, 14):
    from annotationlib import Format

    SIGNATURE_OPTIONS["annotation_format"] = Format.STRING


class HacsUnavailable(Exception):
    """The selected store is absent, starting, disabled or has a changed API."""


@dataclass
class RegistrationResult:
    added: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    backend: str = "HACS"


@dataclass
class StoreSelection:
    name: str
    ha_version: str
    signals: list[str]
    manager: object | None = field(default=None, repr=False)
    error: str | None = None

    def diagnostics(self):
        """Export only policy information, never a manager or its credentials."""
        return {"backend": self.name, "home_assistant_version": self.ha_version,
                "marketplace_from": MARKETPLACE_FROM, "signals": self.signals,
                "available": False, "reason": self.error}


async def async_select_store(hass) -> StoreSelection:
    """Use the new store once required by version or detected in this install.

    Version is the announced stable cutover. Actual core metadata and entries
    also cover betas/backports before that date. No optional component code is
    imported, and detection is repeated on every refresh.
    """
    version, signals = ha_const.__version__, []
    try:
        if AwesomeVersion(version) >= AwesomeVersion(MARKETPLACE_FROM):
            signals.append("ha_version")
    except AwesomeVersionException:
        # Custom/dev version strings still use the actual installation signals.
        pass
    replacement = getattr(loader, "BLOCKED_CUSTOM_INTEGRATIONS", {}).get("hacs")
    if getattr(replacement, "replaced_by", None) == "marketplace":
        signals.append("core_replacement")
    try:
        integration = await loader.async_get_integration(hass, "marketplace")
    except loader.IntegrationNotFound:
        pass
    else:
        if integration.is_built_in:
            signals.append("builtin_integration")
    entries = hass.config_entries.async_entries("marketplace")
    if entries:
        signals.append("config_entry")
    selected = StoreSelection("Marketplace" if signals else "HACS", version, signals)
    if signals:
        for entry in entries:
            if entry.state is ConfigEntryState.LOADED and not getattr(entry, "disabled_by", None):
                manager = getattr(entry, "runtime_data", None)
                if manager is not None:
                    selected.manager = manager
                    return selected
        selected.error = "Marketplace is not loaded" if entries else "Marketplace is required but not configured"
    else:
        selected.manager = hass.data.get("hacs")
        if selected.manager is None:
            selected.error = "HACS is not loaded"
    return selected


def registry_api(selection):
    """Validate the entire call contract before any repository can be changed."""
    if selection.error:
        raise HacsUnavailable(selection.error)
    hacs, name = selection.manager, selection.name
    if getattr(getattr(hacs, "system", None), "disabled", False):
        raise HacsUnavailable(f"{name} is disabled")
    if getattr(getattr(hacs, "status", None), "startup", False):
        raise HacsUnavailable(f"{name} is still starting")
    register = getattr(hacs, "async_register_repository", None)
    lookup = getattr(getattr(hacs, "repositories", None), "get_by_full_name", None)
    save = getattr(getattr(hacs, "data", None), "async_write", None)
    categories = getattr(getattr(hacs, "common", None), "categories", ()) or ()
    if not callable(register) or not callable(lookup) or not callable(save) or "integration" not in categories:
        raise HacsUnavailable(f"This {name} version does not provide the expected registry API")
    try:
        inspect.signature(register, **SIGNATURE_OPTIONS).bind(
            repository_full_name="seb5594/example", category="integration", check=True,
        )
        inspect.signature(lookup, **SIGNATURE_OPTIONS).bind("seb5594/example")
        inspect.signature(save, **SIGNATURE_OPTIONS).bind()
        if (not inspect.iscoroutinefunction(register) or not inspect.iscoroutinefunction(save)
            or inspect.iscoroutinefunction(lookup)):
            raise TypeError("Registration/persistence must be async and lookup must be sync")
    except (TypeError, ValueError) as err:
        raise HacsUnavailable(f"The {name} repository registration API has changed") from err
    if name == "Marketplace":
        if not getattr(hacs, "github_connected", False):
            raise HacsUnavailable("Open Settings > Marketplace and connect GitHub before adding catalog repositories")
        if not getattr(hacs, "warning_acceptances", {}):
            raise HacsUnavailable("Open Settings > Marketplace and accept the first-use notice before adding catalog repositories")
    return register, lookup, save


async def async_store_diagnostics(hass):
    """Explain selection and readiness without modifying or registering anything."""
    selected = await async_select_store(hass)
    data = selected.diagnostics()
    try:
        registry_api(selected)
    except HacsUnavailable as err:
        data["reason"] = str(err)
    else:
        data["available"] = True
    return data


async def async_register_repositories(hass, catalog: list[dict]) -> RegistrationResult:
    """Register and persist repository metadata, without downloading components."""
    selected = await async_select_store(hass)
    register, lookup, save = registry_api(selected)
    hacs = selected.manager

    result = RegistrationResult(backend=selected.name)
    try:
        for item in catalog:
            repository = item["repository"]
            renamed = getattr(hacs.common, "renamed_repositories", {})
            lookup_name = renamed.get(repository, repository)
            if lookup(lookup_name) is not None:
                result.existing.append(repository)
                continue
            try:
                # Preserve HACS' skip/removed-repository policies, unlike the add UI
                # which clears skip on an explicit manual retry.
                errors = await register(
                    repository_full_name=repository, category="integration", check=True,
                )
                if lookup(lookup_name) is None:
                    result.failed[repository] = str(errors or f"{selected.name} did not register the repository")
                else:
                    result.added.append(repository)
            except Exception as err:
                result.failed[repository] = str(err)
    finally:
        # Persist successful additions even if another repository or task fails.
        if result.added:
            await save()
    return result

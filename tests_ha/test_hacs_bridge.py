"""Test the internal HACS adapter contract without touching HACS storage."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.seb5594_integration_catalog import hacs_bridge
from custom_components.seb5594_integration_catalog.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.seb5594_integration_catalog.hacs_bridge import (
    HacsUnavailable,
    async_register_repositories,
    async_store_diagnostics,
)


@pytest.fixture(autouse=True)
def legacy_store_baseline():
    """Keep policy cases independent of the HA version running the test suite.

    Future Marketplace cores must still exercise legacy HACS cases; individual
    tests override these signals to cover the transition and new store.
    """
    with patch.object(hacs_bridge.ha_const, "__version__", "2026.10.4"), \
        patch.object(hacs_bridge.loader, "BLOCKED_CUSTOM_INTEGRATIONS", {}, create=True), \
        patch.object(hacs_bridge.loader, "async_get_integration", side_effect=hacs_bridge.loader.IntegrationNotFound("marketplace")):
        yield


def hacs_stub(hass):
    registry = {}

    async def register(repository_full_name, category, *, check=True):
        assert category == "integration"
        assert check is True
        registry[repository_full_name] = object()

    hacs = SimpleNamespace(
        common=SimpleNamespace(categories={"integration"}),
        github_connected=True, warning_acceptances={"admin": "accepted"},
        status=SimpleNamespace(startup=False), system=SimpleNamespace(disabled=False),
        repositories=SimpleNamespace(get_by_full_name=registry.get),
        data=SimpleNamespace(async_write=AsyncMock()),
        async_register_repository=register,
    )
    hass.data["hacs"] = hacs
    return hacs, registry


async def test_registers_validated_metadata_once_and_persists(hass, catalog):
    hacs, registry = hacs_stub(hass)
    result = await async_register_repositories(hass, catalog)
    assert result.added == [catalog[0]["repository"]]
    assert len(registry) == 1
    hacs.data.async_write.assert_awaited_once()
    result = await async_register_repositories(hass, catalog)
    assert result.existing == [catalog[0]["repository"]]
    assert result.added == []
    hacs.data.async_write.assert_awaited_once()


async def test_hacs_validation_failure_is_not_reported_as_added(hass, catalog):
    hacs, _ = hacs_stub(hass)
    hacs.async_register_repository = AsyncMock(return_value=["invalid manifest"])
    result = await async_register_repositories(hass, catalog)
    assert result.added == []
    assert "invalid manifest" in result.failed[catalog[0]["repository"]]
    hacs.data.async_write.assert_not_awaited()


async def test_respects_hacs_repository_rename_mapping(hass, catalog):
    hacs, registry = hacs_stub(hass)
    original = catalog[0]["repository"]
    renamed = "seb5594/hass-renamed-integration"
    hacs.common.renamed_repositories = {original: renamed}
    async def register(repository_full_name, category, *, check=True):
        assert repository_full_name == original
        registry[renamed] = object()
    hacs.async_register_repository = register
    result = await async_register_repositories(hass, catalog)
    assert result.added == [original]
    hacs.data.async_write.assert_awaited_once()


async def test_hacs_absent_starting_disabled_or_incompatible(hass, catalog):
    with pytest.raises(HacsUnavailable, match="not loaded"):
        await async_register_repositories(hass, catalog)
    hacs, _ = hacs_stub(hass)
    hacs.status.startup = True
    with pytest.raises(HacsUnavailable, match="still starting"):
        await async_register_repositories(hass, catalog)
    hacs.status.startup = False
    hacs.system.disabled = True
    with pytest.raises(HacsUnavailable, match="disabled"):
        await async_register_repositories(hass, catalog)
    hacs.system.disabled = False
    async def incompatible(repository):
        raise AssertionError("Must not call an incompatible API")
    hacs.async_register_repository = incompatible
    with pytest.raises(HacsUnavailable, match="API has changed"):
        await async_register_repositories(hass, catalog)


async def test_cancellation_persists_successful_prior_registrations(hass, catalog):
    hacs, registry = hacs_stub(hass)
    first = catalog[0]["repository"]
    async def register(repository_full_name, category, *, check=True):
        if repository_full_name != first:
            raise asyncio.CancelledError
        registry[repository_full_name] = object()
    hacs.async_register_repository = register
    with pytest.raises(asyncio.CancelledError):
        await async_register_repositories(hass, catalog + [{"repository": "seb5594/hass-next-integration"}])
    hacs.data.async_write.assert_awaited_once()


async def test_marketplace_uses_loaded_entry_runtime_data_instead_of_legacy_hacs(hass, catalog):
    """Exercise the manager contract used by HA's upcoming built-in store."""
    marketplace, registry = hacs_stub(hass)
    hass.data["hacs"] = object()  # A stale manager must not win after migration.
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=marketplace)
    with patch.object(hass.config_entries, "async_entries", return_value=[entry]) as entries:
        result = await async_register_repositories(hass, catalog)
    entries.assert_called_once_with("marketplace")
    assert result.backend == "Marketplace"
    assert result.added == [catalog[0]["repository"]]
    assert len(registry) == 1
    marketplace.data.async_write.assert_awaited_once()


@pytest.mark.parametrize("state, runtime", [
    (ConfigEntryState.NOT_LOADED, None), (ConfigEntryState.LOADED, None),
])
async def test_marketplace_not_ready_does_not_use_old_hacs(hass, catalog, state, runtime):
    hacs, registry = hacs_stub(hass)
    with patch.object(hass.config_entries, "async_entries", return_value=[
        SimpleNamespace(state=state, runtime_data=runtime),
    ]), pytest.raises(HacsUnavailable, match="Marketplace is not loaded"):
        await async_register_repositories(hass, catalog)
    assert not registry
    hacs.data.async_write.assert_not_awaited()


async def test_marketplace_also_validates_its_registry_capabilities(hass, catalog):
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=object())
    with patch.object(hass.config_entries, "async_entries", return_value=[entry]), \
        pytest.raises(HacsUnavailable, match="Marketplace version"):
        await async_register_repositories(hass, catalog)


@pytest.mark.parametrize("version", ["2026.11.0", "2026.11.3", "2026.12.0", "2027.1.0"])
async def test_new_ha_requires_marketplace_even_without_an_entry(hass, catalog, version):
    hacs, registry = hacs_stub(hass)
    with patch.object(hacs_bridge.ha_const, "__version__", version), \
        pytest.raises(HacsUnavailable, match="Marketplace is required but not configured"):
        await async_register_repositories(hass, catalog)
    assert not registry
    hacs.data.async_write.assert_not_awaited()


@pytest.mark.parametrize("version", ["2024.1.2", "2026.10.4", "2026.11.0b0", "custom-dev"])
async def test_old_or_unknown_version_uses_installation_evidence(hass, catalog, version):
    hacs, _ = hacs_stub(hass)
    with patch.object(hacs_bridge.ha_const, "__version__", version):
        result = await async_register_repositories(hass, catalog)
    assert result.added == [catalog[0]["repository"]]
    hacs.data.async_write.assert_awaited_once()


@pytest.mark.parametrize("signal", ["builtin_integration", "core_replacement"])
async def test_detected_marketplace_blocks_legacy_before_version_cutover(hass, catalog, signal):
    hacs, registry = hacs_stub(hass)
    integration = SimpleNamespace(is_built_in=signal == "builtin_integration")
    replacements = {"hacs": SimpleNamespace(replaced_by="marketplace")} if signal == "core_replacement" else {}
    with patch.object(hacs_bridge.ha_const, "__version__", "2026.11.0b0"), \
        patch.object(hacs_bridge.loader, "async_get_integration", return_value=integration), \
        patch.object(hacs_bridge.loader, "BLOCKED_CUSTOM_INTEGRATIONS", replacements, create=True), \
        pytest.raises(HacsUnavailable, match="Marketplace is required"):
        await async_register_repositories(hass, catalog)
    assert not registry
    hacs.data.async_write.assert_not_awaited()


async def test_pending_marketplace_is_recognized_on_the_next_refresh(hass, catalog):
    marketplace, registry = hacs_stub(hass)
    hass.data["hacs"] = object()
    entry = SimpleNamespace(state=ConfigEntryState.NOT_LOADED, runtime_data=None)
    with patch.object(hass.config_entries, "async_entries", return_value=[entry]):
        with pytest.raises(HacsUnavailable, match="not loaded"):
            await async_register_repositories(hass, catalog)
        entry.state, entry.runtime_data = ConfigEntryState.LOADED, marketplace
        result = await async_register_repositories(hass, catalog)
    assert result.added == [catalog[0]["repository"]]
    assert len(registry) == 1


@pytest.mark.parametrize("field", ["lookup", "async_lookup", "save", "sync_register"])
async def test_changed_api_is_refused_before_any_mutation(hass, catalog, field):
    hacs, registry = hacs_stub(hass)
    register = AsyncMock()
    hacs.async_register_repository = register
    if field == "lookup":
        hacs.repositories.get_by_full_name = lambda: None
    elif field == "async_lookup":
        hacs.repositories.get_by_full_name = AsyncMock()
    elif field == "save":
        async def changed_save(required_parameter):
            raise AssertionError("Must not call an incompatible API")
        hacs.data.async_write = changed_save
    else:
        hacs.async_register_repository = Mock()
    with pytest.raises(HacsUnavailable, match="API has changed"):
        await async_register_repositories(hass, catalog)
    register.assert_not_awaited()
    assert not registry


async def test_diagnostics_explain_selection_without_exporting_credentials(hass):
    marketplace, registry = hacs_stub(hass)
    marketplace.configuration = SimpleNamespace(token="secret-token")
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=marketplace, entry_id="hub")
    with patch.object(hass.config_entries, "async_entries", return_value=[entry]):
        data = await async_get_config_entry_diagnostics(hass, entry)
    store = data["repository_store"]
    assert store["backend"] == "Marketplace"
    assert store["available"] is True
    assert "config_entry" in store["signals"]
    assert "secret-token" not in str(data)
    assert not registry
    marketplace.data.async_write.assert_not_awaited()


async def test_diagnostics_explain_version_gate_and_missing_marketplace(hass):
    with patch.object(hacs_bridge.ha_const, "__version__", "2026.11.0"):
        data = await async_store_diagnostics(hass)
    assert data["backend"] == "Marketplace"
    assert data["available"] is False
    assert "ha_version" in data["signals"]
    assert data["marketplace_from"] == "2026.11.0"
    assert "not configured" in data["reason"]


@pytest.mark.parametrize("attribute,message", [
    ("github_connected", "connect GitHub"),
    ("warning_acceptances", "first-use notice"),
])
async def test_marketplace_requires_account_and_notice(hass, catalog, attribute, message):
    manager, registry = hacs_stub(hass)
    setattr(manager, attribute, False)
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=manager)
    with patch.object(hass.config_entries, "async_entries", return_value=[entry]):
        with pytest.raises(HacsUnavailable, match=message):
            await async_register_repositories(hass, catalog)
    assert not registry
    manager.data.async_write.assert_not_awaited()


def test_actual_marketplace_signatures():
    """Core uses deferred annotations referencing TYPE_CHECKING-only names."""
    base = pytest.importorskip("homeassistant.components.marketplace.base")
    manager = SimpleNamespace(
        common=SimpleNamespace(categories={"integration"}),
        github_connected=True, warning_acceptances={"admin": "accepted"},
        async_register_repository=base.MarketplaceManager.async_register_repository.__get__(object()),
        repositories=base.Repositories(),
        data=SimpleNamespace(async_write=base.MarketplaceData.async_write.__get__(object())),
    )
    selection = hacs_bridge.StoreSelection("Marketplace", "2026.11.0", [], manager)
    assert len(hacs_bridge.registry_api(selection)) == 3

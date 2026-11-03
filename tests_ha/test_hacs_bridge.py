"""Test the internal HACS adapter contract without touching HACS storage."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.seb5594_integration_catalog.hacs_bridge import (
    HacsUnavailable,
    async_register_repositories,
)


def hacs_stub(hass):
    registry = {}

    async def register(repository_full_name, category, *, check=True):
        assert category == "integration"
        assert check is True
        registry[repository_full_name] = object()

    hacs = SimpleNamespace(
        common=SimpleNamespace(categories={"integration"}),
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

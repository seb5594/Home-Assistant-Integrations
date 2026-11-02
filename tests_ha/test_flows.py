"""Exercise hub setup, settings and the opt-in snapshot installer in real HA."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.integration_catalog.const import NAME

DOMAIN = "integration_catalog"
INSTALL = "custom_components.integration_catalog.config_flow.install_selected"


async def installer_options(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"auto_register": False, "notify_new": True},
        options={"selected": ["example"], "auto_register": False}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "install_snapshots"})
    assert result["step_id"] == "install_snapshots"
    return entry, result


async def submit_selection(hass, flow_id):
    manager = hass.config_entries.options
    result = await manager.async_configure(flow_id, {
        "integrations": ["example"], "acknowledge": True,
    })
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await manager.async_configure(flow_id)
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await manager.async_configure(flow_id)
    return result


async def test_hub_config_flow_and_single_instance(hass, catalog):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(INSTALL) as install:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "auto_register": True, "notify_new": True,
        })
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == {"auto_register": True, "notify_new": True}
        await hass.async_block_till_done()
        install.assert_not_called()
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_installer_requires_acknowledgment_and_selection(hass, catalog):
    _, result = await installer_options(hass)
    with patch(INSTALL) as install:
        result = await hass.config_entries.options.async_configure(result["flow_id"], {
            "integrations": ["example"], "acknowledge": False,
        })
        assert result["errors"] == {"acknowledge": "acknowledge_required"}
        result = await hass.config_entries.options.async_configure(result["flow_id"], {
            "integrations": [], "acknowledge": True,
        })
        assert result["errors"] == {"integrations": "select_required"}
        install.assert_not_called()


async def test_snapshot_options_preserve_hub_settings(hass, catalog):
    with patch(INSTALL, return_value={"changed": [], "selected": ["example"]}) as install:
        entry, result = await installer_options(hass)
        install.assert_not_called()
        result = await submit_selection(hass, result["flow_id"])
        assert result["step_id"] == "finish"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options == {"selected": ["example"], "auto_register": False}
        install.assert_called_once()
        await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_install_failure_offers_retry(hass, catalog):
    _, result = await installer_options(hass)
    with patch(INSTALL, side_effect=OSError("download failed")):
        result = await submit_selection(hass, result["flow_id"])
    assert result["step_id"] == "failed"
    assert "download failed" in result["description_placeholders"]["error"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["step_id"] == "install_snapshots"


async def test_hub_settings_preserve_snapshot_selection(hass, catalog):
    entry, _ = await installer_options(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "settings"})
    assert result["step_id"] == "settings"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "auto_register": True, "notify_new": False,
    })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"selected": ["example"], "auto_register": True, "notify_new": False}
    await hass.async_block_till_done()


async def test_legacy_title_migrates_without_changing_domain(hass, catalog):
    entry = MockConfigEntry(domain=DOMAIN, title="Home Assistant Integration Catalog",
        data={"selected": ["example"], "auto_register": False}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    with patch(INSTALL) as install:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.title == NAME
        assert entry.domain == DOMAIN
        assert entry.data["selected"] == ["example"]
        install.assert_not_called()


async def test_refresh_runs_on_startup_retry_hourly_and_stops_on_unload(hass, catalog, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data={"auto_register": False}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    with patch("custom_components.integration_catalog.hub.IntegrationHub.async_refresh", new_callable=AsyncMock) as refresh:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert refresh.await_count == 1
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert refresh.await_count == 2
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert refresh.await_count == 3
        assert await hass.config_entries.async_unload(entry.entry_id)
        freezer.tick(timedelta(hours=2))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert refresh.await_count == 3

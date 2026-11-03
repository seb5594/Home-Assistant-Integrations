"""Exercise hub-only setup, settings and background scheduling in real HA."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.seb5594_integration_catalog.const import NAME

DOMAIN = "seb5594_integration_catalog"


async def test_hub_config_flow_and_single_instance(hass, catalog):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        "auto_register": True, "notify_new": True,
    })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {"auto_register": True, "notify_new": True}
    await hass.async_block_till_done()
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_hub_options_only_offer_registration_and_notifications(hass, catalog):
    entry = MockConfigEntry(domain=DOMAIN, data={"auto_register": True, "notify_new": True}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert {str(key) for key in result["data_schema"].schema} == {"auto_register", "notify_new"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "auto_register": False, "notify_new": False,
    })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"auto_register": False, "notify_new": False}
    await hass.async_block_till_done()


async def test_legacy_title_migrates_without_changing_domain(hass, catalog):
    entry = MockConfigEntry(domain=DOMAIN, title="Home Assistant Integration Catalog",
        data={"auto_register": False}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.title == NAME
    assert entry.domain == DOMAIN


async def test_refresh_runs_on_startup_retry_hourly_and_stops_on_unload(hass, catalog, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data={"auto_register": False}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    with patch("custom_components.seb5594_integration_catalog.hub.IntegrationHub.async_refresh", new_callable=AsyncMock) as refresh:
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

"""Exercise hub-only setup, settings and background scheduling in real HA."""

from datetime import timedelta
from inspect import signature
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import instance_id
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.seb5594_integration_catalog.const import NAME

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # Home Assistant 2025.1 predates the helper module.
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

DOMAIN = "seb5594_integration_catalog"


async def local_advertisement(hass, uuid=None):
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.2"), ip_addresses=[ip_address("192.168.1.2")],
        hostname="homeassistant.local.", port=8123, type="_home-assistant._tcp.local.",
        name="Home._home-assistant._tcp.local.",
        properties={"uuid": uuid or await instance_id.async_get(hass)},
    )


async def test_local_discovery_suggests_setup_without_installing(hass, catalog):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=await local_advertisement(hass),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]["context"]["unique_id"] == DOMAIN
    assert hass.config_entries.async_entries(DOMAIN) == []
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=await local_advertisement(hass),
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_in_progress"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        "auto_register": False, "notify_new": True,
    })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    await hass.async_block_till_done()


async def test_discovery_does_not_suggest_other_home_assistant_instances(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF},
        data=await local_advertisement(hass, "another-instance"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_local_instance"


async def test_discovery_respects_existing_and_ignored_hubs(hass):
    for source in (config_entries.SOURCE_USER, config_entries.SOURCE_IGNORE):
        entry = MockConfigEntry(domain=DOMAIN, source=source, unique_id=DOMAIN)
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=await local_advertisement(hass),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        await hass.config_entries.async_remove(entry.entry_id)


async def test_manifest_matcher_routes_local_advertisement_to_setup(hass):
    """Exercise HA's discovery router, not just a manually initiated flow."""
    from homeassistant.components.zeroconf import ZeroconfDiscovery
    from homeassistant.loader import async_get_zeroconf
    from zeroconf.asyncio import AsyncServiceInfo

    uuid = await instance_id.async_get(hass)
    service_type = "_home-assistant._tcp.local."
    service = AsyncServiceInfo(
        service_type, f"Home.{service_type}", addresses=[ip_address("192.168.1.2").packed],
        port=8123, properties={"uuid": uuid}, server=f"{uuid}.local.",
    )
    matchers = await async_get_zeroconf(hass)
    assert any(matcher["domain"] == DOMAIN for matcher in matchers[service_type])
    await hass.async_start()
    # HA added local service conflict checks after the minimum supported version.
    kwargs = {"local_service_info": service} if "local_service_info" in signature(ZeroconfDiscovery).parameters else {}
    discovery = ZeroconfDiscovery(hass, None, {service_type: matchers[service_type]}, {}, {}, **kwargs)
    discovery._async_process_service_update(service, service_type, service.name)
    wait_kwargs = {"wait_background_tasks": True} if "wait_background_tasks" in signature(hass.async_block_till_done).parameters else {}
    await hass.async_block_till_done(**wait_kwargs)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_ZEROCONF
    assert flows[0]["step_id"] == "user"


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
    hub = hass.data[DOMAIN][entry.entry_id]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert {str(key) for key in result["data_schema"].schema} == {"auto_register", "notify_new"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "auto_register": False, "notify_new": False,
    })
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"auto_register": False, "notify_new": False}
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id] is hub
    assert not hub.enabled("auto_register")
    assert not hub.enabled("notify_new")


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

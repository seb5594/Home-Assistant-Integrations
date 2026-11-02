"""Register catalog repositories in HACS and notify about newly added projects."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import DOMAIN, NAME
from .hub import IntegrationHub

PLATFORMS = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Start metadata synchronization; never download component source at startup."""
    hub = IntegrationHub(hass, entry)
    await hub.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    if entry.title == "Home Assistant Integration Catalog":
        hass.config_entries.async_update_entry(entry, title=NAME)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def schedule_refresh(_now=None):
        entry.async_create_background_task(hass, hub.async_refresh(), f"{DOMAIN} refresh")

    entry.async_on_unload(async_track_time_interval(hass, schedule_refresh, timedelta(hours=1)))
    entry.async_on_unload(async_call_later(hass, 60, schedule_refresh))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    schedule_refresh()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Removing the installer leaves installed integrations and backups intact."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)

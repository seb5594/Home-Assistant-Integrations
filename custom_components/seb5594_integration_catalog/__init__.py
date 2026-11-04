"""Register catalog repositories in HACS and notify about newly added projects."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import DOMAIN, NAME
from .hub import IntegrationHub

PLATFORMS = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool | None:
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
    # Settings are read from the entry on every refresh, so options do not need
    # an update listener or a reload (deprecated by newer HA versions).
    schedule_refresh()
    return True if (MAJOR_VERSION, MINOR_VERSION) < (2026, 11) else None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool | None:
    """Removing the hub leaves HACS repositories and their integrations intact."""
    if (MAJOR_VERSION, MINOR_VERSION) >= (2026, 11):
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id)
        return None
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    return True

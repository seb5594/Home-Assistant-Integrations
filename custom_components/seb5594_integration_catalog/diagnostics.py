"""Explain HACS/Marketplace selection without exporting store credentials."""

from .const import DOMAIN
from .hacs_bridge import async_store_diagnostics


async def async_get_config_entry_diagnostics(hass, entry):
    hub = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    return {
        "repository_store": await async_store_diagnostics(hass),
        "catalog_entries": len(hub._catalog) if hub else 0,
    }

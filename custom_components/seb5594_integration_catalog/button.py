"""Allow a manual catalog refresh without waiting for the hourly check."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, NAME


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RefreshCatalogButton(hass.data[DOMAIN][entry.entry_id], entry)])


class RefreshCatalogButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh_catalog"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, hub, entry):
        self._hub = hub
        self._attr_unique_id = f"{entry.entry_id}_refresh_catalog"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=NAME,
            manufacturer="seb5594", model="Integration Hub",
        )

    async def async_press(self):
        await self._hub.async_refresh()

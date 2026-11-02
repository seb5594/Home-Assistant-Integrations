"""An opt-in installer; startup never modifies other integrations."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """The config/options flows perform explicit installation requests."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Removing the installer leaves installed integrations and backups intact."""
    return True

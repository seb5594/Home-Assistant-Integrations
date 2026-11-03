"""Configure repository discovery and notifications; HACS manages installations."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_AUTO_REGISTER, CONF_NOTIFY_NEW, DOMAIN, NAME


def settings_schema(settings):
    return vol.Schema({
        vol.Required(CONF_AUTO_REGISTER, default=settings.get(CONF_AUTO_REGISTER, True)): bool,
        vol.Required(CONF_NOTIFY_NEW, default=settings.get(CONF_NOTIFY_NEW, True)): bool,
    })


class CatalogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data=user_input)
        return self.async_show_form(step_id="user", data_schema=settings_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CatalogOptionsFlow()


class CatalogOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        settings = dict(self.config_entry.data) | dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=settings_schema(settings))

"""Configure repository discovery and notifications; HACS manages installations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import instance_id

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_AUTO_REGISTER, CONF_NOTIFY_NEW, DOMAIN, NAME


def settings_schema(settings):
    return vol.Schema({
        vol.Required(CONF_AUTO_REGISTER, default=settings.get(CONF_AUTO_REGISTER, True)): bool,
        vol.Required(CONF_NOTIFY_NEW, default=settings.get(CONF_NOTIFY_NEW, True)): bool,
    })


class CatalogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Use this HA instance's own mDNS advertisement as a setup suggestion.

        The manifest is scanned before an integration is configured, unlike
        async_setup. Other Home Assistant installations must not suggest a hub.
        """
        if discovery_info.properties.get("uuid") != await instance_id.async_get(self.hass):
            return self.async_abort(reason="not_local_instance")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": NAME}
        return await self.async_step_user()

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

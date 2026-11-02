"""Explicit selection and installation, shared by config and options flows."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_AUTO_REGISTER, CONF_NOTIFY_NEW, DOMAIN, NAME
from .installer import install_selected, load_catalog

_LOGGER = logging.getLogger(__name__)


def settings_schema(settings):
    return vol.Schema({
        vol.Required(CONF_AUTO_REGISTER, default=settings.get(CONF_AUTO_REGISTER, True)): bool,
        vol.Required(CONF_NOTIFY_NEW, default=settings.get(CONF_NOTIFY_NEW, True)): bool,
    })


class InstallFlow:
    """Keep network and filesystem operations off the event loop."""

    def __init__(self):
        super().__init__()
        self._catalog = None
        self._selected = []
        self._task = None
        self._result = None
        self._error = ""

    async def _async_select(self, step_id, user_input, defaults):
        if self._catalog is None:
            self._catalog = await self.hass.async_add_executor_job(load_catalog)
        errors = {}
        if user_input is not None:
            if not user_input.get("acknowledge"):
                errors["acknowledge"] = "acknowledge_required"
            elif not user_input["integrations"]:
                errors["integrations"] = "select_required"
            else:
                self._selected = user_input["integrations"]
                self._task = None
                return await self.async_step_install()
        choices = [
            {"value": item["domain"], "label": f"{item['name']} · {item['version']}"
             + (f" · HA ≥ {item['homeassistant']}" if item.get("homeassistant") else "")}
            for item in self._catalog
        ]
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({
                vol.Required("integrations", default=defaults): selector.SelectSelector({
                    "options": choices, "multiple": True, "mode": "list",
                }),
                vol.Required("acknowledge", default=False): bool,
            }),
            errors=errors,
        )

    async def _async_run_install(self):
        try:
            self._result = await self.hass.async_add_executor_job(
                install_selected, self.hass.config.config_dir, self._catalog,
                self._selected, HA_VERSION,
            )
        except Exception as err:
            _LOGGER.exception("Catalog installation failed")
            self._error = str(err)
            persistent_notification.async_create(
                self.hass, self._error, title=f"{NAME}: installation failed",
                notification_id=f"{DOMAIN}_result",
            )
        else:
            if self._result["changed"]:
                persistent_notification.async_create(
                    self.hass,
                    "Installed/updated: " + ", ".join(self._result["changed"])
                    + ". Restart Home Assistant, then configure these integrations "
                    "under Settings → Devices & services. Backups of replaced "
                    "versions are in .integration_catalog_backups/.",
                    title=f"{NAME}: restart required",
                    notification_id=f"{DOMAIN}_result",
                )

    async def async_step_install(self, user_input=None):
        if self._task is None:
            self._error = ""
            self._task = asyncio.create_task(self._async_run_install())
        if not self._task.done():
            return self.async_show_progress(
                step_id="install", progress_action="installing", progress_task=self._task,
            )
        return self.async_show_progress_done(
            next_step_id="failed" if self._error else "finish",
        )

    async def async_step_failed(self, user_input=None):
        if user_input is not None:
            return await self._async_select(self._selection_step, None, self._selected)
        return self.async_show_form(
            step_id="failed", data_schema=vol.Schema({}),
            description_placeholders={"error": self._error},
        )

    async def async_step_finish(self, user_input=None):
        if user_input is not None:
            data = dict(self.config_entry.options)
            data["selected"] = self._selected
            return self.async_create_entry(
                title="", data=data,
            )
        changed = self._result["changed"]
        return self.async_show_form(
            step_id="finish", data_schema=vol.Schema({}),
            description_placeholders={"integrations": ", ".join(changed) if changed else "—"},
        )


class CatalogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One catalog instance for the Home Assistant config directory."""

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


class CatalogOptionsFlow(InstallFlow, config_entries.OptionsFlow):
    """Reopen Configure after a HACS catalog update to apply new snapshots."""

    _selection_step = "install_snapshots"

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["settings", "install_snapshots"],
        )

    async def async_step_settings(self, user_input=None):
        settings = dict(self.config_entry.data) | dict(self.config_entry.options)
        if user_input is not None:
            return self.async_create_entry(
                title="", data=dict(self.config_entry.options) | user_input,
            )
        return self.async_show_form(step_id="settings", data_schema=settings_schema(settings))

    async def async_step_install_snapshots(self, user_input=None):
        defaults = self.config_entry.options.get(
            "selected", self.config_entry.data.get("selected", [])
        )
        return await self._async_select("install_snapshots", user_input, defaults)

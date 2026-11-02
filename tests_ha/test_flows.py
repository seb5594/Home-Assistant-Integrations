"""Exercise actual HA config/options flows and the no-startup-writes boundary."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "integration_catalog"
INSTALL = "custom_components.integration_catalog.config_flow.install_selected"


async def submit_selection(hass, manager, flow_id):
    result = await manager.async_configure(flow_id, {
        "integrations": ["example"], "acknowledge": True,
    })
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await manager.async_configure(flow_id)
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await manager.async_configure(flow_id)
    return result


async def test_config_flow_and_single_instance(hass, catalog):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch(INSTALL, return_value={"changed": ["Example Integration"], "selected": ["example"]}) as install:
        result = await submit_selection(hass, hass.config_entries.flow, result["flow_id"])
        assert result["step_id"] == "finish"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {"selected": ["example"]}
        install.assert_called_once()
        await hass.async_block_till_done()
        # Startup is a no-op; setting up the catalog must not install again.
        install.assert_called_once()
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_requires_acknowledgment_and_selection(hass, catalog):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(INSTALL) as install:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "integrations": ["example"], "acknowledge": False,
        })
        assert result["errors"] == {"acknowledge": "acknowledge_required"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {
            "integrations": [], "acknowledge": True,
        })
        assert result["errors"] == {"integrations": "select_required"}
        install.assert_not_called()


async def test_options_flow_applies_only_on_request(hass, catalog):
    entry = MockConfigEntry(domain=DOMAIN, data={"selected": ["example"]}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    with patch(INSTALL, return_value={"changed": [], "selected": ["example"]}) as install:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        install.assert_not_called()
        result = await submit_selection(hass, hass.config_entries.options, result["flow_id"])
        assert result["step_id"] == "finish"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options["selected"] == ["example"]
        install.assert_called_once()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_install_failure_offers_retry(hass, catalog):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(INSTALL, side_effect=OSError("download failed")):
        result = await submit_selection(hass, hass.config_entries.flow, result["flow_id"])
    assert result["step_id"] == "failed"
    assert "download failed" in result["description_placeholders"]["error"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "user"

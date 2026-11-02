"""Use Home Assistant's real flow manager; block actual source downloads."""

from unittest.mock import patch

import pytest

from custom_components.integration_catalog import config_flow, hub


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def block_catalog_network():
    with patch.object(hub.IntegrationHub, "_async_fetch_catalog", side_effect=ValueError("Test network disabled")):
        yield


@pytest.fixture
def catalog():
    entries = [{"name": "Example Integration", "domain": "example", "version": "1.0.0", "homeassistant": "2025.1.0", "repository": "seb5594/hass-example-integration"}]
    with patch.object(config_flow, "load_catalog", return_value=entries), patch.object(hub, "load_catalog", return_value=entries):
        yield entries

"""Use Home Assistant's real flow manager; block actual source downloads."""

from unittest.mock import patch

import pytest

from custom_components.seb5594_integration_catalog import hub


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
    entries[0].update({"release_tag": "v1.0.0",
        "release_url": "https://github.com/seb5594/hass-example-integration/releases/tag/v1.0.0",
        "package_url": "https://github.com/seb5594/hass-example-integration/releases/download/v1.0.0/example.zip"})
    with patch.object(hub, "load_catalog", return_value=entries):
        yield entries

"""Use Home Assistant's real flow manager; block actual source downloads."""

from unittest.mock import patch

import pytest

from custom_components.integration_catalog import config_flow


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def catalog():
    entries = [{"name": "Example Integration", "domain": "example", "version": "1.0.0", "homeassistant": "2025.1.0"}]
    with patch.object(config_flow, "load_catalog", return_value=entries):
        yield entries

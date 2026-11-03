"""New-repository detection, persisted deduplication and metadata validation."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.seb5594_integration_catalog.hacs_bridge import RegistrationResult
from custom_components.seb5594_integration_catalog.hub import (
    MAX_FEED_SIZE,
    IntegrationHub,
    validate_feed,
)

FETCH_CATALOG = IntegrationHub._async_fetch_catalog


def addition():
    return {"repository": "seb5594/hass-next-integration", "domain": "next_integration",
            "name": "The Next Integration", "version": "1.0.0", "release_tag": "v1.0.0",
            "release_url": "https://github.com/seb5594/hass-next-integration/releases/tag/v1.0.0",
            "package_url": "https://github.com/seb5594/hass-next-integration/releases/download/v1.0.0/next_integration.zip"}


async def make_hub(hass):
    entry = MockConfigEntry(domain="seb5594_integration_catalog", data={"auto_register": False, "notify_new": True})
    entry.add_to_hass(hass)
    hub = IntegrationHub(hass, entry)
    await hub.async_initialize()
    return hub, entry


async def test_notifies_only_new_repositories_and_remembers_across_restart(hass, catalog):
    hub, entry = await make_hub(hass)
    with patch.object(hub, "_async_fetch_catalog", return_value=catalog), patch(
        "custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create"
    ) as notify:
        await hub.async_refresh()
        notify.assert_not_called()  # Initial catalog is the baseline.
    newer = catalog + [addition()]
    with patch.object(hub, "_async_fetch_catalog", return_value=newer), patch(
        "custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create"
    ) as notify:
        await hub.async_refresh()
        notify.assert_called_once()
        message = notify.call_args.args[1]
        assert "The Next Integration" in message
        assert addition()["release_url"] in message
        assert addition()["package_url"] in message
        assert "hacs_repository/?owner=seb5594" in message
        assert "No integrations were automatically downloaded" in message
        await hub.async_refresh()
        notify.assert_called_once()
    restored = IntegrationHub(hass, entry)
    await restored.async_initialize()
    with patch.object(restored, "_async_fetch_catalog", return_value=newer), patch(
        "custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create"
    ) as notify:
        await restored.async_refresh()
        notify.assert_not_called()


async def test_version_changes_are_left_to_hacs_not_announced_as_new(hass, catalog):
    hub, _ = await make_hub(hass)
    with patch.object(hub, "_async_fetch_catalog", return_value=catalog):
        await hub.async_refresh()
    updated = deepcopy(catalog)
    updated[0].update({
        "version": "2.0.0", "release_tag": "v2.0.0",
        "release_url": catalog[0]["release_url"].replace("v1.0.0", "v2.0.0"),
        "package_url": catalog[0]["package_url"].replace("v1.0.0", "v2.0.0"),
    })
    with patch.object(hub, "_async_fetch_catalog", return_value=updated), patch(
        "custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create"
    ) as notify:
        await hub.async_refresh()
        assert hub._catalog[0]["version"] == "2.0.0"
        notify.assert_not_called()


async def test_network_failure_keeps_catalog_and_seen_state(hass, catalog):
    hub, _ = await make_hub(hass)
    with patch.object(hub, "_async_fetch_catalog", return_value=catalog):
        await hub.async_refresh()
    before = deepcopy(hub._catalog)
    with patch.object(hub, "_async_fetch_catalog", side_effect=ValueError("invalid feed")), patch(
        "custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create"
    ) as notify:
        await hub.async_refresh()
        assert hub._catalog == before
        assert hub._seen == {catalog[0]["repository"]}
        notify.assert_not_called()


async def test_automatic_registration_and_notification_can_be_disabled(hass, catalog):
    hub, entry = await make_hub(hass)
    hass.config_entries.async_update_entry(entry, options={"auto_register": False, "notify_new": False})
    with patch.object(hub, "_async_fetch_catalog", return_value=catalog), patch(
        "custom_components.seb5594_integration_catalog.hub.async_register_repositories"
    ) as register, patch("custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create") as notify:
        await hub.async_refresh()
        hub._catalog = catalog + [addition()]
        with patch.object(hub, "_async_fetch_catalog", return_value=hub._catalog):
            await hub.async_refresh()
        register.assert_not_called()
        notify.assert_not_called()
        assert addition()["repository"] in hub._seen


@pytest.mark.parametrize("backend", ["HACS", "Marketplace"])
async def test_announces_successful_hacs_registration_in_german(hass, catalog, backend):
    hub, entry = await make_hub(hass)
    hass.config_entries.async_update_entry(entry, options={"auto_register": True})
    hass.config.language = "de"
    hub._seen = {catalog[0]["repository"]}
    with patch.object(hub, "_async_fetch_catalog", return_value=catalog + [addition()]), patch(
        "custom_components.seb5594_integration_catalog.hub.async_register_repositories",
        new=AsyncMock(return_value=RegistrationResult(added=[addition()["repository"]], backend=backend)),
    ) as register, patch("custom_components.seb5594_integration_catalog.hub.persistent_notification.async_create") as notify:
        await hub.async_refresh()
        register.assert_awaited_once()
        assert f"bereits in {backend} hinzugefügt" in notify.call_args.args[1]
        assert "Neu im Integrationskatalog" in notify.call_args.args[1]


@pytest.mark.parametrize("change", [
    {"repository": "somebody/hass-unsafe-integration"}, {"repository": "seb5594/unrelated"},
    {"domain": "../outside"}, {"name": ""}, {"version": None},
    {"release_tag": "v9.9.9"},
    {"release_url": "https://github.com/seb5594/hass-example-integration/tree/main"},
    {"package_url": "https://github.com/seb5594/hass-example-integration/archive/refs/heads/main.zip"},
])
def test_feed_rejects_unapproved_or_malformed_entries(catalog, change):
    bad = dict(catalog[0]) | change
    with pytest.raises(ValueError):
        validate_feed({"schema_version": 2, "integrations": [bad]})


def test_feed_rejects_partial_and_duplicate_payloads(catalog):
    for payload in [None, {}, {"schema_version": 3, "integrations": catalog},
                    {"schema_version": 2, "integrations": []},
                    {"schema_version": 2, "integrations": catalog + catalog}]:
        with pytest.raises(ValueError):
            validate_feed(payload)


async def test_old_branch_cache_is_replaced_by_bundled_release_metadata(hass, catalog):
    hub, _ = await make_hub(hass)
    legacy = {key: value for key, value in catalog[0].items()
              if key not in {"release_tag", "release_url", "package_url"}}
    with patch.object(hub.store, "async_load", return_value={
        "seen": [catalog[0]["repository"]], "catalog": [legacy],
    }):
        await hub.async_initialize()
    assert hub._catalog[0]["release_tag"] == "v1.0.0"
    assert hub._seen == {catalog[0]["repository"]}


class FeedResponse:
    def __init__(self, data, status=200):
        self.status = status
        self.content = SimpleNamespace(iter_chunked=lambda _: self.chunks(data))

    async def chunks(self, data):
        for offset in range(0, len(data), 16384):
            yield data[offset:offset + 16384]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


async def test_fetch_uses_public_bounded_feed_without_redirects(hass, catalog):
    hub, _ = await make_hub(hass)
    response = FeedResponse(json.dumps({"schema_version": 2, "integrations": catalog}).encode())
    session = SimpleNamespace(get=Mock(return_value=response))
    with patch("custom_components.seb5594_integration_catalog.hub.async_get_clientsession", return_value=session):
        result = await FETCH_CATALOG(hub)
    assert result == validate_feed({"schema_version": 2, "integrations": catalog})
    assert session.get.call_args.kwargs["allow_redirects"] is False
    assert session.get.call_args.args[0].endswith("/main/catalog-feed.json")


@pytest.mark.parametrize("data,status", [(b"", 302), (b"", 429), (b"bad-json", 200), (b"x" * (MAX_FEED_SIZE + 1), 200)])
async def test_fetch_rejects_redirects_http_errors_invalid_json_and_large_bodies(hass, catalog, data, status):
    hub, _ = await make_hub(hass)
    session = SimpleNamespace(get=Mock(return_value=FeedResponse(data, status)))
    with patch("custom_components.seb5594_integration_catalog.hub.async_get_clientsession", return_value=session), pytest.raises(ValueError):
        await FETCH_CATALOG(hub)

"""Poll the public catalog, register repositories in HACS and announce additions."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

import aiohttp
from homeassistant.components import persistent_notification
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import CONF_AUTO_REGISTER, CONF_NOTIFY_NEW, DOMAIN, FEED_URL, NAME
from .hacs_bridge import HacsUnavailable, async_register_repositories

_LOGGER = logging.getLogger(__name__)
MAX_FEED_SIZE = 256 * 1024
REPOSITORY_PATTERN = re.compile(
    r"seb5594/(?:hass-[A-Za-z0-9_.-]+-integration|Home-Assistant-[A-Za-z0-9_.-]+-Integration)"
)


def load_catalog() -> list[dict]:
    return json.loads(Path(__file__).with_name("catalog.json").read_text("utf-8"))


def validate_feed(payload: dict) -> list[dict]:
    """Accept only bounded metadata for this author's integration repositories."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise ValueError("Unsupported catalog feed schema")
    entries = payload.get("integrations")
    if not isinstance(entries, list) or not entries or len(entries) > 200:
        raise ValueError("Invalid catalog feed integration list")
    result, repositories, domains = [], set(), set()
    for item in entries:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(key), str) or not item[key] or len(item[key]) > 250
            for key in ("repository", "domain", "name", "version", "release_tag", "release_url", "package_url")
        ):
            raise ValueError("Incomplete catalog feed entry")
        if not REPOSITORY_PATTERN.fullmatch(item["repository"]):
            raise ValueError("Catalog entry is not an allowed seb5594 integration repository")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", item["domain"]):
            raise ValueError("Invalid catalog domain")
        tag, repository = item["release_tag"], item["repository"]
        if tag.removeprefix("v") != item["version"]:
            raise ValueError("Release tag does not match the packaged version")
        if item["release_url"] != f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}":
            raise ValueError("Invalid release URL")
        package = urlsplit(item["package_url"])
        expected_prefix = f"/{repository}/releases/download/{quote(tag, safe='')}/"
        if (package.scheme != "https" or package.netloc != "github.com" or package.query or package.fragment
            or not package.path.startswith(expected_prefix)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", package.path[len(expected_prefix):])):
            raise ValueError("Invalid release package URL")
        if item["repository"] in repositories or item["domain"] in domains:
            raise ValueError("Duplicate catalog repository or domain")
        repositories.add(item["repository"])
        domains.add(item["domain"])
        result.append({key: item[key] for key in (
            "repository", "domain", "name", "version", "release_tag", "release_url", "package_url",
        )})
    return sorted(result, key=lambda item: item["repository"])


def hacs_link(repository: str) -> str:
    owner, name = repository.split("/")
    return "https://my.home-assistant.io/redirect/hacs_repository/?" + urlencode({
        "owner": owner, "repository": name, "category": "integration",
    })


def markdown_label(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", value).replace("\n", " ").replace("\r", " ")


class IntegrationHub:
    """Persist seen repositories so unchanged catalogs never repeat notifications."""

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._catalog = []
        self._seen = None
        self._last_saved = None
        self._bridge_error = None
        self._lock = asyncio.Lock()

    def enabled(self, key: str) -> bool:
        return self.entry.options.get(key, self.entry.data.get(key, True))

    async def async_initialize(self):
        bundled = await self.hass.async_add_executor_job(load_catalog)
        self._catalog = validate_feed({"schema_version": 2, "integrations": bundled})
        saved = await self.store.async_load()
        if saved:
            self._seen = set(saved.get("seen", []))
            if saved.get("catalog"):
                try:
                    self._catalog = validate_feed({"schema_version": 2, "integrations": saved["catalog"]})
                except ValueError:
                    _LOGGER.info("Replacing the pre-release-policy cache with the bundled release catalog")
            self._last_saved = saved

    async def _async_fetch_catalog(self) -> list[dict]:
        session = async_get_clientsession(self.hass)
        async with session.get(
            FEED_URL, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise ValueError(f"Catalog HTTP status {response.status}")
            data = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                data.extend(chunk)
                if len(data) > MAX_FEED_SIZE:
                    raise ValueError("Catalog feed exceeds size limit")
            return validate_feed(json.loads(data))

    async def async_refresh(self, _now=None):
        """A failed fetch keeps the last known catalog and never implies removals."""
        async with self._lock:
            try:
                self._catalog = await self._async_fetch_catalog()
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.warning("Cannot refresh %s; retaining the cached catalog: %s", NAME, err)
            present = {item["repository"] for item in self._catalog}
            # First use establishes a baseline, rather than announcing the whole catalog.
            new_items = [item for item in self._catalog if self._seen is not None and item["repository"] not in self._seen]
            registration = None
            if self.enabled(CONF_AUTO_REGISTER):
                try:
                    registration = await async_register_repositories(self.hass, self._catalog)
                    error = "\n".join(f"{repo}: {reason}" for repo, reason in registration.failed.items())
                except HacsUnavailable as err:
                    error = str(err)
                except Exception as err:
                    _LOGGER.exception("Repository store synchronization failed")
                    error = str(err)
                if error != self._bridge_error:
                    if error:
                        _LOGGER.warning("Repository store synchronization: %s", error)
                        if error not in {"HACS is still starting", "Marketplace is still starting"}:
                            persistent_notification.async_create(
                                self.hass,
                                "Repositories could not be added to HACS / Marketplace automatically: " + error
                                + ". Open Settings > Marketplace on Home Assistant 2026.11 or newer, "
                                "or HACS on older versions. The hub will retry automatically.",
                                title=f"{NAME}: HACS / Marketplace", notification_id=f"{DOMAIN}_hacs",
                            )
                    else:
                        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_hacs")
                    self._bridge_error = error
            if new_items and self.enabled(CONF_NOTIFY_NEW):
                self._notify_new(new_items, registration)
            self._seen = (self._seen or set()) | present
            saved = {"seen": sorted(self._seen), "catalog": self._catalog}
            if saved != self._last_saved:
                await self.store.async_save(saved)
                self._last_saved = saved

    def _notify_new(self, items: list[dict], registration):
        german = self.hass.config.language == "de"
        backend = registration.backend if registration else "HACS / Marketplace"
        lines = []
        for item in items:
            registered = registration and item["repository"] in (registration.added + registration.existing)
            status = (f"bereits in {backend} hinzugefügt" if german else f"already added to {backend}") if registered else ""
            label = markdown_label(item["name"])
            link_label = f"In {backend} öffnen" if german else f"Open in {backend}"
            lines.append(f"- **{label}** · [{markdown_label(item['release_tag'])}]({item['release_url']})"
                         f" · [ZIP]({item['package_url']}) · [{link_label}]({hacs_link(item['repository'])})"
                         + (f" — {status}" if status else ""))
        intro = "Neu im Integrationskatalog:" if german else "New in the integration catalog:"
        footer = (f"Die Integrationen wurden nicht automatisch heruntergeladen. Öffne {backend}, um sie zu installieren."
                  if german else f"No integrations were automatically downloaded. Open {backend} to install them.")
        persistent_notification.async_create(
            self.hass, intro + "\n\n" + "\n".join(lines) + "\n\n" + footer,
            title=NAME, notification_id=f"{DOMAIN}_new_integrations",
        )

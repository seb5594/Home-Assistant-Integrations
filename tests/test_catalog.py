"""Validate the checked-in public catalog and its presentation."""

import json
import re
import unittest
from pathlib import Path

from scripts.sync_catalog import render_readme

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.items = json.loads((ROOT / "custom_components/seb5594_integration_catalog/catalog.json").read_text("utf-8"))

    def test_readme_is_reproducible_and_uses_friendly_names(self):
        rendered = render_readme(self.items)
        self.assertEqual(rendered, (ROOT / "README.md").read_text("utf-8"))
        for item in self.items:
            self.assertIn(f'height="48" alt=""> {item["name"]}', rendered)
            self.assertNotIn(f"### [{item['domain']}]", rendered)
            self.assertTrue((ROOT / item["logo"]).is_file())

    def test_lock_and_gitmodules_agree(self):
        legacy = json.loads((ROOT / ".github/catalog.json").read_text("utf-8"))
        self.assertEqual(legacy, [{"repository": x["repository"], "commit": x["commit"]} for x in self.items])
        modules = (ROOT / ".gitmodules").read_text("utf-8")
        self.assertEqual(modules.count("[submodule "), len(self.items))
        for item in self.items:
            self.assertIn(f"path = integrations/{item['domain']}", modules)
            self.assertIn(f"url = https://github.com/{item['repository']}.git", modules)
            self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(item["name"])
            self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", item["package"]["sha256"]))

    def test_hacs_layout_is_one_integration(self):
        manifests = list((ROOT / "custom_components").glob("*/manifest.json"))
        self.assertEqual([path.parent.name for path in manifests], ["seb5594_integration_catalog"])
        manifest = json.loads(manifests[0].read_text("utf-8"))
        self.assertEqual(manifest["domain"], "seb5594_integration_catalog")
        hacs = json.loads((ROOT / "hacs.json").read_text("utf-8"))
        self.assertEqual(hacs["filename"], manifest["domain"] + ".zip")
        self.assertTrue(manifest["config_flow"])
        self.assertTrue((manifests[0].parent / "brand/icon.png").exists())

    def test_public_discovery_feed_matches_pinned_metadata(self):
        feed = json.loads((ROOT / "catalog-feed.json").read_text("utf-8"))
        self.assertEqual(feed["schema_version"], 2)
        self.assertEqual(feed["integrations"], [
            {key: item[key] for key in ("repository", "domain", "name", "version", "release_tag", "release_url", "package_url")}
            for item in self.items
        ])
        for item in self.items:
            self.assertEqual(item["release_tag"].removeprefix("v"), item["version"])
            self.assertIn(f"/releases/download/{item['release_tag']}/", item["package_url"])
            self.assertRegex(item["package"]["sha256"], r"^[a-f0-9]{64}$")

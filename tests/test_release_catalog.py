"""Published release/package selection, with no default-branch fallback."""

import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile

from scripts import sync_catalog
from scripts.build_release import build_release


def zip_bytes(files):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()


class ReleaseSelectionTests(unittest.TestCase):
    def setUp(self):
        self.repo = {"full_name": "seb5594/hass-example-integration", "default_branch": "main"}
        self.tag = "v1.2.3"
        self.commit = "b" * 40
        self.url = "https://github.com/seb5594/hass-example-integration/releases/download/v1.2.3/example.zip"
        self.package = zip_bytes({"manifest.json": json.dumps({
            "domain": "example", "name": "Released Friendly Name", "version": "1.2.3",
        }), "__init__.py": "# published code"})
        self.release = {"tag_name": self.tag, "draft": False, "prerelease": False,
            "published_at": "2026-11-03T00:00:00Z", "target_commitish": "main", "assets": []}
        self.set_asset()
        self.source = zip_bytes({
            "repo-tag/custom_components/example/manifest.json": json.dumps({
                "domain": "example", "name": "Source name", "version": "0.0.0",
            }), "repo-tag/hacs.json": '{"filename":"example.zip","homeassistant":"2025.1.0"}',
        })

    def set_asset(self):
        self.release["assets"] = [{"name": "example.zip", "state": "uploaded",
            "browser_download_url": self.url,
            "digest": "sha256:" + hashlib.sha256(self.package).hexdigest()}]

    def api(self, path):
        if path.endswith("/releases/latest"):
            return self.release
        if path.endswith("/commits/v1.2.3"):
            return {"sha": self.commit}
        self.fail(f"Unexpected API request (a branch fallback is forbidden): {path}")

    def fetch(self, url):
        if url == self.url:
            return self.package
        if url == f"https://codeload.github.com/{self.repo['full_name']}/zip/{self.commit}":
            return self.source
        self.fail(f"Unexpected download URL: {url}")

    def inspect(self):
        with patch.object(sync_catalog, "api", side_effect=self.api), patch.object(sync_catalog, "fetch", side_effect=self.fetch):
            return sync_catalog.inspect_repository(self.repo)

    def test_metadata_comes_from_uploaded_package_and_tag_commit(self):
        item = self.inspect()
        self.assertEqual(item["name"], "Released Friendly Name")
        self.assertEqual(item["version"], "1.2.3")
        self.assertEqual(item["release_tag"], "v1.2.3")
        self.assertEqual(item["commit"], self.commit)
        self.assertEqual(item["package_url"], self.url)
        self.assertNotIn("files", item)  # No installer payload is distributed.

    def test_missing_stable_release_is_skipped_without_fallback(self):
        with patch.object(sync_catalog, "api", side_effect=HTTPError("latest", 404, "Not found", None, None)), patch.object(sync_catalog, "fetch") as fetch:
            self.assertIsNone(sync_catalog.inspect_repository(self.repo))
            fetch.assert_not_called()

    def test_access_and_network_errors_do_not_prune_the_catalog(self):
        with patch.object(sync_catalog, "api", side_effect=HTTPError("latest", 403, "Rate limited", None, None)):
            with self.assertRaises(HTTPError):
                sync_catalog.inspect_repository(self.repo)

    def test_drafts_and_prereleases_are_not_offered(self):
        for flag in ("draft", "prerelease"):
            self.release[flag] = True
            self.assertIsNone(self.inspect())
            self.release[flag] = False

    def test_missing_latest_package_does_not_select_an_older_release(self):
        self.release["assets"] = []
        self.assertIsNone(self.inspect())

    def test_tag_must_match_packaged_version(self):
        self.package = zip_bytes({"manifest.json": json.dumps({
            "domain": "example", "name": "Example", "version": "1.2.4",
        }), "__init__.py": ""})
        self.set_asset()
        with self.assertRaisesRegex(ValueError, "release tag and packaged manifest disagree"):
            self.inspect()

    def test_package_digest_must_match_the_release_asset(self):
        self.release["assets"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.inspect()

    def test_package_rejects_archive_traversal(self):
        with self.assertRaisesRegex(ValueError, "Unsafe release package path"):
            sync_catalog.read_package(zip_bytes({"../outside": "no"}))

    def test_no_arbitrary_asset_url_is_used(self):
        self.release["assets"][0]["browser_download_url"] = "https://example.com/not-a-release.zip"
        with self.assertRaisesRegex(ValueError, "unexpected release package URL"):
            self.inspect()


class HubPackageTests(unittest.TestCase):
    def test_catalog_sync_preserves_hub_version_even_when_projects_change(self):
        """New projects/releases update the feed without advertising a hub update."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component = root / "custom_components/seb5594_integration_catalog"
            component.mkdir(parents=True)
            (root / "assets/brands").mkdir(parents=True)
            manifest = component / "manifest.json"
            original = '{"domain":"seb5594_integration_catalog","version":"2026.11.3.5"}\n'
            manifest.write_text(original, "utf-8")
            (component / "catalog.json").write_text("[]", "utf-8")
            item = {"repository": "seb5594/hass-new-integration", "domain": "new",
                "name": "New Project", "version": "2.0.0", "release_tag": "v2.0.0",
                "release_url": "https://github.com/example/releases/tag/v2.0.0",
                "package_url": "https://github.com/example/releases/download/v2.0.0/new.zip",
                "commit": "a" * 40, "logo": "new.png", "logo_source": "Package"}
            with patch.object(sync_catalog, "ROOT", root), patch.object(sync_catalog, "COMPONENT", component), \
                patch("sys.argv", ["sync_catalog.py"]), \
                patch.object(sync_catalog, "api", return_value=[{"name": "hass-new-integration", "full_name": item["repository"]}]), \
                patch.object(sync_catalog, "inspect_repository", return_value=item), \
                patch.object(sync_catalog, "sync_submodules"), \
                patch.object(sync_catalog, "render_readme", return_value="Updated catalog"):
                for version in ("2.0.0", "2.0.1"):
                    item.update(version=version, release_tag=f"v{version}")
                    sync_catalog.main()
                    self.assertEqual(manifest.read_text("utf-8"), original)
                    feed = json.loads((root / "catalog-feed.json").read_text("utf-8"))
                    self.assertEqual(feed["integrations"][0]["version"], version)

    def test_hacs_package_is_flat_and_contains_no_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            package = build_release(Path(directory))
            with ZipFile(package) as archive:
                names = archive.namelist()
                self.assertIn("manifest.json", names)
                self.assertIn("hub.py", names)
                self.assertNotIn("installer.py", names)
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.startswith("custom_components/") for name in names))
            checksum = hashlib.sha256(package.read_bytes()).hexdigest()
            self.assertEqual((Path(directory) / "SHA256SUMS.txt").read_text().split()[0], checksum)

"""Filesystem, ownership, verification and recovery tests without Home Assistant."""

import importlib.util
import json
import stat
import tempfile
import unittest
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "catalog_installer", ROOT / "custom_components/integration_catalog/installer.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def snapshot(domain="example", version="1.0.0", extra=None):
    files = {
        f"custom_components/{domain}/manifest.json": json.dumps({
            "domain": domain, "name": domain.title(), "version": version,
        }).encode(),
        f"custom_components/{domain}/__init__.py": b"# never imported\n",
        "LICENSE": b"Source project license\n",
    }
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for path, data in {**files, **(extra or {})}.items():
            archive.writestr(f"repository-commit/{path}", data)
    item = {
        "repository": f"seb5594/hass-{domain}-integration", "commit": version[0] * 40,
        "name": domain.title(), "domain": domain, "version": version,
        "homeassistant": "2025.1.0", "files": {},
    }
    for path, data in files.items():
        name = f".source-license/{path}" if path == "LICENSE" else path.split("/", 2)[2]
        item["files"][name] = {"path": path, "sha256": installer.digest(data)}
    return item, output.getvalue()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name)
        self.item, self.data = snapshot()

    def install(self, item=None, data=None, **kwargs):
        item = item or self.item
        return installer.install_selected(
            str(self.config), [item], [item["domain"]], "2026.10.4",
            download=kwargs.get("download", lambda _: data or self.data),
        )

    def test_first_install_license_marker_and_idempotence(self):
        self.assertEqual(self.install()["changed"], ["Example"])
        target = self.config / "custom_components/example"
        self.assertEqual((target / ".source-license/LICENSE").read_bytes(), b"Source project license\n")
        self.assertTrue((target / installer.MARKER).is_file())
        def no_download(_):
            self.fail("An unchanged snapshot must not be downloaded")
        self.assertEqual(self.install(download=no_download)["changed"], [])

    def test_update_retains_complete_old_directory(self):
        self.install()
        item, data = snapshot(version="2.0.0")
        self.install(item, data)
        backups = list((self.config / ".integration_catalog_backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads((backups[0] / "manifest.json").read_text())["version"], "1.0.0")
        self.assertEqual(json.loads((backups[0] / installer.MARKER).read_text())["commit"], "1" * 40)

    def test_refuses_unmanaged_install_before_any_download(self):
        target = self.config / "custom_components/example"
        target.mkdir(parents=True)
        (target / "__init__.py").write_text("manual")
        with self.assertRaisesRegex(installer.InstallError, "outside this catalog"):
            self.install(download=lambda _: self.fail("Must preflight first"))
        self.assertEqual((target / "__init__.py").read_text(), "manual")

    def test_refuses_modified_and_added_files(self):
        self.install()
        target = self.config / "custom_components/example"
        (target / "local.txt").write_text("keep me")
        with self.assertRaisesRegex(installer.InstallError, "local files changed"):
            self.install()

    def test_ignores_interpreter_cache(self):
        self.install()
        cache = self.config / "custom_components/example/__pycache__"
        cache.mkdir()
        (cache / "__init__.cpython-313.pyc").write_bytes(b"cache")
        self.assertEqual(self.install()["changed"], [])

    def test_checksum_failure_does_not_install(self):
        self.item["files"]["__init__.py"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(installer.InstallError, "checksum"):
            self.install()
        self.assertFalse((self.config / "custom_components/example").exists())
        self.assertFalse((self.config / ".integration-catalog.lock").exists())

    def test_all_downloads_verified_before_first_write(self):
        second, archive = snapshot("second")
        second["files"]["__init__.py"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(installer.InstallError, "checksum"):
            installer.install_selected(str(self.config), [self.item, second],
                ["example", "second"], "2026.10.4",
                download=lambda item: self.data if item["domain"] == "example" else archive)
        self.assertFalse((self.config / "custom_components/example").exists())

    def test_archive_traversal_is_rejected(self):
        item, data = snapshot(extra={"../../escaped": b"bad"})
        with self.assertRaisesRegex(installer.InstallError, "Unsafe path"):
            self.install(item, data)
        self.assertFalse((self.config / "escaped").exists())

    def test_catalog_traversal_and_windows_paths_are_rejected(self):
        for path in ["../outside", "/absolute", "C:/absolute", "a\\b", "a/./b", "a//b"]:
            with self.subTest(path=path), self.assertRaises(installer.InstallError):
                installer.safe_relative(path)

    def test_archive_symlink_is_rejected(self):
        output = BytesIO(self.data)
        with ZipFile(output, "a") as archive:
            info = ZipInfo("repository-commit/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "/etc/passwd")
        with self.assertRaisesRegex(installer.InstallError, "symbolic link"):
            self.install(data=output.getvalue())

    def test_manifest_domain_must_match_catalog(self):
        item = deepcopy(self.item)
        item["domain"] = "different"
        with self.assertRaisesRegex(installer.InstallError, "Manifest does not match"):
            self.install(item)

    def test_homeassistant_minimum_checked_before_download(self):
        self.item["homeassistant"] = "2099.1.0"
        with self.assertRaisesRegex(installer.InstallError, "requires Home Assistant"):
            self.install(download=lambda _: self.fail("Must check compatibility first"))
        self.assertFalse(installer.compatible("2026.11.0b1", "2026.11.0"))
        self.assertTrue(installer.compatible("2026.11.0b1", "2026.10.4"))

    def test_replacement_failure_restores_original(self):
        self.install()
        item, data = snapshot(version="2.0.0")
        original = Path.rename
        def fail_stage(path, target):
            if path.name == "example" and path.parent.name.startswith(".integration-catalog-"):
                raise OSError("simulated filesystem failure")
            return original(path, target)
        with patch.object(Path, "rename", fail_stage):
            with self.assertRaisesRegex(installer.InstallError, "simulated filesystem failure"):
                self.install(item, data)
        target = self.config / "custom_components/example"
        self.assertEqual(json.loads((target / "manifest.json").read_text())["version"], "1.0.0")

    def test_detects_changes_while_download_runs(self):
        self.install()
        item, data = snapshot(version="2.0.0")
        def download(_):
            (self.config / "custom_components/example/local.txt").write_text("new local file")
            return data
        with self.assertRaisesRegex(installer.InstallError, "local files changed"):
            self.install(item, download=download)

    def test_lock_blocks_concurrent_installation(self):
        with installer.install_lock(self.config):
            with self.assertRaisesRegex(installer.InstallError, "Installer busy"):
                self.install()

    def test_invalid_selection_and_reserved_domains(self):
        for selection in [[], ["unknown"], ["example", "example"]]:
            with self.subTest(selection=selection), self.assertRaises(installer.InstallError):
                installer.install_selected(str(self.config), [self.item], selection, "2026.10.4")
        item, data = snapshot("hacs")
        with self.assertRaisesRegex(installer.InstallError, "Invalid integration domain"):
            self.install(item, data)

    def test_catalog_cannot_switch_source_ownership(self):
        self.install()
        item = deepcopy(self.item)
        item["repository"] = "seb5594/hass-other-integration"
        with self.assertRaisesRegex(installer.InstallError, "different repository"):
            self.install(item)


if __name__ == "__main__":
    unittest.main()

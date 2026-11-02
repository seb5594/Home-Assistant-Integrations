"""Install verified, pinned component snapshots without importing their code.

This module uses only the standard library, so filesystem behavior can be tested
without starting Home Assistant. Call it in an executor, never on the event loop.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from zipfile import ZipFile

MARKER = ".integration-catalog.json"
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
RESERVED_DOMAINS = {"hacs", "homeassistant", "integration_catalog"}


class InstallError(Exception):
    """A download, ownership or validation check failed."""


def load_catalog() -> list[dict]:
    """Read the catalog shipped with this HACS version."""
    return json.loads(Path(__file__).with_name("catalog.json").read_text("utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(value: str) -> Path:
    """Reject archive traversal and Windows path syntax as well as POSIX paths."""
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(
        part in {"", ".", ".."} or "\\" in part or ":" in part
        for part in value.split("/")
    ):
        raise InstallError(f"Unsafe path: {value}")
    return Path(*path.parts)


def tree_hashes(folder: Path) -> dict[str, str]:
    """Ignore interpreter caches, but reject symlinks and modified source files."""
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise InstallError(f"Symbolic link found: {path}")
        relative = path.relative_to(folder)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_file() and relative.as_posix() != MARKER:
            result[relative.as_posix()] = digest(path.read_bytes())
    return result


def check_owned(target: Path, item: dict) -> dict | None:
    """Never take ownership of a manual or separately HACS-managed install."""
    if target.is_symlink():
        raise InstallError(f"{item['name']}: target is a symbolic link")
    if not target.exists():
        return None
    marker = target / MARKER
    if not target.is_dir() or not marker.is_file() or marker.is_symlink():
        raise InstallError(f"{item['name']}: already installed outside this catalog")
    try:
        previous = json.loads(marker.read_text("utf-8"))
    except (ValueError, OSError) as err:
        raise InstallError(f"{item['name']}: invalid ownership marker") from err
    if previous.get("repository") != item["repository"]:
        raise InstallError(f"{item['name']}: belongs to a different repository")
    if previous.get("hashes") != tree_hashes(target):
        raise InstallError(f"{item['name']}: local files changed; refusing to overwrite")
    return previous


def download_archive(item: dict) -> bytes:
    """Public immutable GitHub archive; no token or HACS internals required."""
    repository, commit = item["repository"], item["commit"]
    if not re.fullmatch(r"seb5594/[A-Za-z0-9_.-]+", repository) or not re.fullmatch(
        r"[0-9a-f]{40}", commit
    ):
        raise InstallError("Invalid source repository or commit")
    url = f"https://codeload.github.com/{repository}/zip/{commit}"
    request = Request(url, headers={"User-Agent": "Home-Assistant-Integration-Catalog"})
    with urlopen(request, timeout=60) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise InstallError("Archive exceeds download limit")
    return data


def extract_verified(data: bytes, item: dict, destination: Path) -> dict[str, str]:
    """Extract only allowlisted files, validating every file's SHA-256 first."""
    if len(data) > MAX_ARCHIVE:
        raise InstallError("Archive exceeds download limit")
    with ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise InstallError("Archive exceeds expanded size limit")
        if len({info.filename for info in infos}) != len(infos):
            raise InstallError("Duplicate archive entries")
        roots = {info.filename.split("/")[0] for info in infos}
        if len(roots) != 1:
            raise InstallError("Archive has no unique root")
        root = roots.pop()
        for info in infos:
            safe_relative(info.filename.rstrip("/"))
            if stat.S_ISLNK(info.external_attr >> 16):
                raise InstallError("Archive contains a symbolic link")
        expected = item["files"]
        if "manifest.json" not in expected or "__init__.py" not in expected:
            raise InstallError("Incomplete component snapshot")
        hashes = {}
        for name, source in expected.items():
            if name == MARKER:
                raise InstallError("Snapshot contains reserved ownership marker")
            relative = safe_relative(name)
            safe_relative(source["path"])
            data = archive.read(f"{root}/{source['path']}")
            if digest(data) != source["sha256"]:
                raise InstallError(f"{item['name']}: checksum mismatch for {name}")
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            hashes[name] = source["sha256"]
    manifest = json.loads((destination / "manifest.json").read_text("utf-8"))
    if manifest.get("domain") != item["domain"] or manifest.get("version") != item["version"]:
        raise InstallError("Manifest does not match catalog")
    (destination / MARKER).write_text(
        json.dumps({"repository": item["repository"], "commit": item["commit"],
                    "version": item["version"], "hashes": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    return hashes


def compatible(installed: str, minimum: str) -> bool:
    """Compare HA stable releases, treating a prerelease as below that stable."""
    def key(value):
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(.*)", value)
        if not match:
            raise InstallError(f"Cannot compare Home Assistant version: {value}")
        return tuple(map(int, match.groups()[:3])) + (not bool(match[4]),)
    return not minimum or key(installed) >= key(minimum)


@contextmanager
def install_lock(config: Path):
    """Serialize installers, including cancelled flows whose executor still runs."""
    lock = config / ".integration-catalog.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as err:
        raise InstallError("Installer busy, or stale .integration-catalog.lock after a crash") from err
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def install_selected(config_dir: str, catalog: list[dict], selected: list[str],
                     ha_version: str, download=download_archive) -> dict:
    """Preflight and stage the entire selection before swapping any live folder.

    Old versions remain in .integration_catalog_backups. Each folder replacement
    is atomic; a failed swap restores that folder. A process crash between the two
    renames may require restoring its retained backup (documented in INSTALL.md).
    """
    config = Path(config_dir).resolve()
    components = config / "custom_components"
    backup_root = config / ".integration_catalog_backups"
    if components.is_symlink() or backup_root.is_symlink():
        raise InstallError("Component and backup directories must not be symbolic links")
    components.mkdir(exist_ok=True)
    by_domain = {item["domain"]: item for item in catalog}
    if not selected or len(set(selected)) != len(selected) or set(selected) - by_domain.keys():
        raise InstallError("Select at least one known integration, without duplicates")
    with install_lock(config), tempfile.TemporaryDirectory(
        prefix=".integration-catalog-", dir=config
    ) as staging:
        pending = []
        for domain in selected:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", domain) or domain in RESERVED_DOMAINS:
                raise InstallError(f"Invalid integration domain: {domain}")
            item = by_domain[domain]
            if not compatible(ha_version, item.get("homeassistant", "")):
                raise InstallError(f"{item['name']}: requires Home Assistant {item['homeassistant']}")
            previous = check_owned(components / domain, item)
            expected_hashes = {name: source["sha256"] for name, source in item["files"].items()}
            if previous and previous.get("commit") == item["commit"] and previous["hashes"] == expected_hashes:
                continue
            pending.append((item, previous))
        for item, _ in pending:
            folder = Path(staging) / item["domain"]
            folder.mkdir()
            extract_verified(download(item), item, folder)
        changed = []
        try:
            for item, previous in pending:
                domain = item["domain"]
                target = components / domain
                # Check again after downloading, in case another tool changed files.
                if check_owned(target, item) != previous:
                    raise InstallError(f"{item['name']}: installation changed during download")
                backup = None
                if target.exists():
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    backup = backup_root / f"{domain}-{stamp}"
                    backup_root.mkdir(exist_ok=True)
                    target.rename(backup)
                try:
                    (Path(staging) / domain).rename(target)
                except OSError:
                    if backup is not None:
                        backup.rename(target)
                    raise
                changed.append(item["name"])
        except Exception as err:
            suffix = f" Already applied: {', '.join(changed)}. Restart Home Assistant." if changed else ""
            raise InstallError(f"{err}.{suffix}") from err
        return {"changed": changed, "selected": selected}

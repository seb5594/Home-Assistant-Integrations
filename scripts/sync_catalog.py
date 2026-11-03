#!/usr/bin/env python3
"""Discover published integration releases; generate metadata and gitlinks.

No private workflow engine is needed. All generated metadata and file hashes
come from an immutable source commit. A failed discovery never prunes entries.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/seb5594_integration_catalog"
OWNER = "seb5594"
HUB = f"{OWNER}/Home-Assistant-Integrations"
REPO_PATTERN = re.compile(r"^(hass-.+-integration|Home-Assistant-.+-Integration)$", re.I)
BRAND_SOURCES = {
    "pulseaudio_loopback": (
        "https://raw.githubusercontent.com/home-assistant/brands/"
        "2448af4760063a885f173080eb5381323b7ae9a4/core_integrations/pulseaudio_loopback/icon.png"
    ),
}


def fetch(url, *, api=False):
    headers = {"User-Agent": "Home-Assistant-Integration-Catalog"}
    if api and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return response.read()


def api(path):
    return json.loads(fetch(f"https://api.github.com/{path}", api=True))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")


def write_public_feed(items):
    """Small polling feed pointing to the latest published release packages."""
    write_json(ROOT / "catalog-feed.json", {
        "schema_version": 2,
        "integrations": [
            {key: item[key] for key in ("repository", "domain", "name", "version", "release_tag", "release_url", "package_url")}
            for item in items
        ],
    })


def inspect_repository(repo):
    repository = repo["full_name"]
    try:
        release = api(f"repos/{repository}/releases/latest")
    except HTTPError as err:
        if err.code == 404:
            print(f"Skipping {repository}: no published stable release", flush=True)
            return None
        raise
    if release.get("draft") or release.get("prerelease") or not release.get("published_at"):
        return None
    tag = release["tag_name"]
    # Resolve the tag itself: target_commitish can be a moving branch name.
    commit = api(f"repos/{repository}/commits/{quote(tag, safe='')}")["sha"]
    archive = ZipFile(BytesIO(fetch(f"https://codeload.github.com/{repository}/zip/{commit}")))
    root = archive.namelist()[0].split("/")[0] + "/"
    files = {name[len(root):]: archive.read(name) for name in archive.namelist()
             if name.startswith(root) and not name.endswith("/")}
    manifests = sorted(path for path in files if re.fullmatch(
        r"custom_components/[^/]+/manifest.json", path
    ))
    if not manifests:
        return None
    if len(manifests) != 1:
        raise ValueError(f"{repository}: expected exactly one integration")
    manifest_path = manifests[0]
    source_manifest = json.loads(files[manifest_path])
    domain = source_manifest["domain"]
    if manifest_path != f"custom_components/{domain}/manifest.json":
        raise ValueError(f"{repository}: manifest domain does not match its directory")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", domain) or domain in {"hacs", "homeassistant", "seb5594_integration_catalog"}:
        raise ValueError(f"{repository}: unsafe domain {domain}")
    hacs = json.loads(files.get("hacs.json", b"{}"))
    filename = hacs.get("filename") or f"{domain}.zip"
    asset = next((asset for asset in release.get("assets", [])
                  if asset["name"] == filename and asset.get("state") == "uploaded"), None)
    if asset is None:
        print(f"Skipping {repository}: latest release has no uploaded {filename}", flush=True)
        return None
    package_url = f"https://github.com/{repository}/releases/download/{quote(tag, safe='')}/{quote(filename, safe='')}"
    if asset["browser_download_url"] != package_url:
        raise ValueError(f"{repository}: unexpected release package URL")
    package_data = fetch(package_url)
    package_hash = hashlib.sha256(package_data).hexdigest()
    if asset.get("digest") and asset["digest"] != f"sha256:{package_hash}":
        raise ValueError(f"{repository}: release package digest mismatch")
    package_files = read_package(package_data)
    package_manifests = [path for path in package_files if path == "manifest.json" or path.endswith("/manifest.json")]
    if len(package_manifests) != 1:
        raise ValueError(f"{repository}: release package must contain exactly one manifest")
    package_manifest_path = package_manifests[0]
    package_prefix = package_manifest_path.removesuffix("manifest.json")
    manifest = json.loads(package_files[package_manifest_path])
    if manifest.get("domain") != domain or tag.removeprefix("v") != manifest.get("version"):
        raise ValueError(f"{repository}: release tag and packaged manifest disagree")
    readme = html.unescape(files.get("README.md", b"").decode("utf-8"))
    test_match = re.search(r"label=tests&message=([^&\s)\"]+)", readme)
    item = {
        "repository": repository, "commit": commit, "domain": domain,
        "name": manifest["name"], "version": manifest["version"],
        "release_tag": tag,
        "release_url": f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}",
        "published_at": release["published_at"],
        "package_url": package_url,
        "package": {"name": filename, "url": package_url, "sha256": package_hash},
        "homeassistant": hacs.get("homeassistant", ""),
        "description": repo.get("description") or manifest["name"],
        "changelog": next((p for p in ("CHANGELOG.md", "CHANGES.md") if p in files), ""),
        "ci": next((p.split("/")[-1] for p in (
            ".github/workflows/ci.yml", ".github/workflows/test.yml"
        ) if p in files), ""),
        "tests": unquote(test_match[1]) if test_match else "",
        "logo": "assets/catalog.svg",
        "logo_source": "Original catalog fallback symbol; not a source project brand asset.",
    }
    for logo in ("brand/logo.png", "brand/icon.png", "logo.png", "icon.png"):
        if package_prefix + logo in package_files:
            asset = f"assets/brands/{domain}.png"
            (ROOT / asset).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / asset).write_bytes(package_files[package_prefix + logo])
            item["logo"] = asset
            item["logo_source"] = f"{item['release_url']} ({filename}: {logo})"
            break
    if item["logo"] == "assets/catalog.svg" and domain in BRAND_SOURCES:
        asset = f"assets/brands/{domain}.png"
        (ROOT / asset).write_bytes(fetch(BRAND_SOURCES[domain]))
        item["logo"] = asset
        item["logo_source"] = BRAND_SOURCES[domain]
    return item


def read_package(data):
    """Read release metadata and branding without extracting source files to disk."""
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Release package exceeds download limit")
    with ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > 128 * 1024 * 1024:
            raise ValueError("Release package exceeds expanded size limit")
        if len({info.filename for info in infos}) != len(infos):
            raise ValueError("Duplicate release package entries")
        for info in infos:
            name = info.filename.rstrip("/")
            if any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in name.split("/")):
                raise ValueError("Unsafe release package path")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Release package contains a symbolic link")
        return {info.filename: archive.read(info) for info in infos if not info.is_dir()}


def badge(label, message, color="1877A5", url=""):
    src = f"https://img.shields.io/static/v1?label={quote(label)}&message={quote(message)}&color={color}&style=flat"
    image = f"![{label}: {message}]({src})"
    return f"[{image}]({url})" if url else image


def render_readme(items):
    body = (ROOT / "templates/README.md").read_text("utf-8")
    overview, cards = [], []
    for item in items:
        repo = item["repository"]
        url = f"https://github.com/{repo}"
        hacs = f"https://my.home-assistant.io/redirect/hacs_repository/?owner={OWNER}&repository={repo.split('/')[1]}&category=integration"
        overview.append(
            f"| <img src=\"{item['logo']}\" height=\"44\" alt=\"\"> "
            f"| **[{item['name']}]({url})** | [{item['release_tag']}]({item['release_url']}) "
            f"| {item['homeassistant'] or 'See documentation'} | [Install]({hacs}) |"
        )
        version = badge("release", item["release_tag"], url=item["release_url"])
        minimum = badge("Home Assistant", "≥ " + item["homeassistant"]) if item["homeassistant"] else ""
        checks = (f"[![release checks](https://img.shields.io/github/check-runs/{repo}/{item['commit']}?label=release%20checks)]({url}/commit/{item['commit']}/checks)"
                  if item["ci"] else "")
        tests = badge("tests", item["tests"], "2F855A") if item["tests"] else ""
        downloads = f"[![release downloads](https://img.shields.io/github/downloads/{repo}/{quote(item['release_tag'], safe='')}/total?label=downloads)]({item['package_url']})"
        issues = f"[![issues](https://img.shields.io/github/issues/{repo}?label=issues)]({url}/issues)"
        changelog = f" · [Changelog]({url}/blob/{quote(item['release_tag'], safe='')}/{item['changelog']})" if item["changelog"] else ""
        cards.append(
            f"### <img src=\"{item['logo']}\" height=\"48\" alt=\"\"> {item['name']}\n\n"
            f"{item['description']}\n\n"
            f"{version} {minimum}<br>\n{checks} {tests} {downloads} {issues}\n\n"
            f"[**Open in HACS**]({hacs}) · [Release package]({item['package_url']}) · [Documentation]({url}/tree/{quote(item['release_tag'], safe='')}){changelog}\n\n"
            f"<details>\n<summary>Release and source details</summary>\n\n"
            f"- Domain: `{item['domain']}`\n"
            f"- Published release: [{item['release_tag']}]({item['release_url']})\n"
            f"- Source: [`integrations/{item['domain']}`](integrations/{item['domain']}) (Git submodule)\n"
            f"- Pinned commit: [`{item['commit'][:7]}`]({url}/commit/{item['commit']})\n"
            f"- Test count, when shown, is copied from the source README at this commit.\n\n"
            f"</details>\n"
        )
    body = body.replace("{{COUNT}}", str(len(items)))
    body = body.replace("{{OVERVIEW}}", "\n".join(overview))
    return body.replace("{{INTEGRATIONS}}", "\n".join(cards))


def sync_submodules(items):
    lines = []
    existing = subprocess.check_output(["git", "ls-files", "--stage", "integrations/"], cwd=ROOT, text=True)
    desired = {f"integrations/{item['domain']}" for item in items}
    for line in existing.splitlines():
        mode_sha, path = line.split("\t", 1)
        if mode_sha.startswith("160000 ") and path not in desired:
            subprocess.run(["git", "update-index", "--force-remove", "--", path], cwd=ROOT, check=True)
    for item in items:
        path = f"integrations/{item['domain']}"
        (ROOT / path).mkdir(parents=True, exist_ok=True)
        lines.extend([f'[submodule "{item["domain"]}"]', f"\tpath = {path}",
                      f"\turl = https://github.com/{item['repository']}.git"])
        subprocess.run(["git", "update-index", "--add", "--cacheinfo",
                        f"160000,{item['commit']},{path}"], cwd=ROOT, check=True)
    (ROOT / ".gitmodules").write_text("\n".join(lines) + "\n", "utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-lock", action="store_true", help="Render README from the existing lock, without network or index changes")
    args = parser.parse_args()
    if args.from_lock:
        items = json.loads((COMPONENT / "catalog.json").read_text("utf-8"))
    else:
        repositories = []
        for page in range(1, 100):
            batch = api(f"users/{OWNER}/repos?per_page=100&page={page}")
            repositories.extend(batch)
            if len(batch) < 100:
                break
        items = []
        for repo in sorted(repositories, key=lambda r: r["name"].lower()):
            if repo.get("private") or repo.get("archived") or repo.get("disabled") or not REPO_PATTERN.fullmatch(repo["name"]):
                continue
            print(f"Inspecting {repo['full_name']}", flush=True)
            item = inspect_repository(repo)
            if item:
                items.append(item)
        if not items or len({item["domain"] for item in items}) != len(items):
            raise ValueError("Discovery returned no integrations or duplicate domains; refusing to replace catalog")
        items.sort(key=lambda item: item["name"].casefold())
        previous = json.loads((COMPONENT / "catalog.json").read_text("utf-8")) if (COMPONENT / "catalog.json").exists() else None
        sync_submodules(items)
        write_json(COMPONENT / "catalog.json", items)
        write_json(ROOT / ".github/catalog.json", [
            {"repository": item["repository"], "commit": item["commit"]} for item in items
        ])
        if items != previous:
            manifest = json.loads((COMPONENT / "manifest.json").read_text("utf-8"))
            now = datetime.now(timezone.utc)
            candidate = (now.year, now.month, now.day, 0)
            previous_version = tuple(map(int, manifest["version"].split(".")))
            if candidate <= previous_version:
                candidate = previous_version[:-1] + (previous_version[-1] + 1,)
            manifest["version"] = ".".join(map(str, candidate))
            write_json(COMPONENT / "manifest.json", manifest)
    write_public_feed(items)
    (ROOT / "README.md").write_text(render_readme(items), "utf-8")
    sources = "# Brand assets\n\nSource graphics retain their original rights and licenses.\n\n" + "\n".join(
        f"- **{item['name']}** (`{item['logo']}`): {item['logo_source']}" for item in items
    )
    (ROOT / "assets/brands/README.md").write_text(sources + "\n", "utf-8")
    print(f"Catalog: {len(items)} integrations")


if __name__ == "__main__":
    main()

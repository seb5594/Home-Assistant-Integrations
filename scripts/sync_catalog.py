#!/usr/bin/env python3
"""Discover public integrations; generate a README, installer lock and gitlinks.

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
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/integration_catalog"
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


def inspect_repository(repo):
    repository = repo["full_name"]
    commit = api(f"repos/{repository}/commits/{repo['default_branch']}")["sha"]
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
    manifest = json.loads(files[manifest_path])
    domain = manifest["domain"]
    if manifest_path != f"custom_components/{domain}/manifest.json":
        raise ValueError(f"{repository}: manifest domain does not match its directory")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", domain) or domain in {"hacs", "homeassistant", "integration_catalog"}:
        raise ValueError(f"{repository}: unsafe domain {domain}")
    prefix = f"custom_components/{domain}/"
    locked_files = {}
    for path, content in files.items():
        if path.startswith(prefix):
            relative = path[len(prefix):]
        elif re.fullmatch(r"(LICENSE|COPYING|NOTICE)(\.[^/]+)?", path, re.I):
            relative = f".source-license/{path}"
        else:
            continue
        locked_files[relative] = {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
    hacs = json.loads(files.get("hacs.json", b"{}"))
    readme = html.unescape(files.get("README.md", b"").decode("utf-8"))
    test_match = re.search(r"label=tests&message=([^&\s)\"]+)", readme)
    item = {
        "repository": repository, "commit": commit, "domain": domain,
        "name": manifest["name"], "version": manifest["version"],
        "homeassistant": hacs.get("homeassistant", ""),
        "description": repo.get("description") or manifest["name"],
        "branch": repo["default_branch"],
        "changelog": next((p for p in ("CHANGELOG.md", "CHANGES.md") if p in files), ""),
        "ci": next((p.split("/")[-1] for p in (
            ".github/workflows/ci.yml", ".github/workflows/test.yml"
        ) if p in files), ""),
        "tests": unquote(test_match[1]) if test_match else "",
        "logo": "assets/catalog.svg",
        "logo_source": "Original catalog fallback symbol; not a source project brand asset.",
        "files": dict(sorted(locked_files.items())),
    }
    for logo in ("brand/logo.png", "brand/icon.png", "logo.png", "icon.png"):
        if prefix + logo in files:
            asset = f"assets/brands/{domain}.png"
            (ROOT / asset).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / asset).write_bytes(files[prefix + logo])
            item["logo"] = asset
            item["logo_source"] = f"https://github.com/{repository}/blob/{commit}/{prefix}{logo}"
            break
    if item["logo"] == "assets/catalog.svg" and domain in BRAND_SOURCES:
        asset = f"assets/brands/{domain}.png"
        (ROOT / asset).write_bytes(fetch(BRAND_SOURCES[domain]))
        item["logo"] = asset
        item["logo_source"] = BRAND_SOURCES[domain]
    return item


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
            f"| **[{item['name']}]({url})** | {item['version']} "
            f"| {item['homeassistant'] or 'See documentation'} | [Install]({hacs}) |"
        )
        version = badge("version", item["version"], url=f"{url}/releases")
        minimum = badge("Home Assistant", "≥ " + item["homeassistant"]) if item["homeassistant"] else ""
        checks = (f"[![checks](https://img.shields.io/github/actions/workflow/status/{repo}/{item['ci']}?branch={quote(item['branch'])}&label=checks)]({url}/actions/workflows/{item['ci']})"
                  if item["ci"] else "")
        tests = badge("tests", item["tests"], "2F855A") if item["tests"] else ""
        downloads = f"[![downloads](https://img.shields.io/github/downloads/{repo}/total?label=downloads)]({url}/releases)"
        issues = f"[![issues](https://img.shields.io/github/issues/{repo}?label=issues)]({url}/issues)"
        changelog = f" · [Changelog]({url}/blob/{item['branch']}/{item['changelog']})" if item["changelog"] else ""
        cards.append(
            f"### <img src=\"{item['logo']}\" height=\"48\" alt=\"\"> {item['name']}\n\n"
            f"{item['description']}\n\n"
            f"{version} {minimum}<br>\n{checks} {tests} {downloads} {issues}\n\n"
            f"[**Open in HACS**]({hacs}) · [Documentation]({url}){changelog}\n\n"
            f"<details>\n<summary>Source snapshot and technical details</summary>\n\n"
            f"- Domain: `{item['domain']}`\n"
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
            manifest["version"] = f"{now.year}.{now.month}.{now.day}.{now.hour * 3600 + now.minute * 60 + now.second}"
            write_json(COMPONENT / "manifest.json", manifest)
    (ROOT / "README.md").write_text(render_readme(items), "utf-8")
    sources = "# Brand assets\n\nSource graphics retain their original rights and licenses.\n\n" + "\n".join(
        f"- **{item['name']}** (`{item['logo']}`): {item['logo_source']}" for item in items
    )
    (ROOT / "assets/brands/README.md").write_text(sources + "\n", "utf-8")
    print(f"Catalog: {len(items)} integrations")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the HACS release asset; the component files are at the ZIP root."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/seb5594_integration_catalog"


def build_release(output: Path):
    manifest = json.loads((COMPONENT / "manifest.json").read_text("utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    package = output / "seb5594_integration_catalog.zip"
    with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(COMPONENT.rglob("*")):
            relative = path.relative_to(COMPONENT)
            if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise ValueError(f"Release component contains a symbolic link: {path}")
            if path.is_file():
                archive.write(path, relative.as_posix())
    with ZipFile(package) as archive:
        if json.loads(archive.read("manifest.json")) != manifest or "__init__.py" not in archive.namelist():
            raise ValueError("Invalid HACS package layout")
    checksum = hashlib.sha256(package.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{checksum}  {package.name}\n", "utf-8")
    print(f"v{manifest['version']}: {package}")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    build_release(parser.parse_args().output)

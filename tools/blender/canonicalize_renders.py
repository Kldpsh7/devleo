"""Canonicalize Blender PNGs and refresh manifest hashes deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonicalize(path: Path) -> None:
    image = Image.open(path).convert("RGBA")
    pixels = bytearray(image.tobytes())
    for index in range(0, len(pixels), 4):
        if pixels[index + 3] == 0:
            pixels[index : index + 3] = b"\x00\x00\x00"
    canonical = Image.frombytes("RGBA", image.size, bytes(pixels))
    canonical.save(path, format="PNG", compress_level=9, optimize=False)


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest_path = render_dir / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [manifest["neutral"], *manifest["animation"]["frames"]]
    for entry in entries:
        path = render_dir / entry["file"]
        canonicalize(path)
        entry["sha256"] = checksum(path)
        entry["bytes"] = path.stat().st_size
    manifest["generator"]["canonicalizer"] = "tools/blender/canonicalize_renders.py"
    manifest["render"]["hidden_rgb_under_zero_alpha"] = "cleared"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_CANONICAL_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()

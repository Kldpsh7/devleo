"""Register non-airborne Blender animation frames to one alpha ground line."""

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
    parser.add_argument("--ground-line", type=int, required=True)
    return parser.parse_args()


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register(path: Path, ground_line: int) -> int:
    image = Image.open(path).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"cannot register empty frame: {path}")
    shift_y = ground_line - bbox[3]
    shifted_bbox = (bbox[0], bbox[1] + shift_y, bbox[2], bbox[3] + shift_y)
    if shifted_bbox[1] < 0 or shifted_bbox[3] > image.height:
        raise ValueError(f"ground registration would clip {path}: {shifted_bbox}")
    registered = Image.new("RGBA", image.size, (0, 0, 0, 0))
    registered.alpha_composite(image, (0, shift_y))
    registered.save(path, format="PNG", compress_level=9, optimize=False)
    return shift_y


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest_path = render_dir / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [
        frame for animation in manifest.get("animations", []) for frame in animation["frames"]
    ]
    shifts: dict[str, int] = {}
    for entry in entries:
        relative_path = entry["file"]
        if relative_path not in shifts:
            path = render_dir / relative_path
            shifts[relative_path] = register(path, args.ground_line)
        path = render_dir / relative_path
        entry["sha256"] = checksum(path)
        entry["bytes"] = path.stat().st_size

    neutral_path = manifest["neutral"]["file"]
    neutral_entry = next(entry for entry in entries if entry["file"] == neutral_path)
    manifest["neutral"] = dict(neutral_entry)
    manifest["generator"]["ground_registrar"] = "tools/blender/register_grounded_frames.py"
    manifest["render"]["ground_line_px"] = args.ground_line
    manifest["render"]["ground_shift_range_px"] = [min(shifts.values()), max(shifts.values())]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_GROUND_REGISTERED={manifest_path}")


if __name__ == "__main__":
    main()

"""Extract the four diagonal Leo views from a 2x2 reference sheet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from extract_turnaround_textures import components, dilate, extend_edge_colors
from PIL import Image

VIEW_NAMES = ("front_left", "front_right", "rear_left", "rear_right")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_subject(panel: Image.Image) -> Image.Image:
    rgba = np.asarray(panel.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    border = max(10, panel.width // 60)
    border_pixels = np.concatenate(
        (rgb[:border].reshape(-1, 3), rgb[-border:].reshape(-1, 3)), axis=0
    )
    background = np.median(border_pixels, axis=0)
    distance = np.sqrt(np.sum((rgb - background) ** 2, axis=2))
    alpha = np.clip((distance - 9.0) * (255.0 / 27.0), 0.0, 255.0).astype(np.uint8)
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = (maximum - minimum) / np.maximum(maximum, 1.0)
    seed = (alpha >= 42) & ((saturation >= 0.12) | (maximum <= 120.0))
    subjects = sorted(components(seed), key=len, reverse=True)
    if not subjects:
        raise RuntimeError("No cub subject found in diagonal reference panel")
    component_mask = np.zeros(seed.shape, dtype=bool)
    y_values, x_values = zip(*subjects[0], strict=True)
    component_mask[np.asarray(y_values), np.asarray(x_values)] = True
    keep = dilate(component_mask, 7)
    alpha[~keep] = 0
    rgba[:, :, 3] = alpha
    visible_y, visible_x = np.nonzero(alpha >= 8)
    padding = 6
    left = max(0, int(visible_x.min()) - padding)
    top = max(0, int(visible_y.min()) - padding)
    right = min(panel.width, int(visible_x.max()) + padding + 1)
    bottom = min(panel.height, int(visible_y.max()) + padding + 1)
    return Image.fromarray(rgba, mode="RGBA").crop((left, top, right, bottom))


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGBA")
    midpoint_x = image.width // 2
    midpoint_y = image.height // 2
    panels = (
        image.crop((0, 0, midpoint_x, midpoint_y)),
        image.crop((midpoint_x, 0, image.width, midpoint_y)),
        image.crop((0, midpoint_y, midpoint_x, image.height)),
        image.crop((midpoint_x, midpoint_y, image.width, image.height)),
    )

    views: dict[str, object] = {}
    for name, panel in zip(VIEW_NAMES, panels, strict=True):
        texture = extract_subject(panel)
        output = output_dir / f"{name}.png"
        texture.save(output, optimize=True)
        projection = output_dir / f"{name}-projection.png"
        extend_edge_colors(texture).save(projection, optimize=True)
        views[name] = {
            "file": output.name,
            "sha256": sha256(output),
            "projection_file": projection.name,
            "projection_sha256": sha256(projection),
            "texture_size": [texture.width, texture.height],
        }

    manifest = {
        "schema_version": 1,
        "source": str(source),
        "source_sha256": sha256(source),
        "layout": "2x2 front-left/front-right/rear-left/rear-right",
        "views": views,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"LEO_DIAGONAL_TEXTURES={output_dir}")


if __name__ == "__main__":
    main()

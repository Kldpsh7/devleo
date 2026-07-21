"""Extract transparent project-owned texture projections from Leo's turnaround."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

VIEW_NAMES = ("front", "left", "rear", "right")


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


def components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    result: list[list[tuple[int, int]]] = []
    for start_y, start_x in zip(*np.nonzero(mask), strict=True):
        if visited[start_y, start_x]:
            continue
        queue: deque[tuple[int, int]] = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True
        component: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            component.append((y, x))
            for next_y, next_x in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if not (0 <= next_y < height and 0 <= next_x < width):
                    continue
                if visited[next_y, next_x] or not mask[next_y, next_x]:
                    continue
                visited[next_y, next_x] = True
                queue.append((next_y, next_x))
        if len(component) >= 1000:
            result.append(component)
    return result


def dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(iterations):
        expanded = result.copy()
        expanded[1:] |= result[:-1]
        expanded[:-1] |= result[1:]
        expanded[:, 1:] |= result[:, :-1]
        expanded[:, :-1] |= result[:, 1:]
        result = expanded
    return result


def erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(iterations):
        contracted = result.copy()
        contracted[1:] &= result[:-1]
        contracted[:-1] &= result[1:]
        contracted[:, 1:] &= result[:, :-1]
        contracted[:, :-1] &= result[:, 1:]
        result = contracted
    return result


def extend_edge_colors(texture: Image.Image) -> Image.Image:
    """Fill projection-only transparent pixels from the nearest subject color."""
    rgba = np.asarray(texture.convert("RGBA"), dtype=np.uint8).copy()
    known = erode(rgba[:, :, 3] >= 220, 6)
    if not np.any(known):
        raise RuntimeError("Cannot extend an empty turnaround texture")
    queue: deque[tuple[int, int]] = deque(
        (int(y), int(x)) for y, x in zip(*np.nonzero(known), strict=True)
    )
    height, width = known.shape
    while queue:
        y, x = queue.popleft()
        for next_y, next_x in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if not (0 <= next_y < height and 0 <= next_x < width) or known[next_y, next_x]:
                continue
            rgba[next_y, next_x, :3] = rgba[y, x, :3]
            known[next_y, next_x] = True
            queue.append((next_y, next_x))
    rgba[:, :, 3] = 255
    return Image.fromarray(rgba, mode="RGBA")


def extract_views(image: Image.Image) -> list[tuple[Image.Image, dict[str, object]]]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    border = max(12, image.width // 80)
    border_pixels = np.concatenate((rgb[:, :border], rgb[:, -border:]), axis=1)
    background = np.median(border_pixels, axis=1, keepdims=True)
    distance = np.sqrt(np.sum((rgb - background) ** 2, axis=2))
    alpha = np.clip((distance - 11.0) * (255.0 / 25.0), 0.0, 255.0).astype(np.uint8)
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = (maximum - minimum) / np.maximum(maximum, 1.0)
    seed = (alpha >= 46) & ((saturation >= 0.10) | (maximum <= 125.0))
    subjects = sorted(components(seed), key=len, reverse=True)[:4]
    if len(subjects) != 4:
        raise RuntimeError(f"Expected four turnaround subjects, found {len(subjects)}")
    subjects.sort(key=lambda component: min(x for _, x in component))

    outputs: list[tuple[Image.Image, dict[str, object]]] = []
    for component in subjects:
        component_mask = np.zeros(seed.shape, dtype=bool)
        y_values, x_values = zip(*component, strict=True)
        component_mask[np.asarray(y_values), np.asarray(x_values)] = True
        keep = dilate(component_mask, 5)
        view_alpha = alpha.copy()
        view_alpha[~keep] = 0
        view_rgba = rgba.copy()
        view_rgba[:, :, 3] = view_alpha
        visible_y, visible_x = np.nonzero(view_alpha >= 8)
        padding = 4
        left = max(0, int(visible_x.min()) - padding)
        top = max(0, int(visible_y.min()) - padding)
        right = min(image.width, int(visible_x.max()) + padding + 1)
        bottom = min(image.height, int(visible_y.max()) + padding + 1)
        crop = Image.fromarray(view_rgba, mode="RGBA").crop((left, top, right, bottom))
        outputs.append(
            (
                crop,
                {
                    "source_size": [image.width, image.height],
                    "crop_box": [left, top, right, bottom],
                    "texture_size": [crop.width, crop.height],
                    "opaque_pixels": int(np.count_nonzero(view_alpha >= 245)),
                    "visible_pixels": int(np.count_nonzero(view_alpha >= 8)),
                },
            )
        )
    return outputs


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGBA")
    views: dict[str, object] = {}
    for name, (texture, metadata) in zip(VIEW_NAMES, extract_views(image), strict=True):
        if name == "front":
            # The canonical front reference includes a tail tuft beside the
            # left hind leg. Remove that asymmetric margin before projection
            # so the face, chest, and paws stay centered on the sculpt.
            trim = round(texture.width * 0.16)
            texture = texture.crop((trim, 0, texture.width, texture.height))
            metadata["projection_trim"] = [trim, 0, 0, 0]
            metadata["texture_size"] = [texture.width, texture.height]
        output = output_dir / f"{name}.png"
        texture.save(output, optimize=True)
        projection_output = output_dir / f"{name}-projection.png"
        extend_edge_colors(texture).save(projection_output, optimize=True)
        metadata["file"] = output.name
        metadata["sha256"] = sha256(output)
        metadata["projection_file"] = projection_output.name
        metadata["projection_sha256"] = sha256(projection_output)
        views[name] = metadata
    manifest = {
        "schema_version": 1,
        "source": str(source),
        "source_sha256": sha256(source),
        "method": "row-background distance plus largest connected component",
        "views": views,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"LEO_TURNAROUND_TEXTURES={output_dir}")


if __name__ == "__main__":
    main()

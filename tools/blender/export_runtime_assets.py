"""Export approved Blender masters into deterministic runtime density tiers."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

MASTER_SIZE = (1152, 1248)
MASTER_GROUND_LINE = 1214
CELL_SIZE = (192, 208)
DENSITIES = {"1x": 1, "2x": 2, "4x": 4}
ATLAS_COLUMNS = 8
ATLAS_ROWS = 11


@dataclass(frozen=True)
class FamilySpec:
    path: str
    expected_frames: int
    frame_duration_ms: int
    loop: bool


FAMILIES = {
    "idle": FamilySpec("idle-prototype/idle", 12, 167, True),
    "walk-right": FamilySpec("locomotion/animations/walk-right", 12, 125, True),
    "walk-left": FamilySpec("locomotion/animations/walk-left", 12, 125, True),
    "run-right": FamilySpec("locomotion/animations/run-right", 12, 85, True),
    "run-left": FamilySpec("locomotion/animations/run-left", 12, 85, True),
    "wave": FamilySpec("gestures/animations/wave", 10, 150, False),
    "jump": FamilySpec("gestures/animations/jump", 12, 110, False),
    "failure": FamilySpec("core-animations/animations/failure", 14, 140, False),
    "waiting": FamilySpec("core-animations/animations/waiting", 12, 210, True),
    "working": FamilySpec("core-animations/animations/working", 16, 145, True),
    "review": FamilySpec("core-animations/animations/review", 12, 210, True),
    "idle-to-walk-right": FamilySpec("transitions/animations/idle-to-walk-right", 20, 70, False),
    "walk-right-to-idle": FamilySpec("transitions/animations/walk-right-to-idle", 20, 70, False),
    "idle-to-walk-left": FamilySpec("transitions/animations/idle-to-walk-left", 20, 70, False),
    "walk-left-to-idle": FamilySpec("transitions/animations/walk-left-to-idle", 20, 70, False),
    "gaze": FamilySpec("gaze-directions/directions", 16, 200, False),
}

# Codex v2 standard row contract. Directional rows intentionally use Leo's
# approved pounce-Run family; the calmer Walk family remains in the full export.
ATLAS_ROWS_SPEC: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("idle", "idle", (0, 2, 4, 6, 8, 10)),
    ("running-right", "run-right", (0, 2, 3, 5, 6, 8, 9, 11)),
    ("running-left", "run-left", (0, 2, 3, 5, 6, 8, 9, 11)),
    ("waving", "wave", (0, 3, 5, 8)),
    ("jumping", "jump", (0, 3, 5, 8, 11)),
    ("failed", "failure", (0, 2, 4, 6, 8, 10, 12, 13)),
    ("waiting", "waiting", (0, 2, 4, 6, 8, 10)),
    ("running", "working", (0, 3, 6, 8, 11, 14)),
    ("review", "review", (0, 2, 4, 6, 8, 10)),
    ("look-row-9", "gaze", tuple(range(0, 8))),
    ("look-row-10", "gaze", tuple(range(8, 16))),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rgba(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != MASTER_SIZE:
        raise ValueError(f"unexpected master size for {path}: {image.size}")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"empty master frame: {path}")
    return image


def clear_hidden_rgb(image: Image.Image) -> Image.Image:
    pixels = bytearray(image.convert("RGBA").tobytes())
    for index in range(0, len(pixels), 4):
        if pixels[index + 3] == 0:
            pixels[index : index + 3] = b"\x00\x00\x00"
    return Image.frombytes("RGBA", image.size, bytes(pixels))


def shift_image(image: Image.Image, shift_y: int) -> Image.Image:
    if shift_y == 0:
        return image.copy()
    bbox = image.getchannel("A").getbbox()
    if bbox is None or bbox[1] + shift_y < 0 or bbox[3] + shift_y > image.height:
        raise ValueError(f"ground shift {shift_y} would clip frame with bbox {bbox}")
    shifted = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shifted.alpha_composite(image, (0, shift_y))
    return shifted


def resize_master(image: Image.Image, density: int) -> Image.Image:
    size = (CELL_SIZE[0] * density, CELL_SIZE[1] * density)
    premultiplied = image.convert("RGBa")
    resized = premultiplied.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    return clear_hidden_rgb(resized)


def save_lossless_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="WEBP", lossless=True, quality=100, method=4, exact=True)


def discover_sources(source_root: Path) -> dict[str, list[Path]]:
    sources: dict[str, list[Path]] = {}
    for name, spec in FAMILIES.items():
        paths = sorted((source_root / spec.path).glob("*.png"))
        if len(paths) != spec.expected_frames:
            raise ValueError(
                f"expected {spec.expected_frames} {name} frames in {spec.path}, found {len(paths)}"
            )
        sources[name] = paths
    return sources


def ground_shifts(sources: dict[str, list[Path]]) -> dict[str, int]:
    shifts: dict[str, int] = {}
    for name, paths in sources.items():
        bottoms = []
        for path in paths:
            bbox = load_rgba(path).getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"empty master frame: {path}")
            bottoms.append(bbox[3])
        shifts[name] = MASTER_GROUND_LINE - max(bottoms)
    return shifts


def main() -> None:
    args = parse_args()
    source_root = args.source_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = discover_sources(source_root)
    shifts = ground_shifts(sources)

    source_entries = {
        name: [
            {
                "file": str(path.relative_to(source_root)),
                "sha256": checksum(path),
                "bytes": path.stat().st_size,
            }
            for path in paths
        ]
        for name, paths in sources.items()
    }
    density_entries: dict[str, object] = {}

    for density_name, density in DENSITIES.items():
        processed: dict[tuple[str, int, int], Image.Image] = {}
        cell_size = (CELL_SIZE[0] * density, CELL_SIZE[1] * density)
        atlas = Image.new(
            "RGBA",
            (ATLAS_COLUMNS * cell_size[0], ATLAS_ROWS * cell_size[1]),
            (0, 0, 0, 0),
        )
        frame_entries: dict[str, list[dict[str, object]]] = {}
        for family_name, paths in sources.items():
            family_entries: list[dict[str, object]] = []
            for index, path in enumerate(paths):
                image = resize_master(shift_image(load_rgba(path), shifts[family_name]), density)
                processed[(family_name, density, index)] = image
                frame_path = (
                    output_dir / "frames" / density_name / family_name / f"{index:02d}.webp"
                )
                save_lossless_webp(image, frame_path)
                family_entries.append(
                    {
                        "index": index,
                        "file": str(frame_path.relative_to(output_dir)),
                        "sha256": checksum(frame_path),
                        "bytes": frame_path.stat().st_size,
                    }
                )
            frame_entries[family_name] = family_entries

        atlas_rows: list[dict[str, object]] = []
        for row_index, (state, family_name, indices) in enumerate(ATLAS_ROWS_SPEC):
            for column, source_index in enumerate(indices):
                atlas.alpha_composite(
                    processed[(family_name, density, source_index)],
                    (column * cell_size[0], row_index * cell_size[1]),
                )
            row_entry: dict[str, object] = {
                "row": row_index,
                "state": state,
                "source_family": family_name,
                "source_indices": list(indices),
            }
            if row_index == 0:
                atlas.alpha_composite(
                    processed[("idle", density, 0)],
                    (6 * cell_size[0], 0),
                )
                row_entry["neutral_look_column"] = 6
                row_entry["neutral_look_source_index"] = 0
            atlas_rows.append(row_entry)

        atlas_dir = output_dir / "atlases" / density_name
        atlas_path = atlas_dir / "spritesheet.webp"
        save_lossless_webp(clear_hidden_rgb(atlas), atlas_path)
        if density_name == "1x":
            png_path = atlas_dir / "spritesheet.png"
            clear_hidden_rgb(atlas).save(png_path, format="PNG", compress_level=9, optimize=False)
        density_entries[density_name] = {
            "density": density,
            "cell_size": list(cell_size),
            "atlas_size": list(atlas.size),
            "atlas": str(atlas_path.relative_to(output_dir)),
            "atlas_sha256": checksum(atlas_path),
            "atlas_bytes": atlas_path.stat().st_size,
            "rows": atlas_rows,
            "frames": frame_entries,
        }

    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "runtime-export-candidate-not-installed",
        "spriteVersionNumber": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "master_size": list(MASTER_SIZE),
        "master_ground_line_px": MASTER_GROUND_LINE,
        "cell_size_1x": list(CELL_SIZE),
        "atlas_grid": [ATLAS_COLUMNS, ATLAS_ROWS],
        "sources": source_entries,
        "families": {
            name: {
                "frame_count": spec.expected_frames,
                "frame_duration_ms": spec.frame_duration_ms,
                "loop": spec.loop,
                "ground_shift_px": shifts[name],
            }
            for name, spec in FAMILIES.items()
        },
        "densities": density_entries,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_RUNTIME_EXPORT={output_dir}")


if __name__ == "__main__":
    main()

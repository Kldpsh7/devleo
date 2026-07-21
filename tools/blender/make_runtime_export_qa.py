"""Validate Leo's multi-density Blender runtime export and make previews."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

BACKGROUND = (27, 30, 36, 255)
ATLAS_COLUMNS = 8
ATLAS_ROWS = 11
USED_COLUMNS = (7, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path, required=True)
    return parser.parse_args()


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hidden_rgb_count(image: Image.Image) -> int:
    pixels = image.convert("RGBA").tobytes()
    return sum(
        1
        for index in range(0, len(pixels), 4)
        if pixels[index + 3] == 0 and any(pixels[index : index + 3])
    )


def compose(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, BACKGROUND)
    background.alpha_composite(image)
    return background.convert("RGB")


def preview_gif(
    images: list[Image.Image], duration: int, loop: bool, destination: Path
) -> None:
    frames = [compose(image) for image in images]
    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0 if loop else 1,
        optimize=False,
        disposal=2,
    )


def main() -> None:
    args = parse_args()
    export_dir = args.export_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (export_dir / "manifest.json").read_text(encoding="utf-8")
    )
    qa_dir = export_dir / "qa"
    preview_dir = qa_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    official_validation = json.loads(
        (qa_dir / "validation-v2.json").read_text(encoding="utf-8")
    )
    despill = json.loads(
        (qa_dir / "chroma-despill-extended.json").read_text(encoding="utf-8")
    )
    continuity = json.loads(
        (qa_dir / "look-continuity.json").read_text(encoding="utf-8")
    )

    overall_ok = (
        official_validation["ok"] is True
        and despill["ok"] is True
        and continuity["ok"] is True
    )
    density_qa: dict[str, Any] = {}
    for density_name, density_entry in manifest["densities"].items():
        density = density_entry["density"]
        cell_width, cell_height = density_entry["cell_size"]
        atlas_path = export_dir / density_entry["atlas"]
        atlas = Image.open(atlas_path).convert("RGBA")
        expected_atlas_size = (ATLAS_COLUMNS * cell_width, ATLAS_ROWS * cell_height)
        checksum_matches = checksum(atlas_path) == density_entry["atlas_sha256"]
        atlas_hidden_rgb = hidden_rgb_count(atlas)
        atlas_ok = (
            atlas.size == expected_atlas_size
            and checksum_matches
            and atlas_hidden_rgb == 0
        )

        cells: list[dict[str, object]] = []
        for row in range(ATLAS_ROWS):
            for column in range(ATLAS_COLUMNS):
                left = column * cell_width
                top = row * cell_height
                cell = atlas.crop((left, top, left + cell_width, top + cell_height))
                bbox = cell.getchannel("A").getbbox()
                used = column < USED_COLUMNS[row]
                nonempty = bbox is not None
                safe = bbox is None or (
                    bbox[0] > density
                    and bbox[1] > density
                    and bbox[2] < cell_width - density
                    and bbox[3] < cell_height - density
                )
                cell_ok = nonempty and safe if used else not nonempty
                atlas_ok &= cell_ok
                cells.append(
                    {
                        "row": row,
                        "column": column,
                        "used": used,
                        "ok": cell_ok,
                        "alpha_bbox": list(bbox) if bbox is not None else None,
                    }
                )

        family_qa: dict[str, Any] = {}
        for family_name, entries in density_entry["frames"].items():
            images: list[Image.Image] = []
            checksums_match = True
            hidden_rgb = 0
            touches_edge = False
            baselines: list[int] = []
            for entry in entries:
                path = export_dir / entry["file"]
                checksums_match &= checksum(path) == entry["sha256"]
                image = Image.open(path).convert("RGBA")
                if image.size != (cell_width, cell_height):
                    raise ValueError(f"unexpected frame size: {path} {image.size}")
                bbox = image.getchannel("A").getbbox()
                if bbox is None:
                    raise ValueError(f"empty runtime frame: {path}")
                hidden_rgb += hidden_rgb_count(image)
                touches_edge |= (
                    bbox[0] <= density
                    or bbox[1] <= density
                    or bbox[2] >= cell_width - density
                    or bbox[3] >= cell_height - density
                )
                baselines.append(bbox[3])
                images.append(image)

            expected_frames = manifest["families"][family_name]["frame_count"]
            unique_hashes = len({entry["sha256"] for entry in entries})
            loop = manifest["families"][family_name]["loop"]
            minimum_unique_hashes = (
                (expected_frames + 1) // 2
                if loop
                else expected_frames - (2 if family_name == "failure" else 1)
            )
            family_ok = (
                len(entries) == expected_frames
                and checksums_match
                and hidden_rgb == 0
                and not touches_edge
                and unique_hashes >= minimum_unique_hashes
            )
            atlas_ok &= family_ok
            family_qa[family_name] = {
                "ok": family_ok,
                "frame_count": len(entries),
                "unique_frame_hashes": unique_hashes,
                "minimum_unique_frame_hashes": minimum_unique_hashes,
                "checksums_match": checksums_match,
                "hidden_rgb_pixels_under_zero_alpha": hidden_rgb,
                "touches_safety_edge": touches_edge,
                "minimum_alpha_baseline_px": min(baselines),
                "maximum_alpha_baseline_px": max(baselines),
            }
            if density_name == "1x":
                spec = manifest["families"][family_name]
                preview_gif(
                    images,
                    spec["frame_duration_ms"],
                    spec["loop"],
                    preview_dir / f"{family_name}.gif",
                )

        overall_ok &= atlas_ok
        density_qa[density_name] = {
            "ok": atlas_ok,
            "density": density,
            "atlas_size": list(atlas.size),
            "atlas_checksum_matches": checksum_matches,
            "atlas_hidden_rgb_pixels_under_zero_alpha": atlas_hidden_rgb,
            "cells": cells,
            "families": family_qa,
        }

    qa = {
        "ok": overall_ok,
        "spriteVersionNumber": manifest["spriteVersionNumber"],
        "official_v2_validation_ok": official_validation["ok"],
        "despill_ok": despill["ok"],
        "look_continuity_ok": continuity["ok"],
        "densities": density_qa,
        "artifacts": {
            "contact_sheet": "qa/contact-sheet.png",
            "look_directions": "qa/look-directions.png",
            "direction_blind_pairs": "qa/direction-blind-pairs.png",
            "previews": "qa/previews",
        },
    }
    destination = qa_dir / "runtime-export.json"
    destination.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not overall_ok:
        raise SystemExit("runtime export QA failed")
    print(f"LEO_RUNTIME_EXPORT_QA={destination}")


if __name__ == "__main__":
    main()

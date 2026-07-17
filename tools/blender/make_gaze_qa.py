"""Validate Leo gaze renders and create labeled normal-size review artifacts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ALL_DIRECTIONS = (
    "000",
    "022.5",
    "045",
    "067.5",
    "090",
    "112.5",
    "135",
    "157.5",
    "180",
    "202.5",
    "225",
    "247.5",
    "270",
    "292.5",
    "315",
    "337.5",
)
CARDINALS = ("000", "090", "180", "270")
CELL = (192, 208)
ATLAS = (1536, 2288)
BACKGROUND = (27, 30, 36, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def hidden_rgb_count(image: Image.Image) -> int:
    pixels = image.tobytes()
    return sum(
        1
        for index in range(0, len(pixels), 4)
        if pixels[index + 3] == 0 and any(pixels[index : index + 3])
    )


def normal_cell(image: Image.Image) -> Image.Image:
    return image.resize(CELL, Image.Resampling.LANCZOS)


def compose(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, BACKGROUND)
    background.alpha_composite(image)
    return background.convert("RGB")


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (render_dir / "manifest.json").read_text(encoding="utf-8")
    )
    entries = manifest["animation"]["frames"]
    labels = tuple(entry["direction"] for entry in entries)
    if labels not in (CARDINALS, ALL_DIRECTIONS):
        raise ValueError(f"unexpected gaze direction contract: {labels}")

    neutral = Image.open(render_dir / manifest["neutral"]["file"]).convert("RGBA")
    images = [Image.open(render_dir / entry["file"]).convert("RGBA") for entry in entries]
    if {neutral.size, *(image.size for image in images)} != {(1152, 1248)}:
        raise ValueError("gaze renders must use the 1152x1248 master canvas")

    hidden_rgb_pixels = sum(hidden_rgb_count(image) for image in [neutral, *images])
    bboxes = []
    for image in images:
        bbox = image.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError("gaze direction is fully transparent")
        bboxes.append(list(bbox))
    centers = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in bboxes]
    center_drift = max(math.dist(centers[0], center) for center in centers)
    baseline_drift = max(abs(bboxes[0][3] - box[3]) for box in bboxes)
    unique_frames = len({entry["sha256"] for entry in entries})

    normal_images = [normal_cell(image) for image in images]
    normal_neutral = normal_cell(neutral)
    columns = 4 if labels == CARDINALS else 6
    rows = math.ceil((len(images) + 1) / columns)
    panel = (300, 346)
    sheet = Image.new("RGB", (panel[0] * columns, panel[1] * rows), BACKGROUND[:3])
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    review_items = [
        ("neutral", neutral),
        *[(entry["direction"], image) for entry, image in zip(entries, images, strict=True)],
    ]
    for index, (label, image) in enumerate(review_items):
        preview = compose(image)
        preview.thumbnail((panel[0], panel[1] - 30), Image.Resampling.LANCZOS)
        cell_x = (index % columns) * panel[0]
        cell_y = (index // columns) * panel[1]
        sheet.paste(preview, (cell_x + (panel[0] - preview.width) // 2, cell_y))
        expected = "neutral" if label == "neutral" else entries[index - 1]["expected"]
        draw.text(
            (cell_x + 10, cell_y + panel[1] - 22), f"{label} · {expected}", fill="white", font=font
        )
    sheet_path = render_dir / "gaze-directions.png"
    sheet.save(sheet_path, optimize=True)

    preview_frames = []
    for image in normal_images:
        frame = Image.new("RGBA", CELL, BACKGROUND)
        frame.alpha_composite(image)
        preview_frames.append(frame.convert("RGB"))
    preview_frames[0].save(
        render_dir / "gaze-preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=manifest["animation"]["frame_duration_ms"],
        loop=0,
        optimize=False,
        disposal=2,
    )

    continuity = []
    if labels == ALL_DIRECTIONS:
        for index, label in enumerate(labels):
            next_index = (index + 1) % len(labels)
            difference = ImageChops.difference(normal_images[index], normal_images[next_index])
            continuity.append(
                {
                    "from": label,
                    "to": labels[next_index],
                    "different_pixels": sum(
                        1 for alpha in difference.getchannel("A").getdata() if alpha > 0
                    ),
                }
            )

        atlas = Image.new("RGBA", ATLAS, (0, 0, 0, 0))
        atlas.alpha_composite(normal_neutral, (6 * CELL[0], 0))
        for index, image in enumerate(normal_images):
            column = index % 8
            row = 9 + index // 8
            atlas.alpha_composite(image, (column * CELL[0], row * CELL[1]))
        atlas.save(render_dir / "gaze-atlas-qa.webp", format="WEBP", lossless=True, method=6)

    qa = {
        "ok": (
            hidden_rgb_pixels == 0
            and baseline_drift <= 2
            and center_drift <= 18.0
            and unique_frames == len(entries)
        ),
        "directions": list(labels),
        "expected": [entry["expected"] for entry in entries],
        "dimensions": [1152, 1248],
        "normal_cell_dimensions": list(CELL),
        "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
        "maximum_center_drift_px": round(center_drift, 2),
        "maximum_baseline_drift_px": baseline_drift,
        "unique_frame_hashes": unique_frames,
        "alpha_bboxes": bboxes,
        "continuity": continuity,
        "artifacts": {
            "sheet": sheet_path.name,
            "preview": "gaze-preview.gif",
            "qa_atlas": "gaze-atlas-qa.webp" if labels == ALL_DIRECTIONS else None,
        },
    }
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not qa["ok"]:
        raise SystemExit("gaze QA failed")
    print(f"LEO_GAZE_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

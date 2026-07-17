"""Validate and compose review artifacts for Leo's locomotion candidates."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED = {
    "walk-right": (12, 125),
    "walk-left": (12, 125),
    "run-right": (12, 85),
    "run-left": (12, 85),
}
MASTER_SIZE = (1152, 1248)
NORMAL_SIZE = (192, 208)
BACKGROUND = (27, 30, 36, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument(
        "--animations",
        default=",".join(EXPECTED),
        help="comma-separated animation names",
    )
    return parser.parse_args()


def compose(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, BACKGROUND)
    background.alpha_composite(image)
    return background.convert("RGB")


def contact_sheet(images: list[Image.Image], name: str, destination: Path) -> None:
    columns = 6
    panel = (240, 276)
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (panel[0] * columns, panel[1] * rows), BACKGROUND[:3])
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, image in enumerate(images):
        preview = image.resize(NORMAL_SIZE, Image.Resampling.LANCZOS)
        preview = compose(preview)
        cell_x = (index % columns) * panel[0]
        cell_y = (index // columns) * panel[1]
        sheet.paste(preview, (cell_x + 24, cell_y + 18))
        draw.text((cell_x + 12, cell_y + 242), f"{name} · {index:02d}", fill="white", font=font)
    sheet.save(destination, optimize=True)


def preview_gif(images: list[Image.Image], duration: int, destination: Path) -> None:
    previews = [compose(image.resize(NORMAL_SIZE, Image.Resampling.LANCZOS)) for image in images]
    previews[0].save(
        destination,
        save_all=True,
        append_images=previews[1:],
        duration=duration,
        loop=0,
        optimize=False,
        disposal=2,
    )


def background_qa(images: list[tuple[str, Image.Image]], destination: Path) -> None:
    panel = (240, 244)
    backgrounds: list[tuple[str, Image.Image]] = [
        ("light", Image.new("RGBA", NORMAL_SIZE, (244, 241, 233, 255))),
        ("dark", Image.new("RGBA", NORMAL_SIZE, (25, 28, 34, 255))),
        ("saturated", Image.new("RGBA", NORMAL_SIZE, (24, 104, 112, 255))),
    ]
    busy = Image.new("RGBA", NORMAL_SIZE, (48, 51, 64, 255))
    draw = ImageDraw.Draw(busy)
    for offset in range(-NORMAL_SIZE[1], NORMAL_SIZE[0], 18):
        draw.line(
            (offset, 0, offset + NORMAL_SIZE[1], NORMAL_SIZE[1]), fill=(91, 63, 126, 255), width=5
        )
    for y in range(12, NORMAL_SIZE[1], 32):
        draw.rectangle((8, y, 66, y + 8), fill=(214, 171, 66, 255))
    backgrounds.append(("busy", busy))

    font = ImageFont.load_default()
    sheet = Image.new(
        "RGB",
        (panel[0] * len(images), panel[1] * len(backgrounds)),
        BACKGROUND[:3],
    )
    sheet_draw = ImageDraw.Draw(sheet)
    for row, (background_name, background) in enumerate(backgrounds):
        for column, (frame_name, image) in enumerate(images):
            preview = image.resize(NORMAL_SIZE, Image.Resampling.LANCZOS)
            composite = background.copy()
            composite.alpha_composite(preview)
            x = column * panel[0] + 24
            y = row * panel[1] + 18
            sheet.paste(composite.convert("RGB"), (x, y))
            sheet_draw.text(
                (column * panel[0] + 10, row * panel[1] + 226),
                f"{background_name} · {frame_name}",
                fill="white",
                font=font,
            )
    sheet.save(destination, optimize=True)


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (render_dir / "manifest.json").read_text(encoding="utf-8")
    )
    animations = manifest["animations"]
    names = [animation["name"] for animation in animations]
    selected_names = args.animations.split(",")
    if names != selected_names or any(name not in EXPECTED for name in names):
        raise ValueError(f"unexpected locomotion order: {names}")

    qa_animations: dict[str, Any] = {}
    review_frames: list[tuple[str, Image.Image]] = []
    overall_ok = True
    for animation in animations:
        name = animation["name"]
        expected_count, expected_duration = EXPECTED[name]
        if (
            len(animation["frames"]) != expected_count
            or animation["frame_duration_ms"] != expected_duration
            or animation["loop"] is not True
        ):
            raise ValueError(f"unexpected {name} timing contract")
        images = [
            Image.open(render_dir / frame["file"]).convert("RGBA") for frame in animation["frames"]
        ]
        if {image.size for image in images} != {MASTER_SIZE}:
            raise ValueError(f"unexpected {name} dimensions")

        alpha_bboxes: list[list[int]] = []
        hidden_rgb_pixels = 0
        for image in images:
            bbox = image.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"{name} contains an empty frame")
            alpha_bboxes.append(list(bbox))
            pixels = image.tobytes()
            hidden_rgb_pixels += sum(
                1
                for index in range(0, len(pixels), 4)
                if pixels[index + 3] == 0 and any(pixels[index : index + 3])
            )

        centers = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in alpha_bboxes]
        center_drift = max(math.dist(centers[0], center) for center in centers)
        baselines = [box[3] for box in alpha_bboxes]
        baseline_drift = max(baselines) - min(baselines)
        safety_edge = any(
            box[0] <= 8 or box[1] <= 8 or box[2] >= 1144 or box[3] >= 1240 for box in alpha_bboxes
        )
        unique_frames = len({frame["sha256"] for frame in animation["frames"]})
        is_run = name.startswith("run")
        airborne_frames = sum(max(baselines) - baseline >= 35 for baseline in baselines)
        animation_ok = (
            hidden_rgb_pixels == 0
            and not safety_edge
            and center_drift <= (125 if is_run else 24)
            and baseline_drift <= (125 if is_run else 12)
            and unique_frames == expected_count
            and (not is_run or airborne_frames >= 3)
        )
        overall_ok &= animation_ok

        sheet_name = f"{name}-contact-sheet.png"
        preview_name = f"{name}-preview.gif"
        contact_sheet(images, name, render_dir / sheet_name)
        preview_gif(images, expected_duration, render_dir / preview_name)
        review_index = 4 if name.startswith("run") else 0
        review_frames.append((f"{name}-{review_index:02d}", images[review_index]))
        qa_animations[name] = {
            "ok": animation_ok,
            "frame_count": expected_count,
            "frame_duration_ms": expected_duration,
            "loop": True,
            "dimensions": list(MASTER_SIZE),
            "normal_cell_dimensions": list(NORMAL_SIZE),
            "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
            "touches_safety_edge": safety_edge,
            "maximum_center_drift_px": round(center_drift, 2),
            "maximum_baseline_drift_px": baseline_drift,
            "unique_frame_hashes": unique_frames,
            "airborne_frames": airborne_frames,
            "alpha_bboxes": alpha_bboxes,
            "artifacts": {"contact_sheet": sheet_name, "preview": preview_name},
        }

    background_name = "locomotion-background-qa.png"
    background_qa(review_frames, render_dir / background_name)
    qa = {
        "ok": overall_ok,
        "animations": qa_animations,
        "artifacts": {"background_qa": background_name},
    }
    destination = render_dir / "qa.json"
    destination.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not overall_ok:
        raise SystemExit("locomotion QA failed")
    print(f"LEO_LOCOMOTION_QA={destination}")


if __name__ == "__main__":
    main()

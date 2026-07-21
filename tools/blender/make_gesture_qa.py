"""Validate and compose review artifacts for Leo's Wave and Jump candidates."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED = {
    "wave": (10, 150),
    "jump": (12, 110),
}
MASTER_SIZE = (1152, 1248)
NORMAL_SIZE = (192, 208)
BACKGROUND = (27, 30, 36, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def compose(image: Image.Image, color: tuple[int, int, int, int] = BACKGROUND) -> Image.Image:
    background = Image.new("RGBA", image.size, color)
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
        preview = compose(image.resize(NORMAL_SIZE, Image.Resampling.LANCZOS))
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
        loop=1,
        optimize=False,
        disposal=2,
    )


def background_qa(images: list[tuple[str, Image.Image]], destination: Path) -> None:
    backgrounds = (
        ("light", (244, 241, 233, 255)),
        ("dark", (25, 28, 34, 255)),
        ("saturated", (99, 47, 137, 255)),
    )
    panel = (240, 244)
    sheet = Image.new("RGB", (panel[0] * len(images), panel[1] * len(backgrounds)), BACKGROUND[:3])
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for row, (background_name, color) in enumerate(backgrounds):
        for column, (frame_name, image) in enumerate(images):
            preview = compose(image.resize(NORMAL_SIZE, Image.Resampling.LANCZOS), color)
            x = column * panel[0] + 24
            y = row * panel[1] + 18
            sheet.paste(preview, (x, y))
            draw.text(
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
    if [animation["name"] for animation in animations] != list(EXPECTED):
        raise ValueError("unexpected gesture order")

    qa_animations: dict[str, Any] = {}
    review_frames: list[tuple[str, Image.Image]] = []
    overall_ok = True
    for animation in animations:
        name = animation["name"]
        expected_count, expected_duration = EXPECTED[name]
        if (
            len(animation["frames"]) != expected_count
            or animation["frame_duration_ms"] != expected_duration
            or animation["loop"] is not False
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
        endpoint_match = animation["frames"][0]["sha256"] == animation["frames"][-1]["sha256"]
        airborne_frames = (
            sum(max(baselines) - baseline >= 35 for baseline in baselines) if name == "jump" else 0
        )
        animation_ok = (
            hidden_rgb_pixels == 0
            and not safety_edge
            and endpoint_match
            and unique_frames >= expected_count - 2
            and center_drift <= (145 if name == "jump" else 70)
            and baseline_drift <= (145 if name == "jump" else 4)
            and (name != "jump" or airborne_frames >= 4)
        )
        overall_ok &= animation_ok

        sheet_name = f"{name}-contact-sheet.png"
        preview_name = f"{name}-preview.gif"
        contact_sheet(images, name, render_dir / sheet_name)
        preview_gif(images, expected_duration, render_dir / preview_name)
        review_index = 5 if name == "jump" else 4
        review_frames.append((f"{name}-{review_index:02d}", images[review_index]))
        qa_animations[name] = {
            "ok": animation_ok,
            "frame_count": expected_count,
            "frame_duration_ms": expected_duration,
            "loop": False,
            "dimensions": list(MASTER_SIZE),
            "normal_cell_dimensions": list(NORMAL_SIZE),
            "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
            "touches_safety_edge": safety_edge,
            "maximum_center_drift_px": round(center_drift, 2),
            "maximum_baseline_drift_px": baseline_drift,
            "unique_frame_hashes": unique_frames,
            "endpoint_sha256_match": endpoint_match,
            "airborne_frames": airborne_frames,
            "alpha_bboxes": alpha_bboxes,
            "artifacts": {"contact_sheet": sheet_name, "preview": preview_name},
        }

    background_name = "gesture-background-qa.png"
    background_qa(review_frames, render_dir / background_name)
    qa = {
        "ok": overall_ok,
        "animations": qa_animations,
        "artifacts": {"background_qa": background_name},
    }
    destination = render_dir / "qa.json"
    destination.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not overall_ok:
        raise SystemExit("gesture QA failed")
    print(f"LEO_GESTURE_QA={destination}")


if __name__ == "__main__":
    main()

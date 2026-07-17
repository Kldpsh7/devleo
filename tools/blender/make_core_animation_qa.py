"""Validate and compose review artifacts for Leo's core animation candidates."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED = {
    "waiting": (12, 210, True),
    "working": (16, 145, True),
    "review": (12, 210, True),
    "failure": (14, 140, False),
}
BACKGROUND = (27, 30, 36, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def compose(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, BACKGROUND)
    background.alpha_composite(image)
    return background.convert("RGB")


def contact_sheet(images: list[Image.Image], name: str, destination: Path) -> None:
    columns = 6
    panel = (252, 292)
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (panel[0] * columns, panel[1] * rows), BACKGROUND[:3])
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, image in enumerate(images):
        preview = compose(image)
        preview.thumbnail((panel[0], panel[1] - 28), Image.Resampling.LANCZOS)
        cell_x = (index % columns) * panel[0]
        cell_y = (index // columns) * panel[1]
        x = cell_x + (panel[0] - preview.width) // 2
        sheet.paste(preview, (x, cell_y))
        draw.text(
            (cell_x + 10, cell_y + panel[1] - 21), f"{name} · {index:02d}", fill="white", font=font
        )
    sheet.save(destination, optimize=True)


def preview_gif(images: list[Image.Image], duration: int, loop: bool, destination: Path) -> None:
    previews = []
    for image in images:
        preview = compose(image)
        preview.thumbnail((300, 325), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (300, 325), BACKGROUND[:3])
        canvas.paste(preview, ((300 - preview.width) // 2, (325 - preview.height) // 2))
        previews.append(canvas)
    previews[0].save(
        destination,
        save_all=True,
        append_images=previews[1:],
        duration=duration,
        loop=0 if loop else 1,
        optimize=False,
        disposal=2,
    )


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (render_dir / "manifest.json").read_text(encoding="utf-8")
    )
    animations = manifest["animations"]
    names = [animation["name"] for animation in animations]
    if names != list(EXPECTED):
        raise ValueError(f"unexpected animation order: {names}")

    qa_animations: dict[str, Any] = {}
    overall_ok = True
    for animation in animations:
        name = animation["name"]
        expected_count, expected_duration, expected_loop = EXPECTED[name]
        if (
            (animation["frames"] and len(animation["frames"]) != expected_count)
            or animation["frame_duration_ms"] != expected_duration
            or animation["loop"] != expected_loop
        ):
            raise ValueError(f"unexpected {name} timing contract")
        images = [
            Image.open(render_dir / frame["file"]).convert("RGBA") for frame in animation["frames"]
        ]
        sizes = {image.size for image in images}
        if sizes != {(1152, 1248)}:
            raise ValueError(f"unexpected {name} dimensions: {sizes}")

        alpha_bboxes: list[list[int]] = []
        hidden_rgb_pixels = 0
        for image in images:
            bbox = image.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"{name} contains a fully transparent frame")
            alpha_bboxes.append(list(bbox))
            pixels = image.tobytes()
            hidden_rgb_pixels += sum(
                1
                for index in range(0, len(pixels), 4)
                if pixels[index + 3] == 0 and any(pixels[index : index + 3])
            )

        centers = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in alpha_bboxes]
        center_drift = max(math.dist(centers[0], center) for center in centers)
        baseline_drift = max(abs(alpha_bboxes[0][3] - box[3]) for box in alpha_bboxes)
        safety_edge = any(
            box[0] <= 8 or box[1] <= 8 or box[2] >= 1144 or box[3] >= 1240 for box in alpha_bboxes
        )
        unique_frames = len({frame["sha256"] for frame in animation["frames"]})
        drift_limit = 36.0 if animation["loop"] else 180.0
        animation_ok = (
            hidden_rgb_pixels == 0
            and not safety_edge
            and baseline_drift <= 4
            and center_drift <= drift_limit
            and unique_frames >= expected_count // 2
        )
        overall_ok &= animation_ok

        sheet_name = f"{name}-contact-sheet.png"
        preview_name = f"{name}-preview.gif"
        contact_sheet(images, name, render_dir / sheet_name)
        preview_gif(images, expected_duration, expected_loop, render_dir / preview_name)
        qa_animations[name] = {
            "ok": animation_ok,
            "frame_count": expected_count,
            "frame_duration_ms": expected_duration,
            "loop": expected_loop,
            "dimensions": [1152, 1248],
            "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
            "touches_safety_edge": safety_edge,
            "maximum_center_drift_px": round(center_drift, 2),
            "maximum_baseline_drift_px": baseline_drift,
            "unique_frame_hashes": unique_frames,
            "alpha_bboxes": alpha_bboxes,
            "artifacts": {"contact_sheet": sheet_name, "preview": preview_name},
        }

    qa = {"ok": overall_ok, "animations": qa_animations}
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not overall_ok:
        raise SystemExit("core animation QA failed")
    print(f"LEO_CORE_ANIMATION_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

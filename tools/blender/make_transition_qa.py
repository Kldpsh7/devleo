"""Validate and compose review artifacts for Leo's locomotion transitions."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED = {
    "idle-to-walk-right": (20, 70),
    "walk-right-to-idle": (20, 70),
    "idle-to-walk-left": (20, 70),
    "walk-left-to-idle": (20, 70),
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
        ("saturated", (24, 104, 112, 255)),
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
        raise ValueError("unexpected transition order")

    frames_by_name: dict[str, list[dict[str, Any]]] = {}
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
        frames_by_name[name] = animation["frames"]
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
        adjacent_center_steps = [
            math.dist(start, end) for start, end in zip(centers, centers[1:], strict=False)
        ]
        baselines = [box[3] for box in alpha_bboxes]
        adjacent_baseline_steps = [
            abs(start - end) for start, end in zip(baselines, baselines[1:], strict=False)
        ]
        areas = [(box[2] - box[0]) * (box[3] - box[1]) for box in alpha_bboxes]
        adjacent_area_ratios = [
            max(start, end) / min(start, end)
            for start, end in zip(areas, areas[1:], strict=False)
        ]
        safety_edge = any(
            box[0] <= 8 or box[1] <= 8 or box[2] >= 1144 or box[3] >= 1240 for box in alpha_bboxes
        )
        unique_frames = len({frame["sha256"] for frame in animation["frames"]})
        maximum_center_step = max(adjacent_center_steps)
        maximum_baseline_step = max(adjacent_baseline_steps)
        maximum_area_ratio = max(adjacent_area_ratios)
        animation_ok = (
            hidden_rgb_pixels == 0
            and not safety_edge
            and unique_frames == expected_count
            and maximum_center_step <= 50
            and maximum_baseline_step == 0
            and maximum_area_ratio <= 1.24
        )
        overall_ok &= animation_ok

        sheet_name = f"{name}-contact-sheet.png"
        preview_name = f"{name}-preview.gif"
        contact_sheet(images, name, render_dir / sheet_name)
        preview_gif(images, expected_duration, render_dir / preview_name)
        if name.startswith("idle-to"):
            review_frames.extend(
                ((f"{name}-09", images[9]), (f"{name}-19", images[-1]))
            )
        qa_animations[name] = {
            "ok": animation_ok,
            "frame_count": expected_count,
            "frame_duration_ms": expected_duration,
            "loop": False,
            "dimensions": list(MASTER_SIZE),
            "normal_cell_dimensions": list(NORMAL_SIZE),
            "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
            "touches_safety_edge": safety_edge,
            "unique_frame_hashes": unique_frames,
            "maximum_adjacent_center_step_px": round(maximum_center_step, 2),
            "maximum_adjacent_baseline_step_px": maximum_baseline_step,
            "maximum_adjacent_bbox_area_ratio": round(maximum_area_ratio, 4),
            "alpha_bboxes": alpha_bboxes,
            "artifacts": {"contact_sheet": sheet_name, "preview": preview_name},
        }

    exact_reverse_pairs: dict[str, bool] = {}
    for direction in ("right", "left"):
        forward = frames_by_name[f"idle-to-walk-{direction}"]
        reverse = frames_by_name[f"walk-{direction}-to-idle"]
        exact_reverse_pairs[direction] = [frame["sha256"] for frame in forward] == [
            frame["sha256"] for frame in reversed(reverse)
        ]
    shared_idle_endpoint = (
        frames_by_name["idle-to-walk-right"][0]["sha256"]
        == frames_by_name["idle-to-walk-left"][0]["sha256"]
    )
    overall_ok &= all(exact_reverse_pairs.values()) and shared_idle_endpoint

    background_name = "transition-background-qa.png"
    background_qa(review_frames, render_dir / background_name)
    qa = {
        "ok": overall_ok,
        "animations": qa_animations,
        "exact_reverse_pairs": exact_reverse_pairs,
        "shared_idle_endpoint": shared_idle_endpoint,
        "artifacts": {"background_qa": background_name},
    }
    destination = render_dir / "qa.json"
    destination.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not overall_ok:
        raise SystemExit("transition QA failed")
    print(f"LEO_TRANSITION_QA={destination}")


if __name__ == "__main__":
    main()

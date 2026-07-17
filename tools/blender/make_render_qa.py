"""Validate Blender prototype frames and produce human-review artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("render is fully transparent")
    return bbox


def composite(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (*background, 255))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    return copy


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest_path = render_dir / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    scene_validation = manifest.get("scene_validation", {})
    if not scene_validation.get("ok"):
        raise ValueError(f"source scene validation failed: {scene_validation}")
    frame_paths = [render_dir / frame["file"] for frame in manifest["animation"]["frames"]]
    frames = [Image.open(path).convert("RGBA") for path in frame_paths]
    if len(frames) != 12:
        raise ValueError(f"expected 12 Idle frames, found {len(frames)}")
    sizes = {frame.size for frame in frames}
    if len(sizes) != 1:
        raise ValueError(f"inconsistent frame dimensions: {sorted(sizes)}")
    width, height = frames[0].size
    if width < 1024 or height < 1024:
        raise ValueError(
            f"master frames must be at least 1024 px per dimension, got {width}x{height}"
        )

    bboxes = [alpha_bbox(frame) for frame in frames]
    corner_alpha = []
    hidden_rgb_pixels = 0
    for frame in frames:
        alpha = frame.getchannel("A")
        corner_alpha.append(
            max(
                alpha.getpixel(point)
                for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
            )
        )
        pixels = frame.tobytes()
        hidden_rgb_pixels += sum(
            1
            for index in range(0, len(pixels), 4)
            if pixels[index + 3] == 0 and any(pixels[index : index + 3])
        )
    centers = [((left + right) / 2, (top + bottom) / 2) for left, top, right, bottom in bboxes]
    center_x_values = [center[0] for center in centers]
    center_y_values = [center[1] for center in centers]
    max_center_drift = max(
        max(center_x_values) - min(center_x_values), max(center_y_values) - min(center_y_values)
    )
    touches_edge = any(
        left <= 2 or top <= 2 or right >= width - 2 or bottom >= height - 2
        for left, top, right, bottom in bboxes
    )

    tile_size = (288, 312)
    label_height = 28
    contact = Image.new("RGB", (tile_size[0] * 4, (tile_size[1] + label_height) * 3), (30, 33, 39))
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    for index, frame in enumerate(frames):
        row, column = divmod(index, 4)
        x = column * tile_size[0]
        y = row * (tile_size[1] + label_height)
        preview = fit(composite(frame, (30, 33, 39)), tile_size)
        paste_x = x + (tile_size[0] - preview.width) // 2
        paste_y = y + (tile_size[1] - preview.height) // 2
        contact.paste(preview, (paste_x, paste_y))
        draw.text(
            (x + 10, y + tile_size[1] + 7), f"Idle {index:02d}", fill=(238, 238, 238), font=font
        )
    contact.save(render_dir / "contact-sheet.png", optimize=True)

    neutral = Image.open(render_dir / manifest["neutral"]["file"]).convert("RGBA")
    backgrounds = [
        ("white", (248, 248, 248)),
        ("black", (7, 8, 10)),
        ("gray", (105, 109, 116)),
        ("blue", (20, 73, 118)),
    ]
    bg_qa = Image.new("RGB", (320 * len(backgrounds), 374), (25, 25, 25))
    bg_draw = ImageDraw.Draw(bg_qa)
    for index, (label, color) in enumerate(backgrounds):
        preview = fit(composite(neutral, color), (320, 346))
        x = index * 320 + (320 - preview.width) // 2
        bg_qa.paste(preview, (x, 0))
        bg_draw.text((index * 320 + 10, 354), label, fill=(240, 240, 240), font=font)
    bg_qa.save(render_dir / "background-qa.png", optimize=True)

    identity_views = [
        (view["name"], Image.open(render_dir / view["file"]).convert("RGBA"))
        for view in manifest.get("identity_views", [])
    ]
    if len(identity_views) != 3:
        raise ValueError(f"expected three identity views, found {len(identity_views)}")
    identity_panel = (384, 444)
    identity_qa = Image.new(
        "RGB",
        (identity_panel[0] * len(identity_views), identity_panel[1]),
        (27, 30, 36),
    )
    identity_draw = ImageDraw.Draw(identity_qa)
    for index, (name, view) in enumerate(identity_views):
        preview = fit(composite(view, (27, 30, 36)), (identity_panel[0], identity_panel[1] - 30))
        x = index * identity_panel[0] + (identity_panel[0] - preview.width) // 2
        identity_qa.paste(preview, (x, 0))
        identity_draw.text(
            (index * identity_panel[0] + 12, identity_panel[1] - 22),
            name,
            fill=(240, 240, 240),
            font=font,
        )
    identity_qa.save(render_dir / "identity-turnaround.png", optimize=True)

    display_scales = (0.55, 0.75, 1.0, 1.25)
    scale_backgrounds = (("light", (242, 242, 240)), ("dark", (25, 28, 34)))
    panel_width = 300
    panel_height = 310
    scale_qa = Image.new(
        "RGB",
        (panel_width * len(display_scales), panel_height * len(scale_backgrounds)),
        (28, 30, 35),
    )
    scale_draw = ImageDraw.Draw(scale_qa)
    for row, (background_name, background_color) in enumerate(scale_backgrounds):
        for column, scale in enumerate(display_scales):
            target_size = (round(192 * scale), round(208 * scale))
            sprite = neutral.resize(target_size, Image.Resampling.LANCZOS)
            panel = Image.new("RGBA", (panel_width, panel_height), (*background_color, 255))
            panel.alpha_composite(
                sprite,
                ((panel_width - sprite.width) // 2, panel_height - sprite.height - 32),
            )
            x = column * panel_width
            y = row * panel_height
            scale_qa.paste(panel.convert("RGB"), (x, y))
            label_color = (20, 20, 20) if background_name == "light" else (240, 240, 240)
            scale_draw.text(
                (x + 10, y + 9),
                f"{scale:.2f}x · {target_size[0]}×{target_size[1]} · {background_name}",
                fill=label_color,
                font=font,
            )
    scale_qa.save(render_dir / "scale-qa.png", optimize=True)

    gif_frames = [fit(composite(frame, (26, 29, 35)), (384, 416)) for frame in frames]
    gif_frames[0].save(
        render_dir / "idle-preview.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=manifest["animation"]["frame_duration_ms"],
        loop=0,
        disposal=2,
        optimize=False,
    )

    qa = {
        "ok": max(corner_alpha) == 0 and not touches_edge and hidden_rgb_pixels == 0,
        "frame_count": len(frames),
        "dimensions": [width, height],
        "mode": "RGBA",
        "maximum_corner_alpha": max(corner_alpha),
        "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
        "touches_safety_edge": touches_edge,
        "maximum_center_drift_px": round(max_center_drift, 3),
        "alpha_bboxes": [list(bbox) for bbox in bboxes],
        "scene_validation": scene_validation,
        "artifacts": {
            "contact_sheet": "contact-sheet.png",
            "background_qa": "background-qa.png",
            "identity_turnaround": "identity-turnaround.png",
            "scale_qa": "scale-qa.png",
            "preview": "idle-preview.gif",
        },
    }
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not qa["ok"]:
        raise SystemExit("render QA failed; inspect qa.json")
    print(f"LEO_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

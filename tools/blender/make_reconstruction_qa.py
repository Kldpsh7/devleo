"""Validate reconstructed-mesh previews and build a turntable contact sheet."""

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


def composite(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (*background, 255))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (render_dir / "manifest.json").read_text(encoding="utf-8")
    )
    paths = [render_dir / view["file"] for view in manifest["views"]]
    frames = [Image.open(path).convert("RGBA") for path in paths]
    if len(frames) != 8:
        raise ValueError(f"expected eight turntable views, found {len(frames)}")
    sizes = {frame.size for frame in frames}
    if len(sizes) != 1:
        raise ValueError(f"inconsistent render dimensions: {sorted(sizes)}")

    bboxes = [frame.getchannel("A").getbbox() for frame in frames]
    if any(bbox is None for bbox in bboxes):
        raise ValueError("a turntable view is fully transparent")
    width, height = frames[0].size
    edge_failures = [
        index
        for index, bbox in enumerate(bboxes)
        if bbox is not None
        and (bbox[0] <= 2 or bbox[1] <= 2 or bbox[2] >= width - 2 or bbox[3] >= height - 2)
    ]
    corner_alpha = [
        max(
            frame.getchannel("A").getpixel(point)
            for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
        )
        for frame in frames
    ]

    panel = (384, 416)
    label_height = 24
    background = (27, 30, 36)
    contact = Image.new("RGB", (panel[0] * 4, (panel[1] + label_height) * 2), background)
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    for index, (view, frame) in enumerate(zip(manifest["views"], frames, strict=True)):
        row, column = divmod(index, 4)
        x = column * panel[0]
        y = row * (panel[1] + label_height)
        preview = fit(composite(frame, background), panel)
        contact.paste(
            preview,
            (x + (panel[0] - preview.width) // 2, y + (panel[1] - preview.height) // 2),
        )
        draw.text(
            (x + 10, y + panel[1] + 6),
            f"yaw {view['yaw']:03d}",
            fill=(240, 240, 240),
            font=font,
        )
    contact.save(render_dir / "turntable-contact-sheet.png", optimize=True)

    qa = {
        "ok": not edge_failures and max(corner_alpha) == 0,
        "view_count": len(frames),
        "dimensions": [width, height],
        "maximum_corner_alpha": max(corner_alpha),
        "edge_failures": edge_failures,
        "alpha_bboxes": [list(bbox) for bbox in bboxes if bbox is not None],
        "artifacts": {"turntable_contact_sheet": "turntable-contact-sheet.png"},
    }
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not qa["ok"]:
        raise SystemExit("reconstructed-mesh render QA failed; inspect qa.json")
    print(f"LEO_RECONSTRUCTION_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

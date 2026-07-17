"""Validate and compose Leo's canonical state-pose review sheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED_STATES = ("idle", "waiting", "working", "review", "failure")
EXPECTED_LID_ANGLES = (0.0, 48.0, 96.0, 96.0, 0.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        (render_dir / "manifest.json").read_text(encoding="utf-8")
    )
    entries = manifest["animation"]["frames"]
    states = tuple(entry["state"] for entry in entries)
    lid_angles = tuple(entry["lid_degrees"] for entry in entries)
    if states != EXPECTED_STATES:
        raise ValueError(f"unexpected state order: {states}")
    if lid_angles != EXPECTED_LID_ANGLES:
        raise ValueError(f"unexpected laptop angles: {lid_angles}")

    images = [Image.open(render_dir / entry["file"]).convert("RGBA") for entry in entries]
    sizes = {image.size for image in images}
    if len(sizes) != 1:
        raise ValueError(f"state render dimensions differ: {sizes}")
    width, height = images[0].size
    alpha_bboxes = []
    hidden_rgb_pixels = 0
    for image in images:
        bbox = image.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError("state pose is fully transparent")
        alpha_bboxes.append(list(bbox))
        pixels = image.tobytes()
        hidden_rgb_pixels += sum(
            1
            for index in range(0, len(pixels), 4)
            if pixels[index + 3] == 0 and any(pixels[index : index + 3])
        )

    panel = (300, 338)
    sheet = Image.new("RGB", (panel[0] * len(images), panel[1]), (27, 30, 36))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (entry, image) in enumerate(zip(entries, images, strict=True)):
        background = Image.new("RGBA", image.size, (27, 30, 36, 255))
        background.alpha_composite(image)
        preview = background.convert("RGB")
        preview.thumbnail((panel[0], panel[1] - 28), Image.Resampling.LANCZOS)
        x = index * panel[0] + (panel[0] - preview.width) // 2
        sheet.paste(preview, (x, 0))
        draw.text(
            (index * panel[0] + 10, panel[1] - 21),
            f"{entry['state']} · lid {entry['lid_degrees']:.0f}°",
            fill=(242, 242, 242),
            font=font,
        )
    sheet.save(render_dir / "state-poses.png", optimize=True)

    qa = {
        "ok": hidden_rgb_pixels == 0,
        "states": list(states),
        "laptop_lid_degrees": list(lid_angles),
        "dimensions": [width, height],
        "hidden_rgb_pixels_under_zero_alpha": hidden_rgb_pixels,
        "alpha_bboxes": alpha_bboxes,
        "artifact": "state-poses.png",
    }
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if not qa["ok"]:
        raise SystemExit("state-pose QA failed")
    print(f"LEO_STATE_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

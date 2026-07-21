"""Validate and compose realistic Leo's quadruped deformation smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--rig-report", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def composite(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (*background, 255))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def main() -> None:
    args = parse_args()
    render_dir = args.render_dir.expanduser().resolve()
    rig_report = read_json(args.rig_report.expanduser().resolve())
    manifest = read_json(render_dir / "manifest.json")
    frames = [
        Image.open(render_dir / frame["file"]).convert("RGBA") for frame in manifest["frames"]
    ]
    if len(frames) != 12:
        raise ValueError(f"expected twelve deformation frames, found {len(frames)}")
    sizes = {frame.size for frame in frames}
    if len(sizes) != 1:
        raise ValueError(f"inconsistent render dimensions: {sorted(sizes)}")
    width, height = frames[0].size
    bboxes = [frame.getchannel("A").getbbox() for frame in frames]
    if any(bbox is None for bbox in bboxes):
        raise ValueError("a deformation frame is fully transparent")
    alpha_areas = [sum(frame.getchannel("A").histogram()[1:]) for frame in frames]
    neutral_by_view = {
        frame["view"]: alpha_areas[index]
        for index, frame in enumerate(manifest["frames"])
        if frame["pose"] == "neutral"
    }
    area_ratios = [
        alpha_areas[index] / neutral_by_view[frame["view"]]
        for index, frame in enumerate(manifest["frames"])
    ]
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
    label_height = 28
    background = (27, 30, 36)
    contact = Image.new("RGB", (panel[0] * 4, (panel[1] + label_height) * 3), background)
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    for index, (frame_info, frame) in enumerate(zip(manifest["frames"], frames, strict=True)):
        row, column = divmod(index, 4)
        x = column * panel[0]
        y = row * (panel[1] + label_height)
        preview = composite(frame, background)
        preview.thumbnail(panel, Image.Resampling.LANCZOS)
        contact.paste(
            preview,
            (x + (panel[0] - preview.width) // 2, y + (panel[1] - preview.height) // 2),
        )
        draw.text(
            (x + 10, y + panel[1] + 7),
            f"{frame_info['pose']} / {frame_info['view']}",
            fill=(240, 240, 240),
            font=font,
        )
    contact.save(render_dir / "deformation-contact-sheet.png", optimize=True)

    errors: list[str] = []
    if not rig_report.get("ok"):
        errors.append("rig mechanical QA failed")
    if edge_failures:
        errors.append(f"frames touch the safety edge: {edge_failures}")
    if max(corner_alpha):
        errors.append(f"maximum corner alpha is {max(corner_alpha)}")
    ratio_failures = [index for index, ratio in enumerate(area_ratios) if not 0.78 <= ratio <= 1.22]
    if ratio_failures:
        errors.append(f"deformed alpha area is outside 0.78..1.22: {ratio_failures}")
    weights = rig_report["weights"]
    if weights["unweighted_vertices"]:
        errors.append("rig contains unweighted vertices")
    if weights["maximum_influences_per_vertex"] > 4:
        errors.append("rig exceeds four deform influences per vertex")

    qa = {
        "schema_version": 1,
        "ok": not errors,
        "runtime_replacement": False,
        "frame_count": len(frames),
        "pose_count": len(manifest["poses"]),
        "views": manifest["views"],
        "dimensions": [width, height],
        "maximum_corner_alpha": max(corner_alpha),
        "edge_failures": edge_failures,
        "alpha_bboxes": [list(bbox) for bbox in bboxes if bbox is not None],
        "alpha_area_ratios": [round(ratio, 6) for ratio in area_ratios],
        "rig_report": rig_report,
        "errors": errors,
        "artifacts": {"deformation_contact_sheet": "deformation-contact-sheet.png"},
    }
    (render_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(f"deformation QA failed: {errors}")
    print(f"LEO_REALISTIC_DEFORMATION_QA={render_dir / 'qa.json'}")


if __name__ == "__main__":
    main()

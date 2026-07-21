"""Compare clean-topology renders with the approved realistic identity render."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-render-dir", type=Path, required=True)
    parser.add_argument("--candidate-render-dir", type=Path, required=True)
    parser.add_argument("--topology-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-alpha-iou", type=float, default=0.99)
    parser.add_argument("--maximum-channel-mad", type=float, default=5.0)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def binary_alpha(image: Image.Image) -> Image.Image:
    return image.getchannel("A").point(lambda alpha: 255 if alpha else 0)


def white_pixel_count(image: Image.Image) -> int:
    return image.histogram()[255]


def compare_view(source_path: Path, candidate_path: Path) -> dict[str, Any]:
    with Image.open(source_path) as source_file, Image.open(candidate_path) as candidate_file:
        source = source_file.convert("RGBA")
        candidate = candidate_file.convert("RGBA")
    if source.size != candidate.size:
        raise ValueError(
            f"render dimensions differ for {source_path.name}: {source.size} != {candidate.size}"
        )
    source_alpha = binary_alpha(source)
    candidate_alpha = binary_alpha(candidate)
    intersection = ImageChops.darker(source_alpha, candidate_alpha)
    union = ImageChops.lighter(source_alpha, candidate_alpha)
    union_pixels = white_pixel_count(union)
    if union_pixels == 0:
        raise ValueError(f"both renders are transparent for {source_path.name}")
    alpha_iou = white_pixel_count(intersection) / union_pixels
    difference = ImageChops.difference(source.convert("RGB"), candidate.convert("RGB"))
    channel_mad = ImageStat.Stat(difference, union).mean
    return {
        "view": source_path.name,
        "alpha_iou": round(alpha_iou, 6),
        "rgb_channel_mean_absolute_difference": [round(value, 3) for value in channel_mad],
    }


def main() -> None:
    args = parse_args()
    source_dir = args.source_render_dir.expanduser().resolve()
    candidate_dir = args.candidate_render_dir.expanduser().resolve()
    topology_path = args.topology_report.expanduser().resolve()
    output = args.output.expanduser().resolve()

    topology = read_json(topology_path)
    source_render_qa = read_json(source_dir / "qa.json")
    candidate_render_qa = read_json(candidate_dir / "qa.json")
    source_manifest = read_json(source_dir / "manifest.json")
    candidate_manifest = read_json(candidate_dir / "manifest.json")
    source_views = [view["file"] for view in source_manifest["views"]]
    candidate_views = [view["file"] for view in candidate_manifest["views"]]
    if source_views != candidate_views:
        raise ValueError("source and candidate manifests do not contain the same views")

    views = [compare_view(source_dir / name, candidate_dir / name) for name in source_views]
    minimum_alpha_iou = min(view["alpha_iou"] for view in views)
    maximum_channel_mad = max(max(view["rgb_channel_mean_absolute_difference"]) for view in views)
    errors: list[str] = []
    if not topology.get("ok"):
        errors.append("mechanical topology report failed")
    if not source_render_qa.get("ok"):
        errors.append("approved-source render QA failed")
    if not candidate_render_qa.get("ok"):
        errors.append("candidate render QA failed")
    if minimum_alpha_iou < args.minimum_alpha_iou:
        errors.append(
            f"minimum alpha IoU {minimum_alpha_iou:.6f} is below {args.minimum_alpha_iou:.6f}"
        )
    if maximum_channel_mad > args.maximum_channel_mad:
        errors.append(
            f"maximum RGB channel MAD {maximum_channel_mad:.3f} exceeds "
            f"{args.maximum_channel_mad:.3f}"
        )

    report = {
        "schema_version": 1,
        "ok": not errors,
        "runtime_replacement": False,
        "mechanical_topology": topology,
        "render_qa": {
            "approved_source": source_render_qa,
            "candidate": candidate_render_qa,
        },
        "identity_preservation": {
            "minimum_alpha_iou_gate": args.minimum_alpha_iou,
            "maximum_channel_mad_gate": args.maximum_channel_mad,
            "minimum_alpha_iou": minimum_alpha_iou,
            "maximum_channel_mad": maximum_channel_mad,
            "views": views,
        },
        "errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(f"topology identity QA failed: {errors}")
    print(f"LEO_TOPOLOGY_QA={output}")


if __name__ == "__main__":
    main()

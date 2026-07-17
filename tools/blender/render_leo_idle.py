"""Render Leo's neutral frame and 12-frame Idle prototype from a .blend scene."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=64)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def disable_render_stamps(scene: bpy.types.Scene) -> None:
    scene.render.use_stamp = False
    for attribute in (
        "use_stamp_camera",
        "use_stamp_date",
        "use_stamp_filename",
        "use_stamp_frame",
        "use_stamp_hostname",
        "use_stamp_lens",
        "use_stamp_marker",
        "use_stamp_memory",
        "use_stamp_note",
        "use_stamp_render_time",
        "use_stamp_scene",
        "use_stamp_time",
    ):
        if hasattr(scene.render, attribute):
            setattr(scene.render, attribute, False)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    idle_dir = output_dir / "idle"
    idle_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    if scene.get("leo_pipeline_version") != 1:
        raise RuntimeError("The loaded file is not a supported Leo source scene")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    disable_render_stamps(scene)
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = args.samples

    scene.frame_set(scene.frame_start)
    neutral_path = output_dir / "neutral.png"
    scene.render.filepath = str(neutral_path)
    bpy.ops.render.render(write_still=True)

    frames: list[dict[str, object]] = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        path = idle_dir / f"{frame - scene.frame_start:02d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        frames.append(
            {
                "index": frame - scene.frame_start,
                "scene_frame": frame,
                "file": str(path.relative_to(output_dir)),
                "sha256": checksum(path),
                "bytes": path.stat().st_size,
            }
        )

    source_path = Path(bpy.data.filepath).resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        source_display = str(source_path.relative_to(repository_root))
    except ValueError:
        source_display = source_path.name
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "prototype-not-runtime-approved",
        "runtime_replacement": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "platform": platform.platform(),
            "source": source_display,
            "source_sha256": checksum(source_path),
            "script": "tools/blender/render_leo_idle.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
            "resolution_percentage": scene.render.resolution_percentage,
            "samples": args.samples,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
        },
        "animation": {
            "name": "idle",
            "fps": scene.render.fps,
            "frame_duration_ms": round(1000 / scene.render.fps),
            "loop": True,
            "frames": frames,
        },
        "neutral": {
            "file": neutral_path.name,
            "sha256": checksum(neutral_path),
            "bytes": neutral_path.stat().st_size,
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_RENDER_DIR={output_dir}")
    print(f"LEO_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()

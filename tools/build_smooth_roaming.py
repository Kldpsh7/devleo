#!/usr/bin/env python3
"""Interleave approved roam keyframes with generated midpoints and mirror them safely."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

CELL = (192, 208)
KEYFRAME_COUNT = 8
OUTPUT_FRAME_COUNT = 16


def load_frame(path: Path) -> Image.Image:
    with Image.open(path) as source:
        frame = source.convert("RGBA")
    if frame.size != CELL:
        raise SystemExit(f"{path} has size {frame.size}, expected {CELL}")
    return frame


def clear_hidden_rgb(frame: Image.Image) -> Image.Image:
    raw = frame.tobytes()
    pixels = [
        (raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3])
        if raw[offset + 3]
        else (0, 0, 0, 0)
        for offset in range(0, len(raw), 4)
    ]
    clean = Image.new("RGBA", frame.size)
    clean.putdata(pixels)
    return clean


def alpha_edge_pixels(frame: Image.Image) -> int:
    alpha = frame.getchannel("A")
    width, height = frame.size
    return sum(alpha.getpixel((x, y)) > 0 for x in range(width) for y in (0, height - 1)) + sum(
        alpha.getpixel((x, y)) > 0 for y in range(1, height - 1) for x in (0, width - 1)
    )


def frame_digest(frame: Image.Image) -> str:
    return hashlib.sha256(frame.tobytes()).hexdigest()


def assemble(args: argparse.Namespace) -> None:
    keyframes_dir = Path(args.keyframes_dir).resolve()
    midpoints_dir = Path(args.midpoints_dir).resolve()
    output = Path(args.output).resolve()
    strip = Image.new("RGBA", (CELL[0] * OUTPUT_FRAME_COUNT, CELL[1]), (0, 0, 0, 0))
    for index in range(KEYFRAME_COUNT):
        keyframe = load_frame(keyframes_dir / f"{index:02}.png")
        midpoint = load_frame(midpoints_dir / f"{index:02}.png")
        strip.alpha_composite(keyframe, (index * 2 * CELL[0], 0))
        strip.alpha_composite(midpoint, ((index * 2 + 1) * CELL[0], 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    clear_hidden_rgb(strip).save(output)
    print(json.dumps({"ok": True, "output": str(output), "frames": OUTPUT_FRAME_COUNT}, indent=2))


def checkerboard(size: tuple[int, int]) -> Image.Image:
    background = Image.new("RGB", size, "#24272d")
    draw = ImageDraw.Draw(background)
    tile = 16
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill="#30343b")
    return background


def save_preview(frames: list[Image.Image], path: Path, duration_ms: int) -> None:
    rendered: list[Image.Image] = []
    for frame in frames:
        background = checkerboard(CELL).convert("RGBA")
        background.alpha_composite(frame)
        rendered.append(background.convert("RGB"))
    rendered[0].save(
        path,
        save_all=True,
        append_images=rendered[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )


def split(args: argparse.Namespace) -> None:
    source = Path(args.input).resolve()
    right_dir = Path(args.right_output_dir).resolve()
    left_dir = Path(args.left_output_dir).resolve()
    qa_dir = Path(args.qa_dir).resolve()
    with Image.open(source) as image:
        strip = image.convert("RGBA")
    expected_size = (CELL[0] * OUTPUT_FRAME_COUNT, CELL[1])
    if strip.size != expected_size:
        raise SystemExit(f"{source} has size {strip.size}, expected {expected_size}")

    right_dir.mkdir(parents=True, exist_ok=True)
    left_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)
    right_frames: list[Image.Image] = []
    left_frames: list[Image.Image] = []
    frame_reports: list[dict[str, object]] = []
    for index in range(OUTPUT_FRAME_COUNT):
        frame = clear_hidden_rgb(
            strip.crop((index * CELL[0], 0, (index + 1) * CELL[0], CELL[1]))
        )
        edge_pixels = alpha_edge_pixels(frame)
        if edge_pixels:
            raise SystemExit(f"frame {index:02} touches a cell edge ({edge_pixels} pixels)")
        mirrored = clear_hidden_rgb(ImageOps.mirror(frame))
        frame.save(right_dir / f"{index:02}.png")
        mirrored.save(left_dir / f"{index:02}.png")
        right_frames.append(frame)
        left_frames.append(mirrored)
        frame_reports.append(
            {
                "frame": index,
                "bbox": list(frame.getchannel("A").getbbox() or (0, 0, 0, 0)),
                "edge_pixels": edge_pixels,
                "sha256_rgba": frame_digest(frame),
            }
        )

    contact = checkerboard((CELL[0] * 8, CELL[1] * 4)).convert("RGBA")
    for index, frame in enumerate(right_frames + left_frames):
        contact.alpha_composite(frame, ((index % 8) * CELL[0], (index // 8) * CELL[1]))
    contact.convert("RGB").save(qa_dir / "contact-sheet.png")
    save_preview(right_frames, qa_dir / "walk-right.gif", args.duration_ms)
    save_preview(left_frames, qa_dir / "walk-left.gif", args.duration_ms)

    manifest = {
        "ok": True,
        "source": str(source),
        "frame_count": OUTPUT_FRAME_COUNT,
        "frame_duration_ms": args.duration_ms,
        "cell": list(CELL),
        "right_output_dir": str(right_dir),
        "left_output_dir": str(left_dir),
        "left_derivation": "framewise-horizontal-mirror-preserving-order",
        "unique_right_frames": len({report["sha256_rgba"] for report in frame_reports}),
        "frames": frame_reports,
    }
    (qa_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    assemble_parser = commands.add_parser("assemble")
    assemble_parser.add_argument("--keyframes-dir", required=True)
    assemble_parser.add_argument("--midpoints-dir", required=True)
    assemble_parser.add_argument("--output", required=True)
    assemble_parser.set_defaults(handler=assemble)
    split_parser = commands.add_parser("split")
    split_parser.add_argument("--input", required=True)
    split_parser.add_argument("--right-output-dir", required=True)
    split_parser.add_argument("--left-output-dir", required=True)
    split_parser.add_argument("--qa-dir", required=True)
    split_parser.add_argument("--duration-ms", type=int, default=85)
    split_parser.set_defaults(handler=split)
    return root


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()

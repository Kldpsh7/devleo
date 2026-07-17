"""Build a clean, deformable topology candidate for realistic Leo.

Run this file through Blender, not the system Python:

    blender --background --python tools/blender/retopologize_realistic_leo.py -- \
      --input assets/source-3d/leo-realistic.blend \
      --output assets/source-3d/leo-realistic-topology.blend \
      --report assets/renders/work/realistic-topology/topology-report.json

The result remains an isolated modeling candidate. This stage does not rig the
mesh, animate it, or replace runtime sprites.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

import bmesh
import bpy

PIPELINE_VERSION = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--body-name", default="Leo_Realistic_Body")
    parser.add_argument("--target-faces", type=int, default=16_000)
    parser.add_argument("--seed", type=int, default=7)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def mesh_island_count(mesh: bmesh.types.BMesh) -> int:
    unseen = set(mesh.verts)
    count = 0
    while unseen:
        count += 1
        start = unseen.pop()
        queue = deque([start])
        while queue:
            vertex = queue.popleft()
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    return count


def mesh_stats(object_: bpy.types.Object) -> dict[str, Any]:
    mesh = bmesh.new()
    mesh.from_mesh(object_.data)
    face_sides = {
        str(side_count): sum(1 for face in mesh.faces if len(face.verts) == side_count)
        for side_count in sorted({len(face.verts) for face in mesh.faces})
    }
    result = {
        "vertices": len(mesh.verts),
        "edges": len(mesh.edges),
        "faces": len(mesh.faces),
        "face_sides": face_sides,
        "boundary_edges": sum(1 for edge in mesh.edges if edge.is_boundary),
        "nonmanifold_edges": sum(1 for edge in mesh.edges if not edge.is_manifold),
        "isolated_vertices": sum(1 for vertex in mesh.verts if not vertex.link_edges),
        "mesh_islands": mesh_island_count(mesh),
        "unsigned_volume": round(mesh.calc_volume(signed=False), 6),
    }
    mesh.free()
    return result


def material_names(object_: bpy.types.Object) -> list[str | None]:
    return [material.name if material else None for material in object_.data.materials]


def packed_material_images(object_: bpy.types.Object) -> list[dict[str, Any]]:
    images: dict[str, dict[str, Any]] = {}
    for material in object_.data.materials:
        if material is None or not material.use_nodes or material.node_tree is None:
            continue
        for node in material.node_tree.nodes:
            image = getattr(node, "image", None)
            if image is None:
                continue
            packed_files = getattr(image, "packed_files", ())
            images[image.name] = {
                "name": image.name,
                "packed": bool(packed_files),
                "size": list(image.size),
            }
    return sorted(images.values(), key=lambda item: item["name"])


def close_source_holes(object_: bpy.types.Object) -> int:
    mesh = bmesh.new()
    mesh.from_mesh(object_.data)
    boundary_edges = [edge for edge in mesh.edges if edge.is_boundary]
    if not boundary_edges:
        mesh.free()
        return 0
    result = bmesh.ops.holes_fill(mesh, edges=boundary_edges, sides=0)
    bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces)
    filled_faces = len(result.get("faces", []))
    remaining_boundaries = sum(1 for edge in mesh.edges if edge.is_boundary)
    if remaining_boundaries:
        mesh.free()
        raise RuntimeError(f"source hole closure left {remaining_boundaries} boundary edges")
    mesh.to_mesh(object_.data)
    mesh.free()
    object_.data.update()
    return filled_faces


def validate_result(
    *,
    source_stats: dict[str, Any],
    result_stats: dict[str, Any],
    source_materials: list[str | None],
    result_materials: list[str | None],
    source_images: list[dict[str, Any]],
    result_images: list[dict[str, Any]],
    source_vertex_groups: list[str],
    target_faces: int,
) -> list[str]:
    errors: list[str] = []
    lower_face_limit = int(target_faces * 0.75)
    upper_face_limit = int(target_faces * 1.25)
    if not lower_face_limit <= result_stats["faces"] <= upper_face_limit:
        errors.append(
            f"face count {result_stats['faces']} is outside {lower_face_limit}..{upper_face_limit}"
        )
    if result_stats["face_sides"] != {"4": result_stats["faces"]}:
        errors.append(f"result is not all-quads: {result_stats['face_sides']}")
    if result_stats["boundary_edges"]:
        errors.append(f"result has {result_stats['boundary_edges']} boundary edges")
    if result_stats["nonmanifold_edges"]:
        errors.append(f"result has {result_stats['nonmanifold_edges']} non-manifold edges")
    if result_stats["isolated_vertices"]:
        errors.append(f"result has {result_stats['isolated_vertices']} isolated vertices")
    if result_stats["mesh_islands"] != 1:
        errors.append(f"result has {result_stats['mesh_islands']} disconnected mesh islands")
    if result_stats["faces"] >= source_stats["faces"]:
        errors.append("retopology did not reduce the source face count")
    volume_ratio = result_stats["unsigned_volume"] / source_stats["unsigned_volume"]
    if not 0.98 <= volume_ratio <= 1.02:
        errors.append(f"volume ratio {volume_ratio:.6f} is outside 0.98..1.02")
    if result_materials != source_materials:
        errors.append(f"material slots changed from {source_materials!r} to {result_materials!r}")
    if result_images != source_images:
        errors.append("packed projection image inventory changed during retopology")
    unpacked = [image["name"] for image in result_images if not image["packed"]]
    if unpacked:
        errors.append(f"projection images are not packed: {unpacked}")
    if source_vertex_groups:
        errors.append(
            "source already has vertex groups; retopology must not silently discard rig data"
        )
    return errors


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if args.target_faces < 1:
        raise ValueError("--target-faces must be positive")

    bpy.ops.wm.open_mainfile(filepath=str(source))
    body = bpy.data.objects.get(args.body_name)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Expected mesh object {args.body_name!r}")

    source_stats = mesh_stats(body)
    source_materials = material_names(body)
    source_images = packed_material_images(body)
    source_vertex_groups = [group.name for group in body.vertex_groups]
    filled_source_holes = close_source_holes(body)

    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    result = bpy.ops.object.quadriflow_remesh(
        mode="FACES",
        target_faces=args.target_faces,
        seed=args.seed,
        use_mesh_symmetry=False,
        use_preserve_boundary=False,
        use_preserve_sharp=False,
        preserve_attributes=True,
        smooth_normals=True,
    )
    if "FINISHED" not in result:
        raise RuntimeError(f"QuadriFlow failed: {result}")
    for polygon in body.data.polygons:
        polygon.use_smooth = True

    bpy.ops.file.pack_all()
    result_stats = mesh_stats(body)
    result_materials = material_names(body)
    result_images = packed_material_images(body)
    errors = validate_result(
        source_stats=source_stats,
        result_stats=result_stats,
        source_materials=source_materials,
        result_materials=result_materials,
        source_images=source_images,
        result_images=result_images,
        source_vertex_groups=source_vertex_groups,
        target_faces=args.target_faces,
    )
    volume_ratio = result_stats["unsigned_volume"] / source_stats["unsigned_volume"]
    report = {
        "schema_version": 1,
        "ok": not errors,
        "runtime_replacement": False,
        "third_party_mesh": False,
        "project_owned_reference": True,
        "output": output.name,
        "body_object": body.name,
        "generator": {
            "blender": bpy.app.version_string,
            "script": "tools/blender/retopologize_realistic_leo.py",
            "pipeline_version": PIPELINE_VERSION,
        },
        "method": {
            "source_holes": "bmesh holes_fill",
            "retopology": "Blender QuadriFlow",
            "target_faces": args.target_faces,
            "seed": args.seed,
            "symmetry": False,
            "preserve_attributes": True,
        },
        "filled_source_holes": filled_source_holes,
        "source_vertex_groups": source_vertex_groups,
        "volume_ratio": round(volume_ratio, 6),
        "source": {
            "file": source.name,
            "mesh": source_stats,
            "materials": source_materials,
            "packed_images": source_images,
        },
        "result": {
            "file": output.name,
            "mesh": result_stats,
            "materials": result_materials,
            "packed_images": result_images,
        },
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(f"clean-topology QA failed: {errors}")

    scene = bpy.context.scene
    scene["leo_topology_pipeline_version"] = PIPELINE_VERSION
    scene["leo_asset_status"] = "clean-topology-candidate-not-runtime-approved"
    scene["leo_topology_source"] = source.name
    scene["leo_topology_method"] = "closed-source QuadriFlow, attributes preserved"
    scene["leo_topology_target_faces"] = args.target_faces
    scene["leo_next_gate"] = "clean topology identity turntable QA"
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"LEO_REALISTIC_TOPOLOGY={output}")
    print(f"LEO_REALISTIC_TOPOLOGY_QA={report_path}")


if __name__ == "__main__":
    main()

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reproducible_blender_sources_are_retained() -> None:
    source_dir = ROOT / "assets" / "source-3d"
    expected = (
        "leo.blend",
        "leo-realistic-seed.blend",
        "leo-realistic.blend",
        "leo-realistic-topology.blend",
        "leo-realistic-rig.blend",
    )
    for name in expected:
        assert (source_dir / name).stat().st_size > 100_000, name


def test_realistic_identity_references_are_retained() -> None:
    reference_dir = ROOT / "assets" / "source" / "realistic-identity-reference"
    for name in ("cardinal-turnaround.png", "diagonal-turnaround.png", "reference-qa.json"):
        assert (reference_dir / name).stat().st_size > 0, name

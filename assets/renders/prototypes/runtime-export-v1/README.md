# Leo runtime export prototype v1

Status: approved isolated package; not copied into the installed desktop runtime.

This snapshot contains:

- Codex v2 `8×11` package sheets at 1×, 2×, and 4× density.
- `pet.json` with `spriteVersionNumber: 2`.
- Official atlas validation and the single required edge-cleanup report.
- Standard-row contact sheet and actual-size full-family motion previews.
- Labeled 16-direction review, blind-pair evidence, consensus, hidden-answer-key
  validation, continuity metrics, and the recorded minor-warning resolution.
- Independent final visual QA.

The official v2 validator reports no errors or warnings and zero transparent-RGB
residue. Full 232-frame exports at all densities are intentionally omitted from
Git; `tools/blender/export_runtime_assets.sh` deterministically rebuilds them from
the approved Blender work renders.

The two review warnings are limited to isolated horizontal classification of
near-down directions 157.5 and 202.5. All hard cardinal gates pass, and labeled
normal-size review confirms a continuous right-to-down-to-left sequence without
reversal.

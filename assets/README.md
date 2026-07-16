# Asset Workspace

Expected layout:

```text
assets/
├── source/       # high-resolution generation outputs and original references
├── approved/     # reviewed master frames and manifests
└── runtime/      # deterministic 1x, 2x, and 4x exports consumed by the app
```

`source/` and intermediate generated work are not runtime inputs. Only files promoted into `approved/` may be exported into `runtime/`.

Large disposable generation intermediates should stay under ignored `assets/work/` or `assets/generated/` paths. Do not commit secrets, temporary prompts containing private context, or unreviewed generated variants.

See [Graphics Quality](../docs/GRAPHICS_QUALITY.md).

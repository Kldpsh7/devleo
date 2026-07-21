# Asset Workspace

Expected layout:

```text
assets/
├── source/       # canonical high-resolution visual references
├── source-3d/    # reproducible Blender source scenes
└── approved/     # current reviewed master frames and manifests
```

`source/` and intermediate generated work are not runtime inputs. The current
approved art lives in `approved/leo-the-dev-realistic-v2/`; the installed app
loads its packaged copies from `src/lion_cub_pet/assets/`.

Large disposable generation and Blender render intermediates must stay under
ignored `assets/work/`, `assets/generated/`, or `assets/renders/work/` paths.
Do not commit secrets, temporary prompts containing private context, or
unreviewed generated variants.

See [Graphics Quality](../docs/GRAPHICS_QUALITY.md).

Original PNG, WebP, and GIF artwork in this workspace is licensed under
[CC BY 4.0](../LICENSE-ASSETS.md). Non-visual project files remain under the
[MIT License](../LICENSE).

# Contributing

Use Python 3.11 or newer. Keep platform-specific behavior behind a platform adapter and preserve the documented CLI contract.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/pytest -q
.venv/bin/mypy src
```

Windows uses `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Animation changes must satisfy [the graphics release gate](docs/GRAPHICS_QUALITY.md) and include regenerated visual QA artifacts. Never commit generated drafts, secrets, user configuration, logs, or signing material.

For Blender source or render changes, install `.[dev,art]`, run
`tools/blender/render_idle.sh`, and review all outputs documented in
[the Blender pipeline](docs/BLENDER_PIPELINE.md). Scratch renders remain ignored.

By submitting a contribution, you agree that non-visual contributions are
licensed under MIT and original visual artwork contributions are licensed
under CC BY 4.0. Only submit material you have the right to license on those
terms.

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


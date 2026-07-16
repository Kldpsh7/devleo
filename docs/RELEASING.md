# Releasing Leo the Dev

## One-time setup

Software is licensed under MIT and original visual assets under CC BY 4.0. Both notices are included in release archives through PEP 639 package metadata.

1. Create the public GitHub repository and replace every `<OWNER>` placeholder in `README.md`.
2. Create a protected GitHub environment named `pypi`; require an approver for production releases.
3. In PyPI, create a pending Trusted Publisher for package `lion-cub-pet` using the GitHub owner, repository name, workflow `release.yml`, and environment `pypi`.
4. Confirm the repository version, release tag, and changelog all match.

`lion-cub-pet` returned no project from PyPI's JSON API during preparation on 2026-07-16. That is not a reservation; verify the name again immediately before creating the pending publisher.

## Local release gate

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check src tests
mypy src
python -m build
python -m twine check dist/*
```

Install the built wheel into a clean virtual environment and verify:

```bash
python -m venv .release-venv
.release-venv/bin/python -m pip install dist/*.whl
.release-venv/bin/lion-cub-pet version
```

Use `.release-venv\Scripts\` on Windows.

## Publish

1. Commit the version and changelog.
2. Create and push tag `v<version>`.
3. Publish a GitHub Release from that tag.
4. `.github/workflows/release.yml` builds the wheel and source archive, checks metadata, creates `SHA256SUMS`, uploads the distributions through PyPI Trusted Publishing, and attaches all artifacts to the GitHub Release.
5. Install from PyPI on one clean macOS, Windows, and Linux user account before announcing the release.

The workflow uses GitHub OIDC and stores no long-lived PyPI API token.

## Installer checks

Published package:

```bash
LEO_AUTOSTART=0 sh install.sh
```

Unpublished Git source:

```bash
LEO_AUTOSTART=0 LEO_PACKAGE_SPEC="git+https://github.com/<OWNER>/lion-cub-pet" sh install.sh
```

PowerShell uses the same `LEO_AUTOSTART` and `LEO_PACKAGE_SPEC` environment variables with `install.ps1`.

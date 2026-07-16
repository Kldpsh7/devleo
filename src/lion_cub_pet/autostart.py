from __future__ import annotations

import os
import plistlib
import shlex
import sys
from pathlib import Path

from platformdirs import user_config_dir


def command() -> list[str]:
    return [sys.executable, "-m", "lion_cub_pet.runtime"]


def path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/LaunchAgents/dev.lioncub.pet.plist"
    if os.name == "nt":
        return (
            Path(os.environ["APPDATA"])
            / "Microsoft/Windows/Start Menu/Programs/Startup/lion-cub-pet.cmd"
        )
    return Path(user_config_dir("autostart", appauthor=False)) / "lion-cub-pet.desktop"


def enable() -> Path:
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    argv = command()
    if sys.platform == "darwin":
        with target.open("wb") as handle:
            plistlib.dump(
                {"Label": "dev.lioncub.pet", "ProgramArguments": argv, "RunAtLoad": True}, handle
            )
    elif os.name == "nt":
        target.write_text(f'@start "" "{argv[0]}" -m lion_cub_pet.runtime\n', encoding="utf-8")
    else:
        executable = " ".join(shlex.quote(item) for item in argv)
        target.write_text(
            "[Desktop Entry]\nType=Application\nName=Lion Cub Pet\n"
            f"Exec={executable}\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    return target


def disable() -> None:
    path().unlink(missing_ok=True)

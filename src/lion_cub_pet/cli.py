from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import asdict
from typing import Any

from lion_cub_pet import __version__, autostart
from lion_cub_pet.config import (
    PetConfig,
    config_path,
    load_config,
    log_path,
    parse_value,
    runtime_dir,
    save_config,
    set_value,
)
from lion_cub_pet.ipc import send_command

ANIMATIONS = [
    "auto",
    "idle",
    "walk",
    "run",
    "wave",
    "jump",
    "failure",
    "waiting",
    "working",
    "review",
]


def emit(value: Any, as_json: bool = False) -> None:
    if as_json or isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, default=str))
    else:
        print(value)


def request(action: str, value: Any = None, **extra: Any) -> dict[str, Any]:
    return send_command({"action": action, "value": value, **extra})


def start() -> dict[str, Any]:
    try:
        return request("status")
    except (ConnectionError, TimeoutError):
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, "-m", "lion_cub_pet.runtime"], **kwargs)
        # A cold PySide start can take several seconds while macOS loads Qt frameworks.
        for _ in range(150):
            time.sleep(0.1)
            try:
                return request("status")
            except (ConnectionError, TimeoutError):
                continue
        raise RuntimeError(f"pet did not start; inspect {log_path()}") from None


def add_value_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    choices: list[str] | None = None,
) -> None:
    parser = subparsers.add_parser(name)
    parser.add_argument("value", choices=choices)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="lion-cub-pet", description="Control Leo the Dev, the desktop lion cub."
    )
    root.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = root.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install")
    install.add_argument("--autostart", action="store_true")
    install.add_argument("--start", action="store_true")
    uninstall = commands.add_parser("uninstall")
    uninstall.add_argument("--keep-config", action="store_true")
    uninstall.add_argument("--keep-assets", action="store_true")
    for name in [
        "start",
        "stop",
        "restart",
        "status",
        "version",
        "show",
        "hide",
        "toggle",
        "pause",
        "resume",
        "quit",
        "roam",
        "stay",
        "unanchor",
        "demo",
        "advice-now",
        "doctor",
        "paths",
        "check-update",
        "update",
    ]:
        commands.add_parser(name)
    anchor = commands.add_parser("anchor")
    anchor.add_argument(
        "position", choices=["current", "bottom-right", "bottom-left", "top-right", "top-left"]
    )
    move = commands.add_parser("move")
    move.add_argument("x", type=int)
    move.add_argument("y", type=int)
    screen = commands.add_parser("screen")
    screen.add_argument("index")
    add_value_command(commands, "speed")
    add_value_command(commands, "size")
    opacity = commands.add_parser("opacity")
    opacity.add_argument("value", type=float)
    for name in ["always-on-top", "click-through", "avoid-cursor", "dialogues", "advice"]:
        add_value_command(commands, name, ["on", "off"])
    add_value_command(commands, "personality", ["playful"])
    add_value_command(commands, "mode", ["normal", "relax", "focus", "sleep", "motivate"])
    add_value_command(commands, "bounds", ["work-area", "full-screen"])
    for name in ["idle-delay", "run-chance", "snap-distance"]:
        add_value_command(commands, name)
    add_value_command(commands, "play", ANIMATIONS)
    look = commands.add_parser("look")
    look.add_argument("degrees", type=float)
    add_value_command(commands, "laptop", ["auto", "closed", "half-open", "open"])
    say = commands.add_parser("say")
    say.add_argument("text", nargs="+")
    preview = commands.add_parser("preview")
    preview.add_argument("animation", choices=ANIMATIONS[1:])
    auto = commands.add_parser("autostart")
    auto.add_argument("operation", choices=["enable", "disable", "status"])
    config = commands.add_parser("config")
    config_sub = config.add_subparsers(dest="operation", required=True)
    config_sub.add_parser("list")
    get = config_sub.add_parser("get")
    get.add_argument("key")
    set_parser = config_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    unset = config_sub.add_parser("unset")
    unset.add_argument("key")
    config_sub.add_parser("reset")
    config_sub.add_parser("path")
    config_sub.add_parser("edit")
    logs = commands.add_parser("logs")
    logs.add_argument("--follow", action="store_true")
    completion = commands.add_parser("completion")
    completion.add_argument("shell", choices=["bash", "zsh", "fish", "powershell"])
    event = commands.add_parser("event")
    event.add_argument("state", choices=["working", "waiting", "review", "failure", "clear"])
    event.add_argument("--source", default="cli")
    event.add_argument("--ttl", type=int)
    return root


def configure(args: argparse.Namespace) -> Any:
    config = load_config()
    if args.operation == "list":
        return asdict(config)
    if args.operation == "get":
        if not hasattr(config, args.key):
            raise KeyError(args.key)
        return getattr(config, args.key)
    if args.operation == "set":
        set_value(config, args.key, parse_value(args.value))
        save_config(config)
        with suppress(ConnectionError):
            request("set", getattr(config, args.key), key=args.key)
        return {args.key: getattr(config, args.key)}
    if args.operation == "unset":
        default = PetConfig()
        if not hasattr(default, args.key):
            raise KeyError(args.key)
        setattr(config, args.key, getattr(default, args.key))
        save_config(config)
        return {args.key: getattr(config, args.key)}
    if args.operation == "reset":
        save_config(PetConfig())
        return "configuration reset"
    if args.operation == "path":
        return config_path()
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise RuntimeError("set VISUAL or EDITOR")
    config_path().parent.mkdir(parents=True, exist_ok=True)
    if not config_path().exists():
        save_config(config)
    return subprocess.call([editor, str(config_path())])


def completion(shell: str) -> str:
    command_names = [
        "install",
        "uninstall",
        "start",
        "stop",
        "restart",
        "status",
        "version",
        "show",
        "hide",
        "toggle",
        "pause",
        "resume",
        "quit",
        "roam",
        "stay",
        "mode",
        "say",
        "advice-now",
        "anchor",
        "unanchor",
        "move",
        "screen",
        "speed",
        "size",
        "opacity",
        "always-on-top",
        "click-through",
        "personality",
        "dialogues",
        "advice",
        "bounds",
        "idle-delay",
        "run-chance",
        "snap-distance",
        "avoid-cursor",
        "play",
        "look",
        "laptop",
        "demo",
        "preview",
        "autostart",
        "config",
        "doctor",
        "logs",
        "paths",
        "check-update",
        "update",
        "completion",
        "event",
    ]
    commands = " ".join(command_names)
    if shell == "fish":
        return "\n".join(f"complete -c lion-cub-pet -f -a '{name}'" for name in commands.split())
    if shell == "powershell":
        return (
            "Register-ArgumentCompleter -CommandName lion-cub-pet -ScriptBlock "
            f"{{ param($w) '{commands}' -split ' ' | ? {{ $_ -like \"$w*\" }} }}"
        )
    return f"complete -W '{commands}' lion-cub-pet"


def run(args: argparse.Namespace) -> Any:  # noqa: C901, PLR0911
    command = args.command
    if command == "version":
        return __version__
    if command == "install":
        save_config(load_config())
        result: dict[str, Any] = {"installed": True, "config": str(config_path())}
        if args.autostart:
            result["autostart"] = str(autostart.enable())
        if args.start:
            result["runtime"] = start()
        return result
    if command == "uninstall":
        with suppress(ConnectionError):
            request("quit")
        autostart.disable()
        if not args.keep_config:
            config_path().unlink(missing_ok=True)
        return {"uninstalled": True, "package_removal": "run: uv tool uninstall lion-cub-pet"}
    if command == "start":
        return start()
    if command in {"stop", "quit"}:
        return request("quit")
    if command == "restart":
        try:
            request("quit")
            time.sleep(0.3)
        except ConnectionError:
            pass
        return start()
    if command == "status":
        try:
            return request("status")
        except ConnectionError:
            return {"ok": True, "running": False}
    if command in {
        "show",
        "hide",
        "toggle",
        "pause",
        "resume",
        "roam",
        "stay",
        "unanchor",
        "demo",
        "advice-now",
    }:
        return request(command)
    if command == "mode":
        return request("mode", args.value)
    if command == "say":
        return request("say", " ".join(args.text))
    if command == "anchor":
        return request("anchor", args.position)
    if command == "move":
        return request("move", [args.x, args.y])
    if command == "screen":
        value: Any = args.index if args.index == "next" else int(args.index)
        return request("screen", value)
    if command in {
        "speed",
        "size",
        "opacity",
        "always-on-top",
        "click-through",
        "personality",
        "dialogues",
        "advice",
        "bounds",
        "idle-delay",
        "run-chance",
        "snap-distance",
        "avoid-cursor",
        "laptop",
    }:
        key = command.replace("-", "_")
        value = args.value
        if command == "speed":
            value = {"slow": 70.0, "normal": 115.0, "fast": 190.0}.get(
                value, float(value) if value not in {"slow", "normal", "fast"} else value
            )
        elif command == "size":
            value = {"small": 0.7, "normal": 1.0, "large": 1.25}.get(
                value, float(value) if value not in {"small", "normal", "large"} else value
            )
            key = "scale"
        elif command in {"always-on-top", "click-through", "avoid-cursor", "dialogues", "advice"}:
            value = value == "on"
        elif command in {"idle-delay", "opacity"}:
            value = float(value)
        elif command in {"run-chance", "snap-distance"}:
            value = int(value)
        return request("set", value, key=key)
    if command in {"play", "preview"}:
        return request("play", getattr(args, "value", None) or args.animation)
    if command == "look":
        return request("look", args.degrees)
    if command == "autostart":
        if args.operation == "enable":
            return {"enabled": True, "path": str(autostart.enable())}
        if args.operation == "disable":
            autostart.disable()
        return {"enabled": autostart.path().exists(), "path": str(autostart.path())}
    if command == "config":
        return configure(args)
    if command == "paths":
        return {
            "config": config_path(),
            "logs": log_path(),
            "runtime": runtime_dir(),
            "autostart": autostart.path(),
        }
    if command == "doctor":
        try:
            response = request("status")
            running = bool(response.get("ok"))
        except ConnectionError:
            running = False
        return {
            "ok": True,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "running": running,
            "config_valid": isinstance(load_config(), PetConfig),
            "autostart": autostart.path().exists(),
        }
    if command == "logs":
        if not log_path().exists():
            return "no logs"
        if not args.follow:
            return log_path().read_text(encoding="utf-8")[-12000:]
        subprocess.call(["tail", "-f", str(log_path())])
        return 0
    if command == "completion":
        return completion(args.shell)
    if command == "event":
        return request(
            "play",
            "auto" if args.state == "clear" else args.state,
            source=args.source,
            ttl=args.ttl,
        )
    if command == "check-update":
        return {"ok": False, "reason": "release repository is not configured yet"}
    if command == "update":
        return {
            "ok": False,
            "command": "uv tool upgrade lion-cub-pet",
            "reason": "publish the GitHub repository first",
        }
    raise ValueError(command)


def main(argv: Sequence[str] | None = None) -> int:
    tokens = list(argv if argv is not None else sys.argv[1:])
    if "--json" in tokens:
        tokens.remove("--json")
        tokens.insert(0, "--json")
    args = parser().parse_args(tokens)
    try:
        result = run(args)
        emit(result, args.json)
        return 0
    except (ConnectionError, TimeoutError, KeyError, ValueError, RuntimeError) as error:
        emit({"ok": False, "error": str(error)}, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

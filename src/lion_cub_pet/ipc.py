from __future__ import annotations

import json
import os
from typing import Any, cast

from PySide6.QtCore import QIODevice
from PySide6.QtNetwork import QLocalSocket

SERVER_NAME = f"lion-cub-pet-{getattr(os, 'getuid', lambda: os.getpid())()}"


def send_command(command: dict[str, Any], timeout_ms: int = 1500) -> dict[str, Any]:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME, QIODevice.OpenModeFlag.ReadWrite)
    if not socket.waitForConnected(timeout_ms):
        raise ConnectionError("lion cub pet is not running")
    socket.write((json.dumps(command) + "\n").encode())
    if not socket.waitForBytesWritten(timeout_ms) or not socket.waitForReadyRead(timeout_ms):
        raise TimeoutError("lion cub pet did not respond")
    response = bytes(socket.readAll().data()).decode().strip()
    socket.disconnectFromServer()
    return cast(dict[str, Any], json.loads(response))

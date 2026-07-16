#!/bin/sh
set -eu

PACKAGE_SPEC=${LEO_PACKAGE_SPEC:-lion-cub-pet}
AUTOSTART=${LEO_AUTOSTART:-1}

find_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return
  fi
  for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  return 1
}

if ! UV_BIN=$(find_uv); then
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install uv" >&2
    exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV_BIN=$(find_uv) || {
    echo "uv installed but its executable could not be located" >&2
    exit 1
  }
fi

"$UV_BIN" tool install --force "$PACKAGE_SPEC"
TOOL_BIN=$($UV_BIN tool dir --bin)
LEO_BIN="$TOOL_BIN/lion-cub-pet"

if [ "$AUTOSTART" = "0" ]; then
  "$LEO_BIN" install --start
else
  "$LEO_BIN" install --autostart --start
fi

echo "Leo the Dev is installed and running."

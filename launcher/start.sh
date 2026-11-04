#!/bin/bash
# Starts Tape on a Mac or Linux. The first run sets up a private copy of Python and
# Tape's libraries in the data folder, so nothing else on the computer is touched and
# no admin rights are needed. Every download is pinned and checked against a checksum.

set -u

UV_VERSION="0.13.4"
PYTHON_VERSION="3.13"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="$APP_DIR/launcher/requirements.lock"

case "$(uname -s)" in
  Darwin) DEFAULT_DATA="$HOME/Library/Application Support/tape" ;;
  *)      DEFAULT_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/tape" ;;
esac
DATA_DIR="${TAPE_DATA_DIR:-$DEFAULT_DATA}"
RUNTIME="$DATA_DIR/runtime"
VENV="$RUNTIME/venv"
PYTHON="$VENV/bin/python"
UV="$RUNTIME/uv/uv"
STAMP="$RUNTIME/installed.txt"

stop_with_help() {
  echo
  echo "  Tape couldn't start: $1"
  echo "  Check your internet connection and open Start Tape again."
  echo "  START-HERE.html has more help."
  echo
  exit 1
}

sha256_of() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else sha256sum "$1" | cut -d' ' -f1; fi
}

install_uv() {
  local asset sha
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)  asset="uv-aarch64-apple-darwin"; sha="e0b1d4743ce64c55d9f0f4a444afa6b81125680070ee04e853fcd0f6c1ebf8f1" ;;
    Darwin-x86_64) asset="uv-x86_64-apple-darwin"; sha="7be2dcd316122f4b3e5a0a7889f6248266c14425374e105ff7dc9779184603a6" ;;
    Linux-x86_64)  asset="uv-x86_64-unknown-linux-gnu"; sha="2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f" ;;
    Linux-aarch64) asset="uv-aarch64-unknown-linux-gnu"; sha="1ae72b4718729e2ccc4f1ae2c6d1e531ca8467800e0546e9130b3886023a60ab" ;;
    *) stop_with_help "this computer type ($(uname -s) $(uname -m)) isn't supported." ;;
  esac
  mkdir -p "$RUNTIME/uv"
  local archive="$RUNTIME/uv.tar.gz"
  curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$asset.tar.gz" -o "$archive" \
    || stop_with_help "the setup tool couldn't be downloaded."
  if [ "$(sha256_of "$archive")" != "$sha" ]; then
    rm -f "$archive"
    stop_with_help "the setup tool failed its checksum, so it was not used."
  fi
  tar -xzf "$archive" -C "$RUNTIME/uv" --strip-components=1 || stop_with_help "the setup tool couldn't be unpacked."
  rm -f "$archive"
}

WANTED="$(sha256_of "$LOCK") python-$PYTHON_VERSION uv-$UV_VERSION"
HAVE="$(cat "$STAMP" 2>/dev/null || true)"

if [ "$HAVE" != "$WANTED" ] || [ ! -x "$PYTHON" ]; then
  echo
  echo "  Setting up Tape. This only happens once and takes a couple of minutes."
  echo
  mkdir -p "$RUNTIME" || stop_with_help "the folder $RUNTIME couldn't be created."
  [ -x "$UV" ] || install_uv
  export UV_PYTHON_INSTALL_DIR="$RUNTIME/python"
  export UV_CACHE_DIR="$RUNTIME/cache"

  echo "  Getting Python..."
  "$UV" venv --quiet --no-config --clear --python "$PYTHON_VERSION" --python-preference only-managed "$VENV" \
    || stop_with_help "Python could not be set up."

  echo "  Getting the libraries Tape uses..."
  "$UV" pip sync --quiet --no-config --require-hashes --only-binary ':all:' --python "$PYTHON" "$LOCK" \
    || stop_with_help "the libraries could not be installed."

  # Prove it loads before calling it done.
  echo "  Checking that everything loads..."
  (cd "$APP_DIR" && TAPE_DATA_DIR="$DATA_DIR" "$PYTHON" -c 'import tape.server; from tape.ai import claude, chatgpt') \
    || stop_with_help "the libraries installed but won't load."

  echo "$WANTED" > "$STAMP"
  echo "  Setup finished."
fi

export TAPE_DATA_DIR="$DATA_DIR"
export PYTHONUTF8=1
unset PYTHONHOME PYTHONPATH

cd "$APP_DIR" || exit 1
echo
echo "  Tape is starting. Your browser will open in a moment."
echo "  Keep this window open while you use Tape. Close it to quit."
echo
exec "$PYTHON" -m tape serve --open

#!/bin/sh
set -eu

RELEASE_TAG="${FUCKMARK_RELEASE_TAG:-v0.4.1}"
PACKAGE_VERSION="${RELEASE_TAG#v}"
WHEEL_NAME="fuckmark-${PACKAGE_VERSION}-py3-none-any.whl"
RELEASE_BASE="https://github.com/byte271/FuckMark/releases/download/${RELEASE_TAG}"
ROOT="${FUCKMARK_HOME:-$HOME/.local/share/q1z/fuckmark}"
VENV="$ROOT/venv"
BIN="${FUCKMARK_BIN:-$HOME/.local/bin}"
STAGE="$ROOT/stage"

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

ensure_path() {
  shell_name="$(basename "${SHELL:-sh}")"
  escaped=$(printf "%s" "$BIN" | sed "s/'/'\\\\''/g")
  quoted="'${escaped}'"
  line="export PATH=${quoted}:\"\$PATH\""
  case "$shell_name" in
    zsh)
      file="$HOME/.zshrc"
      ;;
    bash)
      file="$HOME/.bashrc"
      ;;
    fish)
      file="$HOME/.config/fish/config.fish"
      mkdir -p "$(dirname "$file")"
      touch "$file"
      fish_line="fish_add_path ${quoted}"
      grep -F "$fish_line" "$file" >/dev/null 2>&1 || printf '\n%s\n' "$fish_line" >> "$file"
      return 0
      ;;
    *)
      file="$HOME/.profile"
      ;;
  esac
  touch "$file"
  grep -F "$line" "$file" >/dev/null 2>&1 || printf '\n%s\n' "$line" >> "$file"
}

download() {
  url="$1"
  dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$dest" "$url"
  else
    printf '%s\n' "curl or wget is required to download the release."
    exit 1
  fi
}

if [ "$(uname -s)" != "Linux" ] && [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' "This installer is for Linux and macOS."
  exit 1
fi

printf '\n%s\n%s\n\n' "FuckMark" "Installing tagged release ${RELEASE_TAG} with SHA-256 verification."

PYTHON="$(find_python || true)"
if [ -z "$PYTHON" ]; then
  printf '%s\n' "Python 3.11 or newer is required. Install it yourself, then rerun."
  printf '%s\n' "This installer does not use sudo and does not install Python."
  exit 1
fi

mkdir -p "$ROOT" "$BIN" "$STAGE"
rm -f "$STAGE/$WHEEL_NAME" "$STAGE/SHA256SUMS.txt"

printf '%s\n' "Downloading ${WHEEL_NAME} and SHA256SUMS.txt..."
download "$RELEASE_BASE/SHA256SUMS.txt" "$STAGE/SHA256SUMS.txt"
download "$RELEASE_BASE/$WHEEL_NAME" "$STAGE/$WHEEL_NAME"

if [ ! -x "$VENV/bin/python" ]; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV"
fi

"$VENV/bin/python" - "$STAGE/SHA256SUMS.txt" "$STAGE/$WHEEL_NAME" <<'PY'
import hashlib
import pathlib
import sys

sums_path = pathlib.Path(sys.argv[1])
wheel_path = pathlib.Path(sys.argv[2])
expected = None
for line in sums_path.read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if len(parts) != 2:
        raise SystemExit("SHA256SUMS.txt line must contain digest and filename")
    digest, name = parts
    if name == wheel_path.name:
        expected = digest.lower()
        break
if expected is None:
    raise SystemExit("wheel filename is missing from SHA256SUMS.txt")
actual = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("wheel SHA-256 does not match SHA256SUMS.txt")
PY

printf '%s\n' "Checksum matched. Installing the verified wheel..."
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-cache-dir --upgrade "$STAGE/$WHEEL_NAME"

cat > "$BIN/fuckmark" <<EOF
#!/bin/sh
exec "$VENV/bin/python" -m fuckmark.cli "\$@"
EOF
chmod +x "$BIN/fuckmark"

ensure_path

printf '\n%s\n%s\n%s\n%s\n%s\n\n' \
  "FuckMark ${PACKAGE_VERSION} installed." \
  "The public CLI inserts hidden Unicode into ordinary English ASCII text." \
  "Installation success is not watermark removal. Check --status for the outcome." \
  "Command: fuckmark --help" \
  "Open a new terminal if the command is not on PATH yet."

#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
crate="$root/crates/fuckmark-scan"
cd "$crate"
rustup target add wasm32-unknown-unknown >/dev/null
cargo test --offline --quiet 2>/dev/null || cargo test --quiet
cargo build --release --target wasm32-unknown-unknown --quiet
src="$crate/target/wasm32-unknown-unknown/release/fuckmark_scan.wasm"
test -f "$src"
for dest in \
  "$root/editors/wasm/fuckmark_scan.wasm" \
  "$root/docs/fuckmark_scan.wasm" \
  "$root/fuckmark/webui/fuckmark_scan.wasm" \
  "$root/editors/browser/fuckmark_scan.wasm"
do
  cp "$src" "$dest"
done
cp "$root/editors/wasm/scan_wasm.js" "$root/docs/scan_wasm.js"
cp "$root/editors/wasm/scan_wasm.js" "$root/fuckmark/webui/scan_wasm.js"
cp "$root/editors/wasm/scan_wasm.js" "$root/editors/browser/scan_wasm.js"
wc -c "$src"

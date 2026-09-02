#!/bin/sh
set -eu
root="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
crate="$root/crates/fuckmark-scan"
cd "$crate"
cargo test --offline --quiet 2>/dev/null || cargo test --quiet
cargo build --release --quiet
lib=""
for candidate in \
  "$crate/target/release/libfuckmark_scan.so" \
  "$crate/target/release/libfuckmark_scan.dylib" \
  "$crate/target/release/fuckmark_scan.dll"
do
  if test -f "$candidate"; then
    lib="$candidate"
    break
  fi
done
test -n "$lib"
printf '%s\n' "$lib"
ls -l "$lib"

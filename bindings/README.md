# Language bindings

The classifier core lives in `crates/fuckmark-scan` (`fuckmark-hidden-scan-v1`).
Python remains the reference implementation in `fuckmark.product.scan`. These
bindings call the same table through the shared C / WASM ABI.

| Binding | Path | Engine |
| --- | --- | --- |
| C / FFI header | `crates/fuckmark-scan/include/fuckmark_scan.h` | host `cdylib` |
| Python (optional native) | `fuckmark/native_scan.py` | host `cdylib` via ctypes |
| Node / JS | `bindings/node` | WASM + JS fallback |
| Browser / extension | `editors/wasm`, `docs/scan.html` | WASM + JS fallback |

## Build the host library

```text
./crates/fuckmark-scan/build-native.sh
```

That prints the path to `libfuckmark_scan.so` (Linux), `.dylib` (macOS), or
`fuckmark_scan.dll` (Windows). Override discovery with `FUCKMARK_SCAN_LIB`.

Categories ABI: pass `*` for every category, an empty string for an empty
selection, or a comma-separated list such as `bidi_control,tag`.

Packed return values begin with a little-endian `u32` length followed by UTF-8
JSON.

## Python

```text
./crates/fuckmark-scan/build-native.sh
python -c "from fuckmark.native_scan import scan_text; print(scan_text('a\u202eb'))"
```

If the library is missing, `available()` is false and callers should use
`fuckmark.product.scan`.

## Node

```text
cd bindings/node
node sync-assets.js
node test.js
```

## C example

```text
./crates/fuckmark-scan/build-native.sh
cc -I crates/fuckmark-scan/include \
  crates/fuckmark-scan/examples/scan_cli.c \
  -L crates/fuckmark-scan/target/release -lfuckmark_scan \
  -Wl,-rpath,\$ORIGIN/../../crates/fuckmark-scan/target/release \
  -o /tmp/fm-scan
/tmp/fm-scan $'a\u202eb'
```

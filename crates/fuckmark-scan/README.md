# fuckmark-scan (Rust / WASM / native)

Native and `wasm32` build of `fuckmark-hidden-scan-v1`. Same category table as
`editors/vscode/scan.js` and `fuckmark.product.scan`. No network, no extra
crate dependencies. C ABI header: `include/fuckmark_scan.h`.

```text
rustup target add wasm32-unknown-unknown
./crates/fuckmark-scan/build-wasm.sh
./crates/fuckmark-scan/build-native.sh
```

`build-wasm.sh` writes `fuckmark_scan.wasm` next to the scan page, packaged web
UI, and Chromium popup. `build-native.sh` builds the host `cdylib` for the
Python ctypes binding and C callers.

Category filter encoding over the ABI: `*` means all categories, an empty
string means an empty selection, otherwise a comma-separated list.

Language bindings overview: [`bindings/README.md`](../../bindings/README.md).

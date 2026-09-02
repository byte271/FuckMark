# fuckmark-scan (Rust / WASM)

Native and `wasm32` build of `fuckmark-hidden-scan-v1`. Same category table as
`editors/vscode/scan.js` and `fuckmark.product.scan`. No network, no extra
crate dependencies.

```text
rustup target add wasm32-unknown-unknown
./crates/fuckmark-scan/build-wasm.sh
```

That writes `fuckmark_scan.wasm` next to the scan page, the packaged web UI,
and the Chromium popup. The page and popup load it when `fetch` works and keep
`scan.js` as the `file://` fallback.

`cargo test` in this directory covers classification, Trojan Source roles, and
clean. Conformance vectors are also replayed from Python via Node on the
committed module.

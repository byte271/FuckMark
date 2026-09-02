# @fuckmark/scan (Node)

Node binding for `fuckmark-hidden-scan-v1`. Loads the committed WASM module and
keeps the JS port as a fallback for lone UTF-16 surrogates / `file`-style
environments.

```text
cd bindings/node
node sync-assets.js
node test.js
```

```js
const scan = require("./index.js");

const result = await scan.scanText(source, null, "javascript");
const cleaned = await scan.cleanText(source, scan.fallback.DEFAULT_SECURITY_CATEGORIES);
```

Assets are copied from `editors/wasm` and `editors/vscode/scan.js`. Re-run
`npm run sync` after rebuilding the WASM module.

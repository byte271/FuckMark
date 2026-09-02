"use strict";

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "../..");
const copies = [
  ["editors/wasm/scan_wasm.js", "scan_wasm.js"],
  ["editors/wasm/fuckmark_scan.wasm", "fuckmark_scan.wasm"],
  ["editors/vscode/scan.js", "scan.js"],
];

for (const [srcRel, destName] of copies) {
  const src = path.join(root, srcRel);
  const dest = path.join(__dirname, destName);
  fs.copyFileSync(src, dest);
  process.stdout.write(destName + "\n");
}

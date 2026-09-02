"use strict";

const assert = require("assert");
const scan = require("./index.js");

(async () => {
  const rlo = String.fromCodePoint(0x202e);
  const result = await scan.scanText("a" + rlo + "b", null, "auto");
  assert.strictEqual(result.total, 1);
  assert.strictEqual(result.findings[0].category, "bidi_control");
  assert.strictEqual(result.findings[0].severity, "critical");
  const cleaned = await scan.cleanText("a" + rlo + "b", ["bidi_control"]);
  assert.strictEqual(cleaned.removed, 1);
  assert.strictEqual(cleaned.cleaned, "ab");
  const empty = await scan.scanText("a" + rlo + "b", [], "auto");
  assert.strictEqual(empty.total, 0);
  const lone = await scan.scanText("\uD800", null, "auto");
  assert.strictEqual(lone.total, 1);
  assert.strictEqual(lone.findings[0].category, "surrogate");
  assert.strictEqual(lone.findings[0].index, 0);
  assert.strictEqual(lone.findings[0].offset, 0);
  assert.strictEqual(lone.truncated, false);
  assert.strictEqual(lone.highest_severity, "high");
  assert.strictEqual(lone.source_length, 1);
  const mixed = await scan.scanText("a\uD800b", null, "auto");
  assert.strictEqual(mixed.total, 1);
  assert.strictEqual(mixed.findings[0].index, 1);
  assert.strictEqual(mixed.source_length, 3);
  process.stdout.write("ok\n");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

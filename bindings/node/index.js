"use strict";

const fs = require("fs");
const path = require("path");
const loader = require("./scan_wasm.js");
const fallback = require("./scan.js");

let ready = null;

function wasmPath() {
  return path.join(__dirname, "fuckmark_scan.wasm");
}

async function createScanEngine() {
  globalThis.FuckMarkScan = fallback;
  const bytes = fs.readFileSync(wasmPath());
  return loader.loadFuckMarkScanWasm(bytes);
}

function getEngine() {
  if (!ready) {
    ready = createScanEngine();
  }
  return ready;
}

async function scanText(text, categories, language) {
  const api = await getEngine();
  return api.scanText(text, categories, language);
}

async function cleanText(text, categories) {
  const api = await getEngine();
  return api.cleanText(text, categories);
}

async function autofixTrojanSource(text) {
  const api = await getEngine();
  return api.autofixTrojanSource(text);
}

async function classify(codepoint) {
  const api = await getEngine();
  return api.classify(codepoint);
}

module.exports = {
  SCAN_ALGORITHM_VERSION: "fuckmark-hidden-scan-v1",
  createScanEngine,
  getEngine,
  scanText,
  cleanText,
  autofixTrojanSource,
  classify,
  fallback,
};

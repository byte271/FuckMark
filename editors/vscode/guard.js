"use strict";

const {
  DEFAULT_SECURITY_CATEGORIES,
  SCAN_ALGORITHM_VERSION,
  scanText,
  cleanText,
} = require("./scan.js");

function extractTagPayload(text) {
  let out = "";
  let offset = 0;
  while (offset < text.length) {
    const cp = text.codePointAt(offset);
    const length = cp > 0xffff ? 2 : 1;
    if (cp >= 0xe0020 && cp <= 0xe007e) {
      out += String.fromCharCode(cp - 0xe0000);
    }
    offset += length;
  }
  return out;
}

function protect(text, categories) {
  const selected = categories || DEFAULT_SECURITY_CATEGORIES;
  return cleanText(text, selected).cleaned;
}

function inspect(text, categories) {
  const selected = categories || DEFAULT_SECURITY_CATEGORIES;
  const result = scanText(text, selected);
  const { cleaned, removed } = cleanText(text, selected);
  return {
    algorithmVersion: SCAN_ALGORITHM_VERSION,
    cleaned,
    removed,
    total: result.total,
    counts: result.counts,
    tagPayload: extractTagPayload(text),
  };
}

function walk(value, categories) {
  if (typeof value === "string") {
    return protect(value, categories);
  }
  if (Array.isArray(value)) {
    return value.map((item) => walk(item, categories));
  }
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value)) {
      out[key] = walk(value[key], categories);
    }
    return out;
  }
  return value;
}

module.exports = {
  extractTagPayload,
  inspect,
  protect,
  walk,
};

"use strict";

const WASM_CATEGORIES = [
  "bidi_control",
  "zero_width",
  "variation_selector",
  "tag",
  "enclosing_mark",
  "line_separator",
  "deprecated",
  "format",
  "control",
  "private_use",
  "noncharacter",
  "surrogate",
];

function utf16Offsets(text) {
  const map = [];
  let offset = 0;
  while (offset < text.length) {
    map.push(offset);
    const cp = text.codePointAt(offset);
    offset += cp > 0xffff ? 2 : 1;
  }
  return map;
}

function codepointToken(cp) {
  return "U+" + Number(cp).toString(16).toUpperCase().padStart(4, "0");
}

function hasLoneSurrogate(text) {
  const source = String(text || "");
  for (let index = 0; index < source.length; index += 1) {
    const unit = source.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      if (index + 1 >= source.length) return true;
      const next = source.charCodeAt(index + 1);
      if (next < 0xdc00 || next > 0xdfff) return true;
      index += 1;
      continue;
    }
    if (unit >= 0xdc00 && unit <= 0xdfff) return true;
  }
  return false;
}

function encodeCategories(categories) {
  if (categories == null) return "*";
  if (Array.isArray(categories)) return categories.join(",");
  return String(categories);
}

const SEVERITY_RANK = { info: 0, medium: 1, high: 2, critical: 3 };

function codePointCount(text) {
  let count = 0;
  for (let offset = 0; offset < text.length; ) {
    const cp = text.codePointAt(offset);
    offset += cp > 0xffff ? 2 : 1;
    count += 1;
  }
  return count;
}

function utf16OffsetToIndex(text, offset) {
  let index = 0;
  let pos = 0;
  while (pos < offset && pos < text.length) {
    const cp = text.codePointAt(pos);
    pos += cp > 0xffff ? 2 : 1;
    index += 1;
  }
  return index;
}

function peakSeverity(findings) {
  let peak = "";
  for (const finding of findings) {
    if ((SEVERITY_RANK[finding.severity] || -1) > (SEVERITY_RANK[peak] || -1)) {
      peak = finding.severity;
    }
  }
  return peak;
}

function normalizeScanResult(source, result) {
  const findings = (result.findings || []).map((finding) => {
    const offset = finding.offset != null ? finding.offset : 0;
    const length = finding.length != null ? finding.length : finding.codepoint > 0xffff ? 2 : 1;
    const index = finding.index != null ? finding.index : utf16OffsetToIndex(source, offset);
    return {
      offset,
      length,
      index,
      codepoint: finding.codepoint,
      category: finding.category,
      context: finding.context,
      severity: finding.severity,
      why: finding.why,
      remedy: finding.remedy,
    };
  });
  return {
    total: result.total || 0,
    counts: result.counts || {},
    findings,
    truncated: Boolean(result.truncated),
    highest_severity: result.highest_severity || peakSeverity(findings),
    source_length: result.source_length != null ? result.source_length : codePointCount(source),
  };
}

function writeUtf8(memory, alloc, bytes) {
  const ptr = alloc(bytes.length);
  new Uint8Array(memory.buffer, ptr, bytes.length).set(bytes);
  return ptr;
}

function readPackedJson(memory, dealloc, ptr) {
  const view = new DataView(memory.buffer, ptr, 4);
  const length = view.getUint32(0, true);
  const bytes = new Uint8Array(memory.buffer, ptr + 4, length);
  const text = new TextDecoder("utf-8").decode(bytes);
  dealloc(ptr, 4 + length);
  return JSON.parse(text);
}

function wrapInstance(instance, fallback) {
  const { memory, fm_alloc, fm_dealloc, fm_classify, fm_scan, fm_clean } = instance.exports;
  const encoder = new TextEncoder();

  function callScan(text, language, categories, maxFindings) {
    const textBytes = encoder.encode(String(text || ""));
    const langBytes = encoder.encode(String(language || "auto"));
    const catBytes = encoder.encode(encodeCategories(categories));
    const textPtr = writeUtf8(memory, fm_alloc, textBytes);
    const langPtr = writeUtf8(memory, fm_alloc, langBytes);
    const catPtr = writeUtf8(memory, fm_alloc, catBytes);
    const resultPtr = fm_scan(
      textPtr,
      textBytes.length,
      langPtr,
      langBytes.length,
      catPtr,
      catBytes.length,
      maxFindings == null ? -1 : maxFindings
    );
    fm_dealloc(textPtr, textBytes.length);
    fm_dealloc(langPtr, langBytes.length);
    fm_dealloc(catPtr, catBytes.length);
    return readPackedJson(memory, fm_dealloc, resultPtr);
  }

  function callClean(text, categories) {
    const textBytes = encoder.encode(String(text || ""));
    const catBytes = encoder.encode(encodeCategories(categories));
    const textPtr = writeUtf8(memory, fm_alloc, textBytes);
    const catPtr = writeUtf8(memory, fm_alloc, catBytes);
    const resultPtr = fm_clean(textPtr, textBytes.length, catPtr, catBytes.length);
    fm_dealloc(textPtr, textBytes.length);
    fm_dealloc(catPtr, catBytes.length);
    return readPackedJson(memory, fm_dealloc, resultPtr);
  }

  function scanText(text, categories, language) {
    const source = String(text || "");
    if (fallback && hasLoneSurrogate(source)) {
      return normalizeScanResult(source, fallback.scanText(source, categories, language));
    }
    const payload = callScan(source, language || "auto", categories, -1);
    const offsets = utf16Offsets(source);
    const findings = (payload.findings || []).map((finding) => {
      const offset = offsets[finding.index] || 0;
      const length = finding.codepoint > 0xffff ? 2 : 1;
      return {
        offset,
        length,
        index: finding.index,
        codepoint: finding.codepoint,
        category: finding.category,
        context: finding.context,
        severity: finding.severity,
        why: finding.why,
        remedy: finding.remedy,
      };
    });
    return {
      total: payload.total || 0,
      counts: payload.counts || {},
      findings,
      truncated: Boolean(payload.truncated),
      highest_severity: payload.highest_severity || "",
      source_length: payload.source_length || 0,
    };
  }

  function cleanText(text, categories) {
    const source = String(text || "");
    if (fallback && hasLoneSurrogate(source)) {
      return fallback.cleanText(source, categories);
    }
    return callClean(source, categories);
  }

  const api = Object.assign({}, fallback || {}, {
    engine: "wasm",
    SCAN_ALGORITHM_VERSION: "fuckmark-hidden-scan-v1",
    classify(cp) {
      const index = fm_classify(cp >>> 0);
      return index < 0 ? null : WASM_CATEGORIES[index];
    },
    scanText,
    cleanText,
    autofixTrojanSource(text) {
      return cleanText(text, ["bidi_control"]);
    },
    codepointToken: (fallback && fallback.codepointToken) || codepointToken,
    hasLoneSurrogate,
    encodeCategories,
  });
  return api;
}

async function instantiateWasm(source) {
  let buffer;
  if (source instanceof ArrayBuffer) {
    buffer = source;
  } else if (ArrayBuffer.isView(source)) {
    buffer = source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength);
  } else if (typeof source === "string") {
    const response = await fetch(source);
    if (!response.ok) {
      throw new Error("fuckmark_scan.wasm missing");
    }
    buffer = await response.arrayBuffer();
  } else {
    throw new Error("wasm source required");
  }
  const result = await WebAssembly.instantiate(buffer, {});
  return result.instance;
}

async function loadFuckMarkScanWasm(source) {
  const fallback = typeof globalThis !== "undefined" ? globalThis.FuckMarkScan : undefined;
  const instance = await instantiateWasm(source || "fuckmark_scan.wasm");
  const api = wrapInstance(instance, fallback);
  if (typeof globalThis !== "undefined") {
    globalThis.FuckMarkScan = api;
    globalThis.FuckMarkScanWasm = api;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports.loadFuckMarkScanWasm = loadFuckMarkScanWasm;
    module.exports.wrapInstance = wrapInstance;
  }
  return api;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports.loadFuckMarkScanWasm = loadFuckMarkScanWasm;
  module.exports.wrapInstance = wrapInstance;
  module.exports.WASM_CATEGORIES = WASM_CATEGORIES;
  module.exports.hasLoneSurrogate = hasLoneSurrogate;
  module.exports.encodeCategories = encodeCategories;
  module.exports.normalizeScanResult = normalizeScanResult;
}
if (typeof globalThis !== "undefined") {
  globalThis.loadFuckMarkScanWasm = loadFuckMarkScanWasm;
}

"use strict";

function getScan() {
  if (typeof globalThis !== "undefined" && globalThis.FuckMarkScan) {
    return globalThis.FuckMarkScan;
  }
  if (typeof module !== "undefined" && module.exports && typeof require === "function") {
    return require("./scan.js");
  }
  throw new Error("FuckMark scan.js is not loaded");
}

const SKIP_TAGS = {
  SCRIPT: true,
  STYLE: true,
  NOSCRIPT: true,
  IFRAME: true,
  OBJECT: true,
  EMBED: true,
  TEXTAREA: true,
};

function isSkipTag(name) {
  return Boolean(SKIP_TAGS[String(name || "").toUpperCase()]);
}

const ZWJ = 0x200d;

function codePointBefore(text, offset) {
  if (offset <= 0) return -1;
  if (offset >= 2) {
    const cp = text.codePointAt(offset - 2);
    if (cp > 0xffff) return cp;
  }
  return text.codePointAt(offset - 1);
}

function codePointAfter(text, offset, length) {
  const next = offset + length;
  if (next >= text.length) return -1;
  return text.codePointAt(next);
}

function isEmojiClusterNeighbor(cp) {
  if (cp < 0 || cp === ZWJ) return false;
  if (cp >= 0xfe00 && cp <= 0xfe0f) return true;
  if (cp >= 0xe0100 && cp <= 0xe01ef) return true;
  if (cp >= 0x1f1e6 && cp <= 0x1f1ff) return true;
  if (cp >= 0x1f000 && cp <= 0x1faff) return true;
  if (cp >= 0x2600 && cp <= 0x27bf) return true;
  return [0x00a9, 0x00ae, 0x203c, 0x2049, 0x2122, 0x2139, 0x3030, 0x303d, 0x3297, 0x3299].includes(cp);
}

function isKeptEmojiJoiner(text, finding) {
  if (!finding || finding.category !== "zero_width" || finding.codepoint !== ZWJ) return false;
  const length = finding.length || 1;
  const prev = codePointBefore(text, finding.offset);
  const next = codePointAfter(text, finding.offset, length);
  return isEmojiClusterNeighbor(prev) && isEmojiClusterNeighbor(next);
}

function shouldStripFinding(finding, text) {
  const scan = getScan();
  const security = new Set(scan.DEFAULT_SECURITY_CATEGORIES);
  if (!finding || !security.has(finding.category)) return false;
  if (isKeptEmojiJoiner(text, finding)) return false;
  if (finding.category === "variation_selector" && finding.severity === "info") return false;
  return true;
}

function cleanForPaste(text) {
  const scan = getScan();
  const source = String(text || "");
  const result = scan.scanText(source, null, "auto");
  const spans = [];
  for (const finding of result.findings) {
    if (!shouldStripFinding(finding, source)) continue;
    spans.push({ start: finding.offset, end: finding.offset + finding.length });
  }
  spans.sort((a, b) => a.start - b.start);
  let out = "";
  let cursor = 0;
  let removed = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    out += source.slice(cursor, span.start);
    cursor = span.end;
    removed += 1;
  }
  out += source.slice(cursor);
  return { cleaned: out, removed, total: result.total, findings: result.findings };
}

function scanString(text, language) {
  return getScan().scanText(String(text || ""), null, language || "auto");
}

function highestSeverity(findings) {
  const rank = { info: 1, medium: 2, high: 3, critical: 4 };
  let highest = "";
  for (const finding of findings || []) {
    if ((rank[finding.severity] || 0) > (rank[highest] || 0)) highest = finding.severity;
  }
  return highest;
}

const FuckMarkPage = {
  SKIP_TAGS,
  isSkipTag,
  shouldStripFinding,
  isKeptEmojiJoiner,
  cleanForPaste,
  scanString,
  highestSeverity,
  getScan,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = FuckMarkPage;
}
if (typeof globalThis !== "undefined") {
  globalThis.FuckMarkPage = FuckMarkPage;
}

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

function shouldStripFinding(finding) {
  const scan = getScan();
  const security = new Set(scan.DEFAULT_SECURITY_CATEGORIES);
  if (!finding || !security.has(finding.category)) return false;
  return finding.severity !== "info";
}

function cleanForPaste(text) {
  const scan = getScan();
  const result = scan.scanText(String(text || ""), null, "auto");
  const spans = [];
  for (const finding of result.findings) {
    if (!shouldStripFinding(finding)) continue;
    spans.push({ start: finding.offset, end: finding.offset + finding.length });
  }
  spans.sort((a, b) => a.start - b.start);
  let out = "";
  let cursor = 0;
  let removed = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    out += text.slice(cursor, span.start);
    cursor = span.end;
    removed += 1;
  }
  out += text.slice(cursor);
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

// Faithful JavaScript port of fuckmark-hidden-scan-v1 (fuckmark/product/scan.py).
// Kept in lockstep with the Python engine by tests/test_vscode_scanner_parity.py.

"use strict";

const SCAN_ALGORITHM_VERSION = "fuckmark-hidden-scan-v1";

const CATEGORY_BIDI_CONTROL = "bidi_control";
const CATEGORY_ZERO_WIDTH = "zero_width";
const CATEGORY_VARIATION_SELECTOR = "variation_selector";
const CATEGORY_TAG = "tag";
const CATEGORY_ENCLOSING_MARK = "enclosing_mark";
const CATEGORY_LINE_SEPARATOR = "line_separator";
const CATEGORY_DEPRECATED = "deprecated";
const CATEGORY_FORMAT = "format";
const CATEGORY_CONTROL = "control";
const CATEGORY_PRIVATE_USE = "private_use";
const CATEGORY_NONCHARACTER = "noncharacter";
const CATEGORY_SURROGATE = "surrogate";

const SCAN_CATEGORIES = [
  CATEGORY_BIDI_CONTROL,
  CATEGORY_ZERO_WIDTH,
  CATEGORY_VARIATION_SELECTOR,
  CATEGORY_TAG,
  CATEGORY_ENCLOSING_MARK,
  CATEGORY_LINE_SEPARATOR,
  CATEGORY_DEPRECATED,
  CATEGORY_FORMAT,
  CATEGORY_CONTROL,
  CATEGORY_PRIVATE_USE,
  CATEGORY_NONCHARACTER,
  CATEGORY_SURROGATE,
];

const CATEGORY_DESCRIPTIONS = {
  [CATEGORY_BIDI_CONTROL]: "bidirectional override/isolate (Trojan Source reordering)",
  [CATEGORY_ZERO_WIDTH]: "zero-width or invisible spacing character",
  [CATEGORY_VARIATION_SELECTOR]: "variation selector (glyph/steganography carrier)",
  [CATEGORY_TAG]: "Unicode tag character (hidden text / prompt-injection smuggling)",
  [CATEGORY_ENCLOSING_MARK]: "enclosing combining mark (alters surrounding glyph)",
  [CATEGORY_LINE_SEPARATOR]: "line/paragraph separator (breaks parsers, invisible)",
  [CATEGORY_DEPRECATED]: "deprecated format control or interlinear annotation",
  [CATEGORY_FORMAT]: "general Unicode format control (Cf)",
  [CATEGORY_CONTROL]: "C0/C1 control character",
  [CATEGORY_PRIVATE_USE]: "private-use codepoint (renderer-defined)",
  [CATEGORY_NONCHARACTER]: "Unicode noncharacter or unassigned codepoint",
  [CATEGORY_SURROGATE]: "lone surrogate codepoint",
};

const DEFAULT_SECURITY_CATEGORIES = [
  CATEGORY_BIDI_CONTROL,
  CATEGORY_ZERO_WIDTH,
  CATEGORY_TAG,
  CATEGORY_CONTROL,
  CATEGORY_NONCHARACTER,
  CATEGORY_SURROGATE,
];

const ALLOWED_WHITESPACE = new Set([0x09, 0x0a, 0x0d, 0x20]);

function inRange(cp, lo, hi) {
  return cp >= lo && cp <= hi;
}

const BIDI_CONTROL = new Set([0x061c, 0x200e, 0x200f]);
for (let cp = 0x202a; cp <= 0x202e; cp += 1) BIDI_CONTROL.add(cp);
for (let cp = 0x2066; cp <= 0x2069; cp += 1) BIDI_CONTROL.add(cp);

const DEPRECATED = new Set([0xfff9, 0xfffa, 0xfffb]);
for (let cp = 0x206a; cp <= 0x206f; cp += 1) DEPRECATED.add(cp);

const ZERO_WIDTH = new Set([
  0x00ad, 0x034f, 0x115f, 0x1160, 0x17b4, 0x17b5, 0x180e, 0x200b, 0x200c,
  0x200d, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x3164, 0xfeff, 0xffa0,
]);

function isVariationSelector(cp) {
  return inRange(cp, 0xfe00, 0xfe0f) || inRange(cp, 0xe0100, 0xe01ef);
}

function isTag(cp) {
  return inRange(cp, 0xe0000, 0xe007f);
}

function isNoncharacter(cp) {
  if (inRange(cp, 0xfdd0, 0xfdef)) return true;
  const low = cp & 0xffff;
  return low === 0xfffe || low === 0xffff;
}

function isEnclosingMark(cp) {
  // Unicode general category Me. Enumerated to avoid a runtime Unicode DB.
  return (
    inRange(cp, 0x0488, 0x0489) ||
    cp === 0x1abe ||
    inRange(cp, 0x20dd, 0x20e0) ||
    inRange(cp, 0x20e2, 0x20e4) ||
    inRange(cp, 0xa670, 0xa672)
  );
}

function isControl(cp) {
  return inRange(cp, 0x00, 0x1f) || inRange(cp, 0x7f, 0x9f);
}

function isLineSeparator(cp) {
  return cp === 0x2028 || cp === 0x2029;
}

// General category Cf ranges (Unicode 15-era), excluding codepoints already
// classified above. Mirrors what unicodedata.category returns as "Cf".
const FORMAT_RANGES = [
  [0x0600, 0x0605],
  [0x06dd, 0x06dd],
  [0x070f, 0x070f],
  [0x0890, 0x0891],
  [0x08e2, 0x08e2],
  [0x110bd, 0x110bd],
  [0x110cd, 0x110cd],
  [0x13430, 0x1343f],
  [0x1bca0, 0x1bca3],
  [0x1d173, 0x1d17a],
];

function isFormat(cp) {
  for (const [lo, hi] of FORMAT_RANGES) {
    if (inRange(cp, lo, hi)) return true;
  }
  return false;
}

function isPrivateUse(cp) {
  return (
    inRange(cp, 0xe000, 0xf8ff) ||
    inRange(cp, 0xf0000, 0xffffd) ||
    inRange(cp, 0x100000, 0x10fffd)
  );
}

function classify(cp) {
  if (ALLOWED_WHITESPACE.has(cp)) return null;
  if (BIDI_CONTROL.has(cp)) return CATEGORY_BIDI_CONTROL;
  if (DEPRECATED.has(cp)) return CATEGORY_DEPRECATED;
  if (ZERO_WIDTH.has(cp)) return CATEGORY_ZERO_WIDTH;
  if (isVariationSelector(cp)) return CATEGORY_VARIATION_SELECTOR;
  if (isTag(cp)) return CATEGORY_TAG;
  if (isNoncharacter(cp)) return CATEGORY_NONCHARACTER;
  if (cp >= 0xd800 && cp <= 0xdfff) return CATEGORY_SURROGATE;
  if (isEnclosingMark(cp)) return CATEGORY_ENCLOSING_MARK;
  if (isLineSeparator(cp)) return CATEGORY_LINE_SEPARATOR;
  if (isControl(cp)) return CATEGORY_CONTROL;
  if (isFormat(cp)) return CATEGORY_FORMAT;
  if (isPrivateUse(cp)) return CATEGORY_PRIVATE_USE;
  return null;
}

function codepointToken(cp) {
  return "U+" + cp.toString(16).toUpperCase().padStart(4, "0");
}

function scanText(text, categories) {
  const selected = categories ? new Set(categories) : null;
  const counts = {};
  const findings = [];
  let total = 0;
  let offset = 0;
  while (offset < text.length) {
    const cp = text.codePointAt(offset);
    const length = cp > 0xffff ? 2 : 1;
    const category = classify(cp);
    if (category !== null && (selected === null || selected.has(category))) {
      total += 1;
      counts[category] = (counts[category] || 0) + 1;
      findings.push({ offset, length, codepoint: cp, category });
    }
    offset += length;
  }
  return { total, counts, findings };
}

function cleanText(text, categories) {
  const selected = categories ? new Set(categories) : null;
  let out = "";
  let removed = 0;
  let offset = 0;
  while (offset < text.length) {
    const cp = text.codePointAt(offset);
    const length = cp > 0xffff ? 2 : 1;
    const category = classify(cp);
    if (category !== null && (selected === null || selected.has(category))) {
      removed += 1;
    } else {
      out += text.slice(offset, offset + length);
    }
    offset += length;
  }
  return { cleaned: out, removed };
}

module.exports = {
  SCAN_ALGORITHM_VERSION,
  SCAN_CATEGORIES,
  CATEGORY_DESCRIPTIONS,
  DEFAULT_SECURITY_CATEGORIES,
  classify,
  codepointToken,
  scanText,
  cleanText,
};

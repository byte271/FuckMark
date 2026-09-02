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

const TROJAN_SOURCE_CATEGORIES = [CATEGORY_BIDI_CONTROL];

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

function isEmojiish(cp) {
  if (cp < 0) return false;
  if (cp >= 0x1f1e6 && cp <= 0x1f1ff) return true;
  if (cp >= 0x1f000 && cp <= 0x1faff) return true;
  if (cp >= 0x2600 && cp <= 0x27bf) return true;
  return cp === 0x200d || [0x00a9, 0x00ae, 0x203c, 0x2049, 0x2122, 0x2139, 0x3030, 0x303d, 0x3297, 0x3299].includes(cp);
}

function isIdentChar(ch) {
  return ch === "_" || /\p{L}|\p{N}/u.test(ch);
}

function neighborBefore(text, offset) {
  if (offset <= 0) return { cp: -1, ch: "" };
  if (offset >= 2) {
    const cp = text.codePointAt(offset - 2);
    if (cp > 0xffff) return { cp, ch: String.fromCodePoint(cp) };
  }
  const cp = text.codePointAt(offset - 1);
  return { cp, ch: String.fromCodePoint(cp) };
}

function neighborAfter(text, offset, length) {
  const nextIndex = offset + length;
  if (nextIndex >= text.length) return { cp: -1, ch: "" };
  const cp = text.codePointAt(nextIndex);
  return { cp, ch: String.fromCodePoint(cp) };
}

const LANGUAGE_ALIASES = {
  auto: "auto",
  javascript: "javascript",
  js: "javascript",
  ts: "javascript",
  typescript: "javascript",
  jsx: "javascript",
  tsx: "javascript",
  c: "c",
  h: "c",
  cc: "c",
  cpp: "c",
  cxx: "c",
  java: "c",
  go: "c",
  rs: "c",
  rust: "c",
  cs: "c",
  css: "c",
  jsonc: "c",
  python: "python",
  py: "python",
  pyi: "python",
  hash: "python",
  sh: "python",
  bash: "python",
  zsh: "python",
  shell: "python",
  shellscript: "python",
  yaml: "python",
  yml: "python",
  rb: "python",
  ruby: "python",
  toml: "python",
  html: "html",
  htm: "html",
  xml: "html",
  sql: "sql",
};

function normalizeLanguage(language) {
  if (!language) return "auto";
  const key = String(language).trim().toLowerCase();
  return LANGUAGE_ALIASES[key] || "auto";
}

function slashComments(language) {
  return language === "auto" || language === "javascript" || language === "c" || language === "sql";
}

function blockComments(language) {
  return slashComments(language);
}

function hashComments(language) {
  return language === "python";
}

function sqlLineComments(language) {
  return language === "sql";
}

function htmlComments(language) {
  return language === "html";
}

function sourceRoles(text, language) {
  const lang = normalizeLanguage(language);
  const roles = new Array(text.length).fill("code");
  let index = 0;
  let inString = "";
  let escape = false;
  while (index < text.length) {
    const ch = text[index];
    if (inString) {
      roles[index] = "string";
      if (escape) {
        escape = false;
        index += 1;
        continue;
      }
      if (ch === "\\" && index + 1 < text.length) {
        escape = true;
        index += 1;
        continue;
      }
      if (ch === inString) inString = "";
      index += 1;
      continue;
    }
    const pair = text.slice(index, index + 2);
    if (slashComments(lang) && pair === "//" && !(index > 0 && text[index - 1] === ":")) {
      let cursor = index;
      while (cursor < text.length && text[cursor] !== "\n" && text[cursor] !== "\r") {
        roles[cursor] = "comment";
        cursor += 1;
      }
      index = cursor;
      continue;
    }
    if (sqlLineComments(lang) && pair === "--") {
      let cursor = index;
      while (cursor < text.length && text[cursor] !== "\n" && text[cursor] !== "\r") {
        roles[cursor] = "comment";
        cursor += 1;
      }
      index = cursor;
      continue;
    }
    if (blockComments(lang) && pair === "/*") {
      const close = text.indexOf("*/", index + 2);
      const stop = close >= 0 ? close + 2 : text.length;
      for (let cursor = index; cursor < stop; cursor += 1) roles[cursor] = "comment";
      index = stop;
      continue;
    }
    if (hashComments(lang) && ch === "#") {
      let cursor = index;
      while (cursor < text.length && text[cursor] !== "\n" && text[cursor] !== "\r") {
        roles[cursor] = "comment";
        cursor += 1;
      }
      index = cursor;
      continue;
    }
    if (htmlComments(lang) && text.slice(index, index + 4) === "<!--") {
      const close = text.indexOf("-->", index + 4);
      const stop = close >= 0 ? close + 3 : text.length;
      for (let cursor = index; cursor < stop; cursor += 1) roles[cursor] = "comment";
      index = stop;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") {
      inString = ch;
      roles[index] = "string";
      index += 1;
      continue;
    }
    index += 1;
  }
  return roles;
}

function classifyContext(text, offset, role, category) {
  const length = text.codePointAt(offset) > 0xffff ? 2 : 1;
  const prev = neighborBefore(text, offset);
  const next = neighborAfter(text, offset, length);
  if ((role === "comment" || role === "string") && category === CATEGORY_BIDI_CONTROL) {
    return role;
  }
  if (
    isEmojiish(prev.cp) ||
    isEmojiish(next.cp) ||
    (prev.cp >= 0xfe00 && prev.cp <= 0xfe0f) ||
    (next.cp >= 0xfe00 && next.cp <= 0xfe0f)
  ) {
    return "emoji";
  }
  if (role === "comment") return "comment";
  if (role === "string") return "string";
  if (isIdentChar(prev.ch) || isIdentChar(next.ch)) return "identifier";
  return "prose";
}

function scoreSeverity(category, context) {
  if (category === CATEGORY_TAG) return "critical";
  if (category === CATEGORY_BIDI_CONTROL) {
    if (context === "identifier" || context === "comment" || context === "string") return "critical";
    return "high";
  }
  if (category === CATEGORY_ZERO_WIDTH) {
    if (context === "emoji") return "info";
    if (context === "identifier") return "high";
    return "medium";
  }
  if (category === CATEGORY_VARIATION_SELECTOR) return context === "emoji" ? "info" : "medium";
  if (category === CATEGORY_CONTROL || category === CATEGORY_NONCHARACTER || category === CATEGORY_SURROGATE) {
    return "high";
  }
  return "medium";
}

function explainFinding(category, context, severity) {
  if (category === CATEGORY_BIDI_CONTROL && context === "identifier") {
    return {
      why: "Bidirectional override sits inside an identifier, so the glyphs can read differently than the bytes (Trojan Source).",
      remedy: "Strip the bidi control and keep the identifier left-to-right.",
    };
  }
  if (category === CATEGORY_BIDI_CONTROL && context === "comment") {
    return {
      why: "Bidirectional override sits inside a comment, so commented-out code can appear to run (Trojan Source commenting-out).",
      remedy: "Strip the bidi control from the comment.",
    };
  }
  if (category === CATEGORY_BIDI_CONTROL && context === "string") {
    return {
      why: "Bidirectional override sits inside a string, so the literal can appear to close early (Trojan Source stretched-string).",
      remedy: "Strip the bidi control from the string.",
    };
  }
  if (category === CATEGORY_BIDI_CONTROL) {
    return {
      why: "Bidirectional override can reorder nearby glyphs (Trojan Source class, CVE-2021-42574).",
      remedy: "Strip U+202A-U+202E / U+2066-U+2069 and rewrite the text left-to-right.",
    };
  }
  if (category === CATEGORY_TAG) {
    return {
      why: "Unicode tag characters encode a second ASCII string that models read and humans do not.",
      remedy: "Strip U+E0020-U+E007F; inspect tag_payload for the smuggled text.",
    };
  }
  if (category === CATEGORY_ZERO_WIDTH && context === "emoji") {
    return {
      why: "Zero-width joiner or invisible mark inside an emoji cluster; usually a legitimate emoji sequence.",
      remedy: "Leave emoji ZWJ sequences unless you are sanitizing for a security boundary.",
    };
  }
  if (category === CATEGORY_ZERO_WIDTH && context === "identifier") {
    return {
      why: "Zero-width character splits an identifier, breaking search and some compilers while looking unchanged.",
      remedy: "Strip the zero-width character from the identifier.",
    };
  }
  if (category === CATEGORY_ZERO_WIDTH) {
    return {
      why: "Invisible spacing or joining character that changes the byte stream without changing the glyphs.",
      remedy: "Strip the zero-width character.",
    };
  }
  if (category === CATEGORY_VARIATION_SELECTOR && context === "emoji") {
    return {
      why: "Variation selector tunes an emoji glyph; usually benign.",
      remedy: "Keep emoji variation selectors unless you are stripping all hidden marks.",
    };
  }
  if (severity === "high") {
    return {
      why: "Hidden or non-text codepoint that should not appear in ordinary source or prompts.",
      remedy: "Strip the character.",
    };
  }
  return {
    why: CATEGORY_DESCRIPTIONS[category] || "Hidden or format codepoint that is invisible or renderer-defined.",
    remedy: "Strip the character if this text crosses a trust boundary.",
  };
}

function scanText(text, categories, language) {
  const selected = categories ? new Set(categories) : null;
  const roles = sourceRoles(text, language);
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
      const context = classifyContext(text, offset, roles[offset] || "code", category);
      const severity = scoreSeverity(category, context);
      const explained = explainFinding(category, context, severity);
      findings.push({
        offset,
        length,
        codepoint: cp,
        category,
        context,
        severity,
        why: explained.why,
        remedy: explained.remedy,
      });
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

function autofixTrojanSource(text) {
  return cleanText(text, TROJAN_SOURCE_CATEGORIES);
}

function languageFromDocumentId(languageId) {
  return normalizeLanguage(languageId);
}

const LANGUAGE_BY_SUFFIX = {
  ".js": "javascript",
  ".mjs": "javascript",
  ".cjs": "javascript",
  ".ts": "javascript",
  ".jsx": "javascript",
  ".tsx": "javascript",
  ".c": "c",
  ".h": "c",
  ".hh": "c",
  ".cc": "c",
  ".cpp": "c",
  ".cxx": "c",
  ".java": "c",
  ".go": "c",
  ".rs": "c",
  ".cs": "c",
  ".css": "c",
  ".py": "python",
  ".pyi": "python",
  ".sh": "python",
  ".bash": "python",
  ".zsh": "python",
  ".yaml": "python",
  ".yml": "python",
  ".rb": "python",
  ".toml": "python",
  ".html": "html",
  ".htm": "html",
  ".xml": "html",
  ".sql": "sql",
};

function languageFromPath(path) {
  const name = String(path || "");
  const slash = Math.max(name.lastIndexOf("/"), name.lastIndexOf("\\"));
  const base = slash >= 0 ? name.slice(slash + 1) : name;
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return "auto";
  const suffix = base.slice(dot).toLowerCase();
  return LANGUAGE_BY_SUFFIX[suffix] || "auto";
}

const FuckMarkScan = {
  SCAN_ALGORITHM_VERSION,
  SCAN_CATEGORIES,
  CATEGORY_DESCRIPTIONS,
  DEFAULT_SECURITY_CATEGORIES,
  TROJAN_SOURCE_CATEGORIES,
  classify,
  classifyContext,
  scoreSeverity,
  normalizeLanguage,
  languageFromDocumentId,
  languageFromPath,
  sourceRoles,
  codepointToken,
  scanText,
  cleanText,
  autofixTrojanSource,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = FuckMarkScan;
}
if (typeof globalThis !== "undefined") {
  globalThis.FuckMarkScan = FuckMarkScan;
}

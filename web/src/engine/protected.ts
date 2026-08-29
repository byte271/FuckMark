import { isIPv4Address, isIPv6Address } from "./ipv";
import {
  UText,
  bisectRight,
  collapseWs,
  findAll,
  isPyDigit,
  pyCasefold,
  searchFrom,
  type ReMatch,
} from "./text";

export const MAX_PROTECTED_ITEMS = 100_000;
const MAX_EXTENDED_PATH_SCAN = 4096;
const MAX_MARKDOWN_LABEL = 999;

const WORD = String.raw`\p{L}\p{N}_`;
const W = `[${WORD}]`;

const URL_RE = new RegExp(
  String.raw`(?<!${W})(?:(?:https?|ftps?|sftp|file|ws|wss|git|ssh|s3):\/\/|www\.)[^\s<>"']+`,
  "giu",
);
const BARE_DOMAIN_RE = new RegExp(
  String.raw`(?<![@\\/${WORD}.-])(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:xn--[A-Z0-9-]{2,59}|[A-Z]{2,63})(?![A-Z0-9-]))(?::\p{Nd}{1,5})?(?:[/?#][^\s<>"']*)?`,
  "giu",
);
const EMAIL_RE = new RegExp(
  `(?<![${WORD}.+-])[A-Z0-9.!#$%&'*+/=?^_\`${"{|}~-"}]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![${WORD}-])`,
  "giu",
);
const IPV4_RE = new RegExp(String.raw`(?<![\p{Nd}.])(?:\p{Nd}{1,3}\.){3}\p{Nd}{1,3}(?![\p{Nd}.])`, "gu");
const IPV6_TOKEN_RE = new RegExp(
  String.raw`(?<![0-9A-Fa-f:.])[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?:%[A-Za-z0-9._~-]+)?(?![0-9A-Za-z_.:~-])`,
  "gu",
);
const ISO_DATE_RE = new RegExp(String.raw`(?<!\p{Nd})\p{Nd}{4}-\p{Nd}{2}-\p{Nd}{2}(?!\p{Nd})`, "gu");
const MONTH = String.raw`(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)`;
const HWS = String.raw`[^\S\r\n]`;
const MONTH_FIRST_DATE_RE = new RegExp(
  String.raw`(?<!${W})${MONTH}${HWS}+\p{Nd}{1,2}(?:,)?${HWS}+\p{Nd}{4}(?!\p{Nd})`,
  "giu",
);
const DAY_FIRST_DATE_RE = new RegExp(
  String.raw`(?<!\p{Nd})\p{Nd}{1,2}${HWS}+${MONTH}${HWS}+\p{Nd}{4}(?!\p{Nd})`,
  "giu",
);
const SLASH_DATE_RE = new RegExp(
  String.raw`(?<!\p{Nd})(?:\p{Nd}{1,2}/\p{Nd}{1,2}/\p{Nd}{2,4}|\p{Nd}{4}/\p{Nd}{1,2}/\p{Nd}{1,2})(?!\p{Nd})`,
  "gu",
);
const NUMBER_BODY = String.raw`[-+]?(?:(?:\p{Nd}{1,3}(?:,\p{Nd}{3})+|\p{Nd}+)(?:\.\p{Nd}+)?|\.\p{Nd}+)(?:[eE][-+]?\p{Nd}+)?`;
const CURRENCY_CODE = String.raw`(?:USD|EUR|GBP|JPY|CNY|RMB)`;
const SIGNED_HWS = String.raw`(?:[-+]${HWS}*)?`;
const CURRENCY_RE = new RegExp(
  String.raw`(?<!${W})(?:${SIGNED_HWS}${CURRENCY_CODE}${HWS}*${NUMBER_BODY}|${SIGNED_HWS}[$€£¥]${HWS}*${NUMBER_BODY}|${NUMBER_BODY}${HWS}*${CURRENCY_CODE})(?!${W})`,
  "giu",
);
const PERCENT_RE = new RegExp(String.raw`(?<![${WORD}.])${NUMBER_BODY}${HWS}*%(?!${W})`, "giu");
const NUMBER_RE = new RegExp(String.raw`(?<![${WORD}.])${NUMBER_BODY}(?!${W})`, "gu");
const CLI_FLAG_RE = new RegExp(String.raw`(?<![${WORD}-])--?[A-Za-z][A-Za-z0-9-]*(?:=[^\s]+)?`, "gu");
const INLINE_CODE_RUN_RE = /`+/gu;
const BLANK_LINE_RE = /\r?\n[ \t]*\r?\n/gu;
const POSIX_PATH_RE = new RegExp(
  String.raw`(?<![${WORD}:])(?:~?/|\./|\.\./)(?:[A-Za-z0-9._~+@%-]+/)*[A-Za-z0-9._~+@%-]+/?`,
  "gu",
);
const RELATIVE_PATH_RE = new RegExp(
  String.raw`(?<![${WORD}:/])(?:[A-Za-z0-9._~+@%-]+/)+[A-Za-z0-9._~+@%-]*\.[A-Za-z][A-Za-z0-9]{0,11}/?`,
  "gu",
);
const EXTENSIONLESS_RELATIVE_PATH_RE = new RegExp(
  String.raw`(?<![${WORD}:/])(?:[A-Za-z0-9._~+@%-]+/){1,}[A-Za-z0-9._~+@%-]+/?`,
  "gu",
);
const FILENAME_TOKEN = String.raw`[A-Za-z0-9._~+@%'-]+`;
const SPACED_BASENAME = String.raw`(?:${FILENAME_TOKEN} ){1,3}${FILENAME_TOKEN}\.[A-Za-z][A-Za-z0-9]{0,11}`;
const WINDOWS_SPACED_FILE_RE = new RegExp(
  String.raw`(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)(?:${FILENAME_TOKEN}[/\\])*${SPACED_BASENAME}`,
  "giu",
);
const POSIX_SPACED_FILE_RE = new RegExp(
  String.raw`(?<![${WORD}:])(?:~?/|\./|\.\./)(?:${FILENAME_TOKEN}/)*${SPACED_BASENAME}`,
  "gu",
);
const HTML_TAG_RE = /<\/?[A-Za-z][A-Za-z0-9:-]{0,64}(?:\s[^<>\r\n]{0,1024})?\/?>/gu;
const HTML_ENTITY_RE = /&(?:[A-Za-z][A-Za-z0-9]{0,31}|#[0-9]{1,7}|#x[0-9A-Fa-f]{1,6});/gu;
const WINDOWS_PATH_RE = new RegExp(
  String.raw`(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)(?:[^\\/:*?"<>|\s]+[/\\])*[^\\/:*?"<>|\s]+`,
  "giu",
);
const WINDOWS_PREFIX_RE = /(?<![A-Z0-9_])(?:[A-Z]:[/\\]|\\\\[A-Z0-9._$-]+\\)/giu;
const POSIX_PREFIX_RE = new RegExp(String.raw`(?<![${WORD}:])(?:~?/|\./|\.\./)`, "gu");
const EXTENDED_BOUNDARY_RE = /[ \t]+(?=(?:https?:\/\/|www\.)|(?:\/|~\/|\.\/|\.\.\/)|[A-Za-z]:\\|\\\\|--?[A-Za-z])/giu;

const PROSE_SLASH_PAIRS = new Set([
  "and/or",
  "or/and",
  "either/or",
  "he/she",
  "she/he",
  "his/her",
  "her/his",
  "yes/no",
  "no/yes",
  "on/off",
  "off/on",
  "true/false",
  "false/true",
  "n/a",
  "w/o",
  "c/o",
  "a/k/a",
  "i/o",
  "input/output",
  "output/input",
  "read/write",
  "write/read",
  "high/low",
  "low/high",
  "left/right",
  "right/left",
  "up/down",
  "down/up",
  "plus/minus",
  "minus/plus",
]);

const PATH_ROOTS = new Set([
  "src",
  "lib",
  "bin",
  "sbin",
  "scripts",
  "tests",
  "docs",
  "dist",
  "tmp",
  "temp",
  "usr",
  "var",
  "opt",
  "etc",
  "include",
  "vendor",
  "pkg",
  "pkgs",
  "tools",
  "assets",
  "static",
  "cmake",
  "modules",
  "third_party",
  "node_modules",
]);

const MONTH_NUMBERS: Record<string, number> = {
  jan: 1,
  january: 1,
  feb: 2,
  february: 2,
  mar: 3,
  march: 3,
  apr: 4,
  april: 4,
  may: 5,
  jun: 6,
  june: 6,
  jul: 7,
  july: 7,
  aug: 8,
  august: 8,
  sep: 9,
  sept: 9,
  september: 9,
  oct: 10,
  october: 10,
  nov: 11,
  november: 11,
  dec: 12,
  december: 12,
};

export type SpanKind =
  | "url"
  | "email"
  | "ipv4"
  | "ipv6"
  | "number"
  | "date"
  | "currency"
  | "percentage"
  | "code"
  | "markdown_destination"
  | "markdown_label"
  | "posix_path"
  | "windows_path"
  | "cli_flag";

export type RawSpan = [number, number, SpanKind];

export function appendSpan(raw: RawSpan[], start: number, end: number, kind: SpanKind): void {
  if (end <= start) return;
  if (raw.length >= MAX_PROTECTED_ITEMS) {
    throw new Error("protected span extraction exceeded item limit");
  }
  raw.push([start, end, kind]);
}

export function isEscaped(text: UText, index: number): boolean {
  let count = 0;
  let cursor = index - 1;
  while (cursor >= 0 && text.at(cursor) === "\\") {
    count += 1;
    cursor -= 1;
  }
  return count % 2 === 1;
}

export function lineEnd(text: UText, start: number): number {
  const end = text.indexOf("\n", start);
  return end < 0 ? text.length : end;
}

export function lineStarts(text: UText): number[] {
  const starts = [0];
  let index = 0;
  while (index < text.length) {
    const character = text.at(index);
    if (character === "\r") {
      index += 1;
      if (index < text.length && text.at(index) === "\n") index += 1;
      starts.push(index);
      continue;
    }
    if (character === "\n") {
      starts.push(index + 1);
      index += 1;
      continue;
    }
    index += 1;
  }
  return starts;
}

export function lineContentEnd(text: UText, lineStart: number, nextLineStart: number): number {
  let end = nextLineStart;
  if (end > lineStart && text.at(end - 1) === "\n") {
    end -= 1;
    if (end > lineStart && text.at(end - 1) === "\r") end -= 1;
    return end;
  }
  if (end > lineStart && text.at(end - 1) === "\r") return end - 1;
  return end;
}

function skipSpacesTabs(text: UText, index: number, limit?: number): number {
  const end = limit === undefined ? text.length : limit;
  while (index < end && (text.at(index) === " " || text.at(index) === "\t")) index += 1;
  return index;
}

function skipOneLineEnding(text: UText, index: number): number {
  if (index < text.length && text.at(index) === "\r") {
    index += 1;
    if (index < text.length && text.at(index) === "\n") index += 1;
    return index;
  }
  if (index < text.length && text.at(index) === "\n") return index + 1;
  return index;
}

function skipReferenceWhitespace(text: UText, index: number): number {
  index = skipSpacesTabs(text, index);
  const advanced = skipOneLineEnding(text, index);
  if (advanced !== index) index = skipSpacesTabs(text, advanced);
  return index;
}

function trimTerminalPunctuation(text: UText, start: number, end: number): [number, number] {
  while (end > start && ".,;:!?".includes(text.at(end - 1))) end -= 1;
  if (end <= start) return [start, end];
  const counts: Record<string, number> = { "(": 0, ")": 0, "[": 0, "]": 0, "{": 0, "}": 0 };
  for (let i = start; i < end; i += 1) {
    const ch = text.at(i);
    if (ch in counts) counts[ch] += 1;
  }
  const openingFor: Record<string, string> = { ")": "(", "]": "[", "}": "{" };
  while (end > start) {
    const closing = text.at(end - 1);
    const opening = openingFor[closing];
    if (opening === undefined || counts[closing] <= counts[opening]) break;
    counts[closing] -= 1;
    end -= 1;
  }
  return [start, end];
}

function addRegex(raw: RawSpan[], text: UText, pattern: RegExp, kind: SpanKind): void {
  for (const match of findAll(pattern, text)) appendSpan(raw, match.start, match.end, kind);
}

function validDateParts(year: number, month: number, day: number): boolean {
  if (year < 1 || year > 9999 || month < 1 || month > 12 || day < 1 || day > 31) return false;
  const dt = new Date(Date.UTC(year, month - 1, day));
  return dt.getUTCFullYear() === year && dt.getUTCMonth() === month - 1 && dt.getUTCDate() === day;
}

function parseIntDigits(value: string): number | null {
  if (!value || ![...value].every((ch) => isPyDigit(ch))) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function validEnglishDate(value: string): boolean {
  const normalized = collapseWs(value.replace(/,/g, ""));
  const parts = normalized.split(" ");
  if (parts.length !== 3) return false;
  let dayText: string;
  let monthText: string;
  let yearText: string;
  if (/^\p{Nd}+$/u.test(parts[0])) {
    [dayText, monthText, yearText] = parts;
  } else {
    [monthText, dayText, yearText] = parts;
  }
  const month = MONTH_NUMBERS[monthText.toLowerCase()];
  const day = parseIntDigits(dayText);
  const year = parseIntDigits(yearText);
  if (month === undefined || day === null || year === null) return false;
  return validDateParts(year, month, day);
}

function validSlashDate(value: string): boolean {
  const parts = value.split("/");
  if (parts.length !== 3 || parts.some((part) => parseIntDigits(part) === null)) return false;
  const [first, second, third] = parts;
  if (first.length === 4) {
    return validDateParts(parseIntDigits(first)!, parseIntDigits(second)!, parseIntDigits(third)!);
  }
  const year = third.length === 4 ? parseIntDigits(third)! : 2000 + parseIntDigits(third)!;
  const a = parseIntDigits(first)!;
  const b = parseIntDigits(second)!;
  return validDateParts(year, a, b) || validDateParts(year, b, a);
}

function addUrls(raw: RawSpan[], text: UText): void {
  for (const pattern of [URL_RE, BARE_DOMAIN_RE]) {
    for (const match of findAll(pattern, text)) {
      const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
      appendSpan(raw, start, end, "url");
    }
  }
}

function addIpAddresses(raw: RawSpan[], text: UText): void {
  for (const match of findAll(IPV4_RE, text)) {
    if (isIPv4Address(match.text)) appendSpan(raw, match.start, match.end, "ipv4");
  }
  for (const match of findAll(IPV6_TOKEN_RE, text)) {
    let candidate = match.text;
    let end = match.end;
    if ((candidate.match(/:/g) || []).length < 2) continue;
    while (candidate.endsWith(".")) {
      candidate = candidate.slice(0, -1);
      end -= 1;
    }
    if (isIPv6Address(candidate)) appendSpan(raw, match.start, end, "ipv6");
  }
}

function addDates(raw: RawSpan[], text: UText): void {
  for (const match of findAll(ISO_DATE_RE, text)) {
    const [year, month, day] = match.text.split("-").map((part) => parseIntDigits(part));
    if (year === null || month === null || day === null) continue;
    if (validDateParts(year, month, day)) appendSpan(raw, match.start, match.end, "date");
  }
  for (const pattern of [MONTH_FIRST_DATE_RE, DAY_FIRST_DATE_RE]) {
    for (const match of findAll(pattern, text)) {
      if (validEnglishDate(match.text)) appendSpan(raw, match.start, match.end, "date");
    }
  }
  for (const match of findAll(SLASH_DATE_RE, text)) {
    if (validSlashDate(match.text)) appendSpan(raw, match.start, match.end, "date");
  }
}

function paragraphEnd(text: UText, start: number): number {
  const match = searchFrom(BLANK_LINE_RE, text, start);
  return match === null ? text.length : match.start;
}

function searchAtLineStart(
  text: UText,
  cursor: number,
  test: (rest: string) => RegExpExecArray | null,
): ReMatch | null {
  for (let i = cursor; i < text.length; i += 1) {
    if (i > 0 && text.at(i - 1) !== "\n") continue;
    const rest = text.raw.slice(text.utf16Index(i));
    const match = test(rest);
    if (match && match.index === 0) {
      return {
        start: i,
        end: i + [...match[0]].length,
        text: match[0],
        groups: match.slice(1),
      };
    }
  }
  return null;
}

function addFencedCode(raw: RawSpan[], text: UText): void {
  let cursor = 0;
  const openTest = (rest: string) => /^[ \t]{0,3}(`{3,}|~{3,})[^\n]*(?:\n|$)/.exec(rest);
  for (;;) {
    const opening = searchAtLineStart(text, cursor, openTest);
    if (opening === null) return;
    const run = opening.groups[0] || "";
    const marker = run[0];
    const minimum = run.length;
    const closeRe = new RegExp(`^[ \\t]{0,3}${marker}{${minimum},}[ \\t]*(?:\\n|$)`);
    const closing = searchAtLineStart(text, opening.end, (rest) => closeRe.exec(rest));
    const end = closing === null ? text.length : closing.end;
    appendSpan(raw, opening.start, end, "code");
    if (closing === null) return;
    cursor = end;
  }
}

function addIndentedCode(raw: RawSpan[], text: UText): void {
  const starts = lineStarts(text);
  const count = starts.length;
  for (let index = 0; index < count; index += 1) {
    const start = starts[index];
    const nextStart = index + 1 < count ? starts[index + 1] : text.length;
    const limit = lineContentEnd(text, start, nextStart);
    let cursor = start;
    for (;;) {
      let spaces = 0;
      let look = cursor;
      while (look < limit && spaces < 4 && text.at(look) === " ") {
        spaces += 1;
        look += 1;
      }
      if (look < limit && text.at(look) === ">") {
        cursor = look + 1;
        if (cursor < limit && (text.at(cursor) === " " || text.at(cursor) === "\t")) cursor += 1;
        continue;
      }
      break;
    }
    if (cursor < limit && text.at(cursor) === "\t") {
      appendSpan(raw, cursor, limit, "code");
      continue;
    }
    if (cursor + 4 <= limit && text.slice(cursor, cursor + 4) === "    ") {
      appendSpan(raw, cursor, limit, "code");
    }
  }
}

function addHtmlMarkup(raw: RawSpan[], text: UText): void {
  addRegex(raw, text, HTML_TAG_RE, "code");
  addRegex(raw, text, HTML_ENTITY_RE, "code");
}

function addInlineCode(raw: RawSpan[], text: UText): void {
  const runs = findAll(INLINE_CODE_RUN_RE, text).filter((match) => !isEscaped(text, match.start));
  if (!runs.length) return;
  const matchByStart = new Map<number, ReMatch>();
  const grouped = new Map<number, number[]>();
  for (const match of runs) {
    matchByStart.set(match.start, match);
    const length = match.text.length;
    const list = grouped.get(length) || [];
    list.push(match.start);
    grouped.set(length, list);
  }
  const byLength = new Map<number, number[]>();
  for (const [length, starts] of grouped) byLength.set(length, starts);
  let consumedUntil = -1;
  for (const opening of runs) {
    if (opening.start < consumedUntil) continue;
    const starts = byLength.get(opening.text.length) || [];
    const position = bisectRight(starts, opening.start);
    const endOfParagraph = paragraphEnd(text, opening.end);
    let closing: ReMatch | null = null;
    if (position < starts.length && starts[position] < endOfParagraph) {
      closing = matchByStart.get(starts[position]) || null;
    }
    const end = closing === null ? lineEnd(text, opening.end) : closing.end;
    appendSpan(raw, opening.start, end, "code");
    consumedUntil = Math.max(end, opening.end);
  }
}

function markdownBracketPairs(text: UText): Array<[number, number]> {
  const stack: number[] = [];
  const pairs: Array<[number, number]> = [];
  for (let index = 0; index < text.length; index += 1) {
    const character = text.at(index);
    if ((character !== "[" && character !== "]") || isEscaped(text, index)) continue;
    if (character === "[") {
      stack.push(index);
      continue;
    }
    if (!stack.length) continue;
    const start = stack.pop()!;
    const inner = index - start - 1;
    if (inner > MAX_MARKDOWN_LABEL) continue;
    pairs.push([start, index]);
  }
  return pairs;
}

function lineIndex(starts: number[], index: number): number {
  return bisectRight(starts, index) - 1;
}

function skipBlockquotes(text: UText, index: number, limit: number): number {
  for (;;) {
    let spaces = 0;
    let cursor = index;
    while (cursor < limit && spaces < 4 && text.at(cursor) === " ") {
      spaces += 1;
      cursor += 1;
    }
    if (cursor < limit && text.at(cursor) === ">") {
      index = cursor + 1;
      if (index < limit && (text.at(index) === " " || text.at(index) === "\t")) index += 1;
      continue;
    }
    return index;
  }
}

function skipListMarker(text: UText, index: number, limit: number): number {
  let spaces = 0;
  let cursor = index;
  while (cursor < limit && spaces < 4 && text.at(cursor) === " ") {
    spaces += 1;
    cursor += 1;
  }
  if (spaces >= 4) return index;
  if (cursor < limit && "-+*".includes(text.at(cursor))) {
    const nxt = cursor + 1;
    if (nxt < limit && (text.at(nxt) === " " || text.at(nxt) === "\t")) return nxt + 1;
    return index;
  }
  let digits = 0;
  while (cursor < limit && isPyDigit(text.at(cursor)) && digits < 9) {
    cursor += 1;
    digits += 1;
  }
  if (digits && cursor < limit && ".)".includes(text.at(cursor))) {
    cursor += 1;
    if (cursor < limit && (text.at(cursor) === " " || text.at(cursor) === "\t")) return cursor + 1;
  }
  return index;
}

function isReferenceDefinitionLabel(
  text: UText,
  start: number,
  end: number,
  starts: number[],
): boolean {
  const lineI = lineIndex(starts, start);
  const lineStart = starts[lineI];
  const nextStart = lineI + 1 < starts.length ? starts[lineI + 1] : text.length;
  const limit = lineContentEnd(text, lineStart, nextStart);
  let cursor = skipBlockquotes(text, lineStart, limit);
  cursor = skipListMarker(text, cursor, limit);
  let indent = 0;
  while (cursor < start && indent < 4 && text.at(cursor) === " ") {
    indent += 1;
    cursor += 1;
  }
  if (cursor !== start || indent >= 4) return false;
  const after = skipReferenceWhitespace(text, end + 1);
  return after < text.length && text.at(after) === ":";
}

function parseLinkDestination(text: UText, start: number): [number, number] | null {
  let index = start;
  if (index >= text.length) return null;
  if (text.at(index) === "<") {
    let cursor = index + 1;
    while (cursor < text.length && !">\r\n".includes(text.at(cursor))) {
      if (text.at(cursor) === "\\" && cursor + 1 < text.length) {
        cursor += 2;
        continue;
      }
      cursor += 1;
    }
    if (cursor < text.length && text.at(cursor) === ">") return [index, cursor + 1];
    return null;
  }
  let cursor = index;
  let depth = 0;
  while (cursor < text.length) {
    const character = text.at(cursor);
    if (" \t\r\n".includes(character) || text.codePoint(cursor) < 32) break;
    if (character === "\\" && cursor + 1 < text.length) {
      cursor += 2;
      continue;
    }
    if (character === "(") depth += 1;
    else if (character === ")") {
      if (depth === 0) break;
      depth -= 1;
    }
    cursor += 1;
  }
  if (cursor <= index) return null;
  return [index, cursor];
}

function normalizeMarkdownLabel(label: string): string {
  return pyCasefold(collapseWs(label));
}

function definitionLabels(
  text: UText,
  pairs: Array<[number, number]>,
): Map<string, Array<[number, number, number, number]>> {
  const found = new Map<string, Array<[number, number, number, number]>>();
  const starts = lineStarts(text);
  for (const [start, end] of pairs) {
    if (!isReferenceDefinitionLabel(text, start, end, starts)) continue;
    const after = skipReferenceWhitespace(text, end + 1);
    if (after >= text.length || text.at(after) !== ":") continue;
    const destFrom = skipReferenceWhitespace(text, after + 1);
    const destination = parseLinkDestination(text, destFrom);
    if (destination === null) continue;
    const [destStart, destEnd] = destination;
    const inner = text.slice(start + 1, end);
    if (!inner.trim()) continue;
    if (end - start - 1 > MAX_MARKDOWN_LABEL) continue;
    const key = normalizeMarkdownLabel(inner);
    const rows = found.get(key) || [];
    rows.push([start + 1, end, destStart, destEnd]);
    found.set(key, rows);
  }
  return found;
}

function markdownLabelClosers(text: UText): Set<number> {
  return new Set(markdownBracketPairs(text).map(([, end]) => end));
}

function addMarkdownDestinations(raw: RawSpan[], text: UText): void {
  let cursor = 0;
  for (;;) {
    const marker = text.indexOf("](", cursor);
    if (marker < 0) return;
    if (isEscaped(text, marker)) {
      cursor = marker + 2;
      continue;
    }
    const start = marker + 2;
    let depth = 1;
    let index = start;
    let escaped = false;
    let closed = false;
    while (index < text.length) {
      const character = text.at(index);
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === "(") depth += 1;
      else if (character === ")") {
        depth -= 1;
        if (depth === 0) {
          appendSpan(raw, start, index, "markdown_destination");
          cursor = index + 1;
          closed = true;
          break;
        }
      }
      index += 1;
    }
    if (!closed) {
      appendSpan(raw, start, index, "markdown_destination");
      cursor = Math.max(index, start + 1);
    }
  }
}

function addValidMarkdownDestinations(raw: RawSpan[], text: UText): void {
  const closers = markdownLabelClosers(text);
  if (!closers.size) return;
  const temporary: RawSpan[] = [];
  addMarkdownDestinations(temporary, text);
  for (const [start, end, kind] of temporary) {
    if (start >= 2 && closers.has(start - 2)) appendSpan(raw, start, end, kind);
  }
}

function addMarkdownReferenceSpans(raw: RawSpan[], text: UText): void {
  const pairs = markdownBracketPairs(text);
  if (!pairs.length) return;
  const defined = definitionLabels(text, pairs);
  if (!defined.size) return;
  const starts = lineStarts(text);
  for (const rows of defined.values()) {
    for (const [labelStart, labelEnd, destStart, destEnd] of rows) {
      appendSpan(raw, labelStart, labelEnd, "markdown_label");
      appendSpan(raw, destStart, destEnd, "markdown_destination");
    }
  }
  const byStart = new Map<number, [number, number]>();
  for (const pair of pairs) byStart.set(pair[0], pair);
  const seen = new Set<number>();
  for (const [start, end] of pairs) {
    if (seen.has(start)) continue;
    if (isReferenceDefinitionLabel(text, start, end, starts)) continue;
    const following = byStart.get(end + 1);
    if (following !== undefined) {
      seen.add(following[0]);
      let labelInner = text.slice(following[0] + 1, following[1]);
      let innerStart = following[0] + 1;
      let innerEnd = following[1];
      if (labelInner.trim() === "") {
        innerStart = start + 1;
        innerEnd = end;
        labelInner = text.slice(innerStart, innerEnd);
      }
      if (defined.has(normalizeMarkdownLabel(labelInner))) {
        appendSpan(raw, innerStart, innerEnd, "markdown_label");
      }
      continue;
    }
    if (end + 1 < text.length && text.at(end + 1) === "(") continue;
    const innerStart = start + 1;
    const innerEnd = end;
    const labelInner = text.slice(innerStart, innerEnd);
    if (defined.has(normalizeMarkdownLabel(labelInner))) {
      appendSpan(raw, innerStart, innerEnd, "markdown_label");
    }
  }
}

function stripSlashes(token: string): string {
  return token.replace(/^\/+|\/+$/g, "");
}

function acceptExtensionlessRelative(token: string): boolean {
  const compact = pyCasefold(stripSlashes(token));
  if (PROSE_SLASH_PAIRS.has(compact)) return false;
  const parts = stripSlashes(token).split("/").filter(Boolean);
  if (parts.length < 2) return false;
  if (parts.length >= 3) return true;
  if (PATH_ROOTS.has(pyCasefold(parts[0]))) return true;
  return parts.some(
    (part) => [...part].some((ch) => "._-".includes(ch)) || [...part].some((ch) => isPyDigit(ch)),
  );
}

function lastComponentHasSpace(text: UText, start: number, end: number, separators: string): boolean {
  const chunk = text.slice(start, end);
  let last = -1;
  for (const separator of separators) {
    last = Math.max(last, chunk.lastIndexOf(separator));
  }
  if (last < 0) return false;
  return chunk.slice(last + 1).includes(" ");
}

function addPosixPaths(raw: RawSpan[], text: UText): void {
  for (const match of findAll(POSIX_PATH_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    appendSpan(raw, start, end, "posix_path");
  }
  for (const match of findAll(RELATIVE_PATH_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    appendSpan(raw, start, end, "posix_path");
  }
  for (const match of findAll(EXTENSIONLESS_RELATIVE_PATH_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    const token = text.slice(start, end);
    if (!acceptExtensionlessRelative(token)) continue;
    appendSpan(raw, start, end, "posix_path");
  }
  for (const match of findAll(POSIX_SPACED_FILE_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    if (lastComponentHasSpace(text, start, end, "/")) appendSpan(raw, start, end, "posix_path");
  }
}

function addWindowsPaths(raw: RawSpan[], text: UText): void {
  for (const match of findAll(WINDOWS_PATH_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    appendSpan(raw, start, end, "windows_path");
  }
  for (const match of findAll(WINDOWS_SPACED_FILE_RE, text)) {
    const [start, end] = trimTerminalPunctuation(text, match.start, match.end);
    if (lastComponentHasSpace(text, start, end, "/\\")) appendSpan(raw, start, end, "windows_path");
  }
}

function pathScanLimit(text: UText, start: number, forbidden: string): number {
  const endOfLine = lineEnd(text, start);
  let end = Math.min(endOfLine, start + MAX_EXTENDED_PATH_SCAN);
  const region = text.slice(start, end);
  const match = EXTENDED_BOUNDARY_RE.exec(region);
  EXTENDED_BOUNDARY_RE.lastIndex = 0;
  if (match && match.index >= 0) end = start + [...region.slice(0, match.index)].length;
  for (let index = start; index < end; index += 1) {
    const ch = text.at(index);
    if (forbidden.includes(ch) || ch === ";") return index;
  }
  return end;
}

function extendedPathEnd(
  text: UText,
  start: number,
  prefixEnd: number,
  separator: string,
  forbidden: string,
): number | null {
  const endOfLine = lineEnd(text, start);
  const limit = pathScanLimit(text, prefixEnd, forbidden);
  const segment = text.slice(start, limit);
  const whitespacePositions: number[] = [];
  for (let index = 0; index < segment.length; index += 1) {
    if (segment[index] === " " || segment[index] === "\t") whitespacePositions.push(index);
  }
  if (!whitespacePositions.length) return null;
  if (!whitespacePositions.some((index) => segment.slice(index + 1).includes(separator))) return null;
  let end = limit;
  for (const relative of whitespacePositions) {
    if (segment.slice(relative + 1).includes(separator)) continue;
    const prefix = segment.slice(0, relative).replace(/[ \t]+$/, "");
    if (/\.[A-Za-z0-9]{1,12}$/.test(prefix)) {
      end = start + relative;
      break;
    }
  }
  if (
    endOfLine > prefixEnd + MAX_EXTENDED_PATH_SCAN &&
    limit === prefixEnd + MAX_EXTENDED_PATH_SCAN &&
    end === limit
  ) {
    throw new Error("extended path scan exceeded resource limit");
  }
  [, end] = trimTerminalPunctuation(text, start, end);
  return end > prefixEnd ? end : null;
}

function otherProtectionIndex(
  raw: RawSpan[],
  ownKind: SpanKind,
): { starts: number[]; intervals: Array<[number, number]> } {
  const ordered = raw
    .filter(([, , kind]) => kind !== ownKind)
    .map(([start, end]) => [start, end] as [number, number])
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const [start, end] of ordered) {
    if (!merged.length || start > merged[merged.length - 1][1]) merged.push([start, end]);
    else merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], end);
  }
  return { starts: merged.map(([start]) => start), intervals: merged };
}

function startsInsideOtherProtection(
  starts: number[],
  intervals: Array<[number, number]>,
  start: number,
): boolean {
  const index = bisectRight(starts, start) - 1;
  return index >= 0 && start < intervals[index][1];
}

function addExtendedWindowsPaths(raw: RawSpan[], text: UText): void {
  const { starts, intervals } = otherProtectionIndex(raw, "windows_path");
  for (const match of findAll(WINDOWS_PREFIX_RE, text)) {
    if (startsInsideOtherProtection(starts, intervals, match.start)) continue;
    const separator = match.text.endsWith("/") ? "/" : "\\";
    const end = extendedPathEnd(text, match.start, match.end, separator, '<>"|?*');
    if (end !== null) appendSpan(raw, match.start, end, "windows_path");
  }
}

function addExtendedPosixPaths(raw: RawSpan[], text: UText): void {
  const { starts, intervals } = otherProtectionIndex(raw, "posix_path");
  for (const match of findAll(POSIX_PREFIX_RE, text)) {
    if (startsInsideOtherProtection(starts, intervals, match.start)) continue;
    const end = extendedPathEnd(text, match.start, match.end, "/", '<>"|');
    if (end !== null) appendSpan(raw, match.start, end, "posix_path");
  }
}

export function addHardMachineSpans(raw: RawSpan[], source: string): void {
  const text = new UText(source);
  addFencedCode(raw, text);
  addInlineCode(raw, text);
  addIndentedCode(raw, text);
  addHtmlMarkup(raw, text);
  addValidMarkdownDestinations(raw, text);
  addMarkdownReferenceSpans(raw, text);
  addUrls(raw, text);
  addRegex(raw, text, EMAIL_RE, "email");
  addIpAddresses(raw, text);
  addDates(raw, text);
  addRegex(raw, text, CURRENCY_RE, "currency");
  addRegex(raw, text, PERCENT_RE, "percentage");
  addRegex(raw, text, NUMBER_RE, "number");
  addPosixPaths(raw, text);
  addExtendedPosixPaths(raw, text);
  addWindowsPaths(raw, text);
  addExtendedWindowsPaths(raw, text);
  addRegex(raw, text, CLI_FLAG_RE, "cli_flag");
}

export function hardMachineIntervals(source: string): Array<[number, number]> {
  const raw: RawSpan[] = [];
  addHardMachineSpans(raw, source);
  const ordered = raw.map(([start, end]) => [start, end] as [number, number]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: Array<[number, number]> = [];
  for (const [start, end] of ordered) {
    if (!merged.length || start > merged[merged.length - 1][1]) merged.push([start, end]);
    else merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], end);
  }
  return merged;
}

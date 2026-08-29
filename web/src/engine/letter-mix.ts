import { EMOJI_SO_RANGES } from "./generated/emoji-so";
import { LIVE_LETTER_RANGES } from "./generated/letters";
import {
  APPROVED_CARRIER_SET,
  LETTER_MIX_APPROVED_CARRIERS,
  LETTER_MIX_CF_PAYLOADS,
  LETTER_MIX_CONTROL_PAYLOADS,
  LETTER_MIX_IA_PAYLOADS,
  LETTER_MIX_INSERTIONS_PER_SITE,
  LETTER_MIX_MARK_PAYLOADS,
  LETTER_MIX_MAX_SELECTED,
  LETTER_MIX_ME_PAYLOADS,
  PRODUCT_DOMAIN_ALLOWED,
} from "./carriers";
import { hardMachineIntervals } from "./protected";
import { isCarrierInsertion, projectVisible } from "./projection";
import { inRanges } from "./text";

const VS_CODEPOINTS = new Set([0xfe0e, 0xfe0f]);
const KEYCAP_BASES = new Set(["#", "*", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]);
const EXTRA_EMOJI = new Set([0x00a9, 0x00ae, 0x203c, 0x2049, 0x2122, 0x2139, 0x3030, 0x303d, 0x3297, 0x3299]);

function isRegionalIndicator(code: number): boolean {
  return code >= 0x1f1e6 && code <= 0x1f1ff;
}

function isEmojiBase(character: string): boolean {
  const code = character.codePointAt(0)!;
  if (isRegionalIndicator(code)) return true;
  if (code >= 0x1f000 && code <= 0x1faff) return true;
  if (code >= 0x2600 && code <= 0x27bf && inRanges(code, EMOJI_SO_RANGES)) return true;
  return EXTRA_EMOJI.has(code);
}

function isLiveLetterBase(character: string): boolean {
  const code = character.codePointAt(0)!;
  if (code <= 0x7f) {
    return (code >= 0x41 && code <= 0x5a) || (code >= 0x61 && code <= 0x7a);
  }
  return inRanges(code, LIVE_LETTER_RANGES);
}

function isKeycapBase(units: string[], index: number): boolean {
  if (!KEYCAP_BASES.has(units[index])) return false;
  const nxt = index + 1;
  if (nxt >= units.length) return false;
  const code = units[nxt].codePointAt(0)!;
  return code === 0xfe0f || code === 0x20e3;
}

function isLiveClusterBase(units: string[], index: number): boolean {
  const character = units[index];
  return isLiveLetterBase(character) || isEmojiBase(character) || isKeycapBase(units, index);
}

function isClusterExtender(character: string): boolean {
  const code = character.codePointAt(0)!;
  if (VS_CODEPOINTS.has(code)) return true;
  if (code >= 0xe0020 && code <= 0xe007f) return true;
  return /^\p{Mn}$/u.test(character) || /^\p{Mc}$/u.test(character) || /^\p{Me}$/u.test(character);
}

function extendCluster(units: string[], start: number): number {
  let index = start + 1;
  if (isRegionalIndicator(units[start].codePointAt(0)!) && index < units.length && isRegionalIndicator(units[index].codePointAt(0)!)) {
    index += 1;
  }
  while (index < units.length) {
    const character = units[index];
    const code = character.codePointAt(0)!;
    if (isClusterExtender(character)) {
      index += 1;
      continue;
    }
    if (code === 0x200d) {
      index += 1;
      if (index < units.length) index += 1;
      continue;
    }
    break;
  }
  return index;
}

function rangeOverlapsBlocked(start: number, end: number, blocked: Array<[number, number]>): boolean {
  for (const [left, right] of blocked) {
    if (start < right && end > left) return true;
  }
  return false;
}

function sourceContainsCarriers(units: string[], approved: ReadonlySet<number>): boolean {
  return units.some((character) => approved.has(character.codePointAt(0)!));
}

export function selectLetterMixSites(
  text: string,
  maxSelected: number | null = LETTER_MIX_MAX_SELECTED,
  approvedCarriers: ReadonlySet<number> = APPROVED_CARRIER_SET,
): number[] {
  const units = [...text];
  if (sourceContainsCarriers(units, approvedCarriers)) return [];
  const blocked = hardMachineIntervals(text);
  const sites: number[] = [];
  let index = 0;
  while (index < units.length) {
    if (!isLiveClusterBase(units, index)) {
      index += 1;
      continue;
    }
    const clusterEnd = extendCluster(units, index);
    if (rangeOverlapsBlocked(index, clusterEnd, blocked)) {
      index = clusterEnd;
      continue;
    }
    sites.push(clusterEnd - 1);
    if (maxSelected !== null && sites.length >= maxSelected) break;
    index = clusterEnd;
  }
  return sites;
}

export function composeLetterMix(text: string, sites: number[]): string {
  const units = [...text];
  const ordered = sites.slice();
  const unique = [...ordered].sort((a, b) => a - b);
  if (ordered.some((value, i) => value !== unique[i]) || new Set(ordered).size !== ordered.length) {
    throw new Error("letter mix sites must be unique and ordered");
  }
  const controlCount = LETTER_MIX_CONTROL_PAYLOADS.length;
  const meCount = LETTER_MIX_ME_PAYLOADS.length;
  const cfCount = LETTER_MIX_CF_PAYLOADS.length;
  const iaCount = LETTER_MIX_IA_PAYLOADS.length;
  const chunks: string[] = [];
  let cursor = 0;
  for (let order = 0; order < ordered.length; order += 1) {
    const index = ordered[order];
    if (index < cursor || index >= units.length) throw new Error("letter mix site is outside the source");
    chunks.push(units.slice(cursor, index + 1).join(""));
    chunks.push(LETTER_MIX_MARK_PAYLOADS[order % 2]);
    chunks.push(LETTER_MIX_CONTROL_PAYLOADS[order % controlCount]);
    chunks.push(LETTER_MIX_ME_PAYLOADS[order % meCount]);
    chunks.push(LETTER_MIX_CF_PAYLOADS[order % cfCount]);
    chunks.push(LETTER_MIX_IA_PAYLOADS[order % iaCount]);
    cursor = index + 1;
  }
  chunks.push(units.slice(cursor).join(""));
  const output = chunks.join("");
  if (projectVisible(output, APPROVED_CARRIER_SET) !== text) {
    throw new Error("letter mix changed the visible projection");
  }
  if (!isCarrierInsertion(text, output, APPROVED_CARRIER_SET)) {
    throw new Error("letter mix is not a carrier insertion");
  }
  const outUnits = [...output];
  let siteIndex = 0;
  let shift = 0;
  for (const [start, end] of hardMachineIntervals(text)) {
    while (siteIndex < ordered.length && ordered[siteIndex] < start) {
      shift += LETTER_MIX_INSERTIONS_PER_SITE;
      siteIndex += 1;
    }
    if (outUnits.slice(start + shift, end + shift).join("") !== units.slice(start, end).join("")) {
      throw new Error("letter mix mutated a hard machine span");
    }
  }
  return output;
}

export function applyLetterAlternatingMix(text: string, maxSelected: number | null = LETTER_MIX_MAX_SELECTED): string {
  return composeLetterMix(text, selectLetterMixSites(text, maxSelected));
}

export function firstUnmixedNonAscii(text: string): [number, number] | null {
  const units = [...text];
  const blocked = hardMachineIntervals(text);
  const covered: Array<[number, number]> = [];
  let index = 0;
  while (index < units.length) {
    if (!isLiveClusterBase(units, index)) {
      index += 1;
      continue;
    }
    const clusterEnd = extendCluster(units, index);
    if (!rangeOverlapsBlocked(index, clusterEnd, blocked)) covered.push([index, clusterEnd]);
    index = clusterEnd;
  }
  let coveredIndex = 0;
  for (let position = 0; position < units.length; position += 1) {
    const codepoint = units[position].codePointAt(0)!;
    if (PRODUCT_DOMAIN_ALLOWED.has(codepoint)) continue;
    while (coveredIndex < covered.length && covered[coveredIndex][1] <= position) coveredIndex += 1;
    if (coveredIndex < covered.length && covered[coveredIndex][0] <= position && position < covered[coveredIndex][1]) {
      continue;
    }
    return [position, codepoint];
  }
  return null;
}

export function isSupportedProductDomain(text: string): boolean {
  return [...text].every((character) => PRODUCT_DOMAIN_ALLOWED.has(character.codePointAt(0)!));
}

export function letterMixApprovedCarriers(): readonly number[] {
  return LETTER_MIX_APPROVED_CARRIERS;
}

import {
  APPROVED_CARRIER_SET,
  DETECT_CONTACT_EMAIL,
  LETTER_MIX_MAX_SELECTED,
  PRODUCT_MAX_INPUT_CHARS,
} from "./carriers";
import { detectFuckMarkInsertions, type DetectResult } from "./detect";
import {
  applyLetterAlternatingMix,
  composeLetterMix,
  firstUnmixedNonAscii,
  isSupportedProductDomain,
  selectLetterMixSites,
} from "./letter-mix";
import { isCarrierInsertion, projectVisible } from "./projection";

export const REASON_TRANSFORMED = "transformed";
export const REASON_SITE_CAP = "site-cap";
export const REASON_UNSUPPORTED_DOMAIN = "unsupported-domain";
export const REASON_ALREADY_TRANSFORMED = "already-transformed";
export const REASON_NO_ELIGIBLE_SITES = "no-eligible-sites";
export const REASON_INTERNAL_ERROR = "internal-error";
export const REASON_TOO_LARGE = "too-large";

export type ProcessResult = {
  output_text: string;
  change_count: number;
  reason: string;
  last_source_index: number | null;
  site_count: number;
  capped: boolean;
  source_length: number;
  first_unsupported: string;
};

function unsupportedToken(text: string): string {
  const found = firstUnmixedNonAscii(text);
  if (found === null) return "";
  return `U+${found[1].toString(16).toUpperCase().padStart(4, "0")}@${found[0]}`;
}

function unchanged(text: string, reason: string): ProcessResult {
  const token = reason === REASON_UNSUPPORTED_DOMAIN ? unsupportedToken(text) : "";
  return {
    output_text: text,
    change_count: 0,
    reason,
    last_source_index: null,
    site_count: 0,
    capped: false,
    source_length: [...text].length,
    first_unsupported: token,
  };
}

export function transformText(text: string): ProcessResult {
  try {
    const sourceLength = [...text].length;
    if (sourceLength > PRODUCT_MAX_INPUT_CHARS) return unchanged(text, REASON_TOO_LARGE);
    if ([...text].some((character) => APPROVED_CARRIER_SET.has(character.codePointAt(0)!))) {
      return unchanged(text, REASON_ALREADY_TRANSFORMED);
    }
    const unsupported = unsupportedToken(text);
    const probe = selectLetterMixSites(text, LETTER_MIX_MAX_SELECTED + 1);
    const capped = probe.length > LETTER_MIX_MAX_SELECTED;
    const sites = probe.slice(0, LETTER_MIX_MAX_SELECTED);
    if (!sites.length) {
      if (unsupported && !isSupportedProductDomain(text)) {
        return {
          output_text: text,
          change_count: 0,
          reason: REASON_UNSUPPORTED_DOMAIN,
          last_source_index: null,
          site_count: 0,
          capped: false,
          source_length: sourceLength,
          first_unsupported: unsupported,
        };
      }
      return {
        output_text: text,
        change_count: 0,
        reason: REASON_NO_ELIGIBLE_SITES,
        last_source_index: null,
        site_count: 0,
        capped: false,
        source_length: sourceLength,
        first_unsupported: unsupported,
      };
    }
    const applied = composeLetterMix(text, sites);
    if (applied === text) {
      return {
        output_text: text,
        change_count: 0,
        reason: REASON_NO_ELIGIBLE_SITES,
        last_source_index: null,
        site_count: 0,
        capped: false,
        source_length: sourceLength,
        first_unsupported: unsupported,
      };
    }
    if (!isCarrierInsertion(text, applied) || projectVisible(applied) !== text) {
      return unchanged(text, REASON_INTERNAL_ERROR);
    }
    return {
      output_text: applied,
      change_count: [...applied].length - sourceLength,
      reason: capped ? REASON_SITE_CAP : REASON_TRANSFORMED,
      last_source_index: sites[sites.length - 1],
      site_count: sites.length,
      capped,
      source_length: sourceLength,
      first_unsupported: unsupported,
    };
  } catch {
    return unchanged(text, REASON_INTERNAL_ERROR);
  }
}

export function processText(text: string): string {
  return transformText(text).output_text;
}

export function stripMarks(text: string): { text: string; removed: number } {
  const scan = detectFuckMarkInsertions(text);
  return { text: projectVisible(text), removed: scan.found };
}

export function removeMarksPayload(text: string): {
  ok: boolean;
  reason: string;
  backend: string;
  detect: DetectResult;
  text: string;
  removed: number;
  contact: string;
  max?: number;
} {
  const sourceLength = [...text].length;
  if (sourceLength > PRODUCT_MAX_INPUT_CHARS) {
    return {
      ok: false,
      reason: "too-large",
      backend: "js",
      max: PRODUCT_MAX_INPUT_CHARS,
      detect: detectFuckMarkInsertions(""),
      text: "",
      removed: 0,
      contact: DETECT_CONTACT_EMAIL,
    };
  }
  const detect = detectFuckMarkInsertions(text);
  if (!detect.detected) {
    return {
      ok: false,
      reason: "not-detected",
      backend: "js",
      detect,
      text,
      removed: 0,
      contact: DETECT_CONTACT_EMAIL,
    };
  }
  const cleaned = projectVisible(text);
  return {
    ok: true,
    reason: "stripped",
    backend: "js",
    detect,
    text: cleaned,
    removed: detect.found,
    contact: DETECT_CONTACT_EMAIL,
  };
}

export { applyLetterAlternatingMix, selectLetterMixSites };

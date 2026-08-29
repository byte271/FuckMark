export const DETECT_CONTACT_EMAIL = "Fhelp@q1z.org";
export const PRODUCT_MAX_INPUT_CHARS = 2_000_000;
export const LETTER_MIX_MAX_SELECTED = 4096;
export const LETTER_MIX_INSERTIONS_PER_SITE = 5;
export const RELEASE_CLI_ALGORITHM_VERSION = "release-cli-v12";
export const ENGINE_ID = "fuckmark-web-engine-v1";

export const LETTER_MIX_MARK_PAYLOADS = ["\u034f", "\ufe00"] as const;
export const LETTER_MIX_CONTROL_CODEPOINTS = [
  0x007f,
  ...range(0x0080, 0x0085),
  ...range(0x0086, 0x00a0),
] as const;
export const LETTER_MIX_CONTROL_PAYLOADS = LETTER_MIX_CONTROL_CODEPOINTS.map((code) =>
  String.fromCodePoint(code),
);
export const LETTER_MIX_ME_PAYLOADS = ["\u20dd"] as const;
export const LETTER_MIX_CF_CODEPOINTS = range(0x13430, 0x13439);
export const LETTER_MIX_CF_PAYLOADS = LETTER_MIX_CF_CODEPOINTS.map((code) => String.fromCodePoint(code));
export const LETTER_MIX_IA_CODEPOINTS = [0xfff9, 0xfffa, 0xfffb] as const;
export const LETTER_MIX_IA_PAYLOADS = LETTER_MIX_IA_CODEPOINTS.map((code) => String.fromCodePoint(code));

export const LETTER_MIX_APPROVED_CARRIERS: readonly number[] = [
  ...LETTER_MIX_MARK_PAYLOADS.map((ch) => ch.codePointAt(0)!),
  ...LETTER_MIX_CONTROL_CODEPOINTS,
  ...LETTER_MIX_ME_PAYLOADS.map((ch) => ch.codePointAt(0)!),
  ...LETTER_MIX_CF_CODEPOINTS,
  ...LETTER_MIX_IA_CODEPOINTS,
];

export const APPROVED_CARRIER_SET = new Set<number>(LETTER_MIX_APPROVED_CARRIERS);
export const MARK_SET = new Set<number>(LETTER_MIX_MARK_PAYLOADS.map((ch) => ch.codePointAt(0)!));
export const CC_SET = new Set<number>(LETTER_MIX_CONTROL_CODEPOINTS);
export const ME_SET = new Set<number>(LETTER_MIX_ME_PAYLOADS.map((ch) => ch.codePointAt(0)!));
export const CF_SET = new Set<number>(LETTER_MIX_CF_CODEPOINTS);
export const IA_SET = new Set<number>(LETTER_MIX_IA_CODEPOINTS);

export const PRODUCT_DOMAIN_ALLOWED = new Set<number>([9, 10, 13, ...range(0x20, 0x7f)]);

function range(start: number, end: number): number[] {
  const out: number[] = [];
  for (let code = start; code < end; code += 1) out.push(code);
  return out;
}

export function isApprovedCarrier(code: number): boolean {
  return APPROVED_CARRIER_SET.has(code);
}

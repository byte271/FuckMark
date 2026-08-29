import { APPROVED_CARRIER_SET, LETTER_MIX_APPROVED_CARRIERS } from "./carriers";

export function productApprovedCarriers(): ReadonlySet<number> {
  return APPROVED_CARRIER_SET;
}

export function projectVisible(
  text: string,
  approved: ReadonlySet<number> = APPROVED_CARRIER_SET,
): string {
  let out = "";
  for (const character of text) {
    if (!approved.has(character.codePointAt(0)!)) out += character;
  }
  return out;
}

export function isCarrierInsertion(
  original: string,
  transformed: string,
  approved: ReadonlySet<number> = APPROVED_CARRIER_SET,
): boolean {
  const source = [...original];
  let index = 0;
  for (const character of transformed) {
    if (index < source.length && character === source[index]) {
      index += 1;
      continue;
    }
    if (approved.has(character.codePointAt(0)!)) continue;
    return false;
  }
  return index === source.length;
}

export function approvedCarrierList(): readonly number[] {
  return LETTER_MIX_APPROVED_CARRIERS;
}

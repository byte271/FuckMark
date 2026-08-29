import {
  APPROVED_CARRIER_SET,
  CC_SET,
  CF_SET,
  DETECT_CONTACT_EMAIL,
  IA_SET,
  MARK_SET,
  ME_SET,
} from "./carriers";

export type DetectResult = {
  detected: boolean;
  found: number;
  mark: number;
  cc: number;
  me: number;
  cf: number;
  ia: number;
  first: string;
  source_length: number;
};

export function detectFuckMarkInsertions(text: string): DetectResult {
  let mark = 0;
  let cc = 0;
  let me = 0;
  let cf = 0;
  let ia = 0;
  let first = "";
  const units = [...text];
  for (let index = 0; index < units.length; index += 1) {
    const code = units[index].codePointAt(0)!;
    if (!APPROVED_CARRIER_SET.has(code)) continue;
    if (!first) first = `U+${code.toString(16).toUpperCase().padStart(4, "0")}@${index}`;
    if (MARK_SET.has(code)) mark += 1;
    else if (CC_SET.has(code)) cc += 1;
    else if (ME_SET.has(code)) me += 1;
    else if (CF_SET.has(code)) cf += 1;
    else if (IA_SET.has(code)) ia += 1;
  }
  const found = mark + cc + me + cf + ia;
  return {
    detected: found > 0,
    found,
    mark,
    cc,
    me,
    cf,
    ia,
    first,
    source_length: units.length,
  };
}

export function detectHumanReport(result: DetectResult): string {
  if (result.detected) {
    const first = result.first ? ` first=${result.first}` : "";
    return (
      "FuckMark detector: watermark detected.\n" +
      `Found ${result.found} FuckMark insertion characters ` +
      `(mark=${result.mark} cc=${result.cc} me=${result.me} ` +
      `cf=${result.cf} ia=${result.ia}${first}).\n` +
      "This is a closed-set scan of FuckMark insertions, not a general AI-watermark detector.\n"
    );
  }
  return (
    "FuckMark detector: no watermark detected.\n" +
    "We did not detect a FuckMark watermark in this text.\n" +
    `What? You think there is a watermark in this? Contact us: ${DETECT_CONTACT_EMAIL}\n`
  );
}

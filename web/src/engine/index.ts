export {
  DETECT_CONTACT_EMAIL,
  ENGINE_ID,
  LETTER_MIX_APPROVED_CARRIERS,
  LETTER_MIX_INSERTIONS_PER_SITE,
  LETTER_MIX_MAX_SELECTED,
  PRODUCT_MAX_INPUT_CHARS,
  RELEASE_CLI_ALGORITHM_VERSION,
} from "./carriers";
export { detectFuckMarkInsertions, detectHumanReport, type DetectResult } from "./detect";
export { hardMachineIntervals } from "./protected";
export { isCarrierInsertion, projectVisible } from "./projection";
export {
  applyLetterAlternatingMix,
  composeLetterMix,
  firstUnmixedNonAscii,
  selectLetterMixSites,
} from "./letter-mix";
export {
  processText,
  removeMarksPayload,
  stripMarks,
  transformText,
  type ProcessResult,
  REASON_ALREADY_TRANSFORMED,
  REASON_NO_ELIGIBLE_SITES,
  REASON_SITE_CAP,
  REASON_TOO_LARGE,
  REASON_TRANSFORMED,
  REASON_UNSUPPORTED_DOMAIN,
} from "./product";

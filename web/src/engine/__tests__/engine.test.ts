import { describe, expect, it } from "vitest";
import fixtures from "../generated/fixtures.json";
import { detectFuckMarkInsertions } from "../detect";
import { hardMachineIntervals } from "../protected";
import { projectVisible } from "../projection";
import { selectLetterMixSites, composeLetterMix } from "../letter-mix";
import { transformText } from "../product";

type Case = {
  name: string;
  source: string;
  sites: number[];
  blocked: number[][];
  output: string;
  reason: string;
  change_count: number;
  site_count: number;
  capped: boolean;
  last_source_index: number | null;
  first_unsupported: string;
  source_length: number;
  detect_source: {
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
  detect_output: {
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
};

const cases = fixtures.cases as Case[];

describe("FuckMark JS engine vs Python goldens", () => {
  it("has generated cases", () => {
    expect(cases.length).toBeGreaterThan(20);
  });

  for (const row of cases) {
    it(row.name, () => {
      const detect = detectFuckMarkInsertions(row.source);
      expect(detect).toEqual(row.detect_source);

      const blocked = hardMachineIntervals(row.source);
      expect(blocked).toEqual(row.blocked.map(([start, end]) => [start, end]));

      const sites = selectLetterMixSites(row.source);
      expect(sites).toEqual(row.sites);

      const result = transformText(row.source);
      expect(result.reason).toBe(row.reason);
      expect(result.output_text).toBe(row.output);
      expect(result.change_count).toBe(row.change_count);
      expect(result.site_count).toBe(row.site_count);
      expect(result.capped).toBe(row.capped);
      expect(result.last_source_index).toBe(row.last_source_index);
      expect(result.first_unsupported).toBe(row.first_unsupported);
      expect(result.source_length).toBe(row.source_length);
      expect(detectFuckMarkInsertions(result.output_text)).toEqual(row.detect_output);
      expect(projectVisible(result.output_text)).toBe(
        row.reason === "already-transformed" ? projectVisible(row.source) : row.source,
      );
      if (row.sites.length && row.reason !== "already-transformed") {
        expect(composeLetterMix(row.source, row.sites)).toBe(row.output);
      }
    });
  }
});

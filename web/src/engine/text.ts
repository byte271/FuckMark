/** Code-point string helpers. Python 3 `str` indexes Unicode scalars, not UTF-16. */

export type ReMatch = {
  start: number;
  end: number;
  text: string;
  groups: (string | undefined)[];
};

export class UText {
  readonly raw: string;
  readonly units: string[];
  private readonly utf16At: number[];
  private readonly cpAt: Int32Array;

  constructor(raw: string) {
    this.raw = raw;
    this.units = [...raw];
    const utf16At = new Array<number>(this.units.length + 1);
    const cpAt = new Int32Array(raw.length + 1);
    let utf = 0;
    let cp = 0;
    utf16At[0] = 0;
    while (utf < raw.length) {
      cpAt[utf] = cp;
      const code = raw.codePointAt(utf)!;
      const width = code > 0xffff ? 2 : 1;
      if (width === 2) cpAt[utf + 1] = cp;
      utf += width;
      cp += 1;
      utf16At[cp] = utf;
    }
    cpAt[raw.length] = cp;
    this.utf16At = utf16At;
    this.cpAt = cpAt;
  }

  get length(): number {
    return this.units.length;
  }

  at(index: number): string {
    return this.units[index];
  }

  codePoint(index: number): number {
    return this.units[index].codePointAt(0)!;
  }

  slice(start: number, end?: number): string {
    return this.units.slice(start, end).join("");
  }

  cpIndex(utf16: number): number {
    if (utf16 < 0) return 0;
    if (utf16 >= this.raw.length) return this.units.length;
    return this.cpAt[utf16];
  }

  utf16Index(cp: number): number {
    if (cp <= 0) return 0;
    if (cp >= this.units.length) return this.raw.length;
    return this.utf16At[cp];
  }

  indexOf(sub: string, startCp = 0, endCp?: number): number {
    const from = this.utf16Index(startCp);
    const to = endCp === undefined ? this.raw.length : this.utf16Index(endCp);
    const region = this.raw.slice(from, to);
    const hit = region.indexOf(sub);
    if (hit < 0) return -1;
    return this.cpIndex(from + hit);
  }

  startsWith(sub: string, startCp: number): boolean {
    const n = [...sub].length;
    return this.slice(startCp, startCp + n) === sub;
  }
}

function withGlobal(re: RegExp): RegExp {
  const flags = re.flags.includes("g") ? re.flags : `${re.flags}g`;
  return new RegExp(re.source, flags);
}

export function findAll(re: RegExp, text: UText): ReMatch[] {
  const global = withGlobal(re);
  const out: ReMatch[] = [];
  let match: RegExpExecArray | null;
  while ((match = global.exec(text.raw)) !== null) {
    if (match[0].length === 0) {
      global.lastIndex += 1;
      continue;
    }
    out.push(toMatch(text, match));
  }
  return out;
}

export function searchFrom(re: RegExp, text: UText, startCp = 0): ReMatch | null {
  const global = withGlobal(re);
  global.lastIndex = text.utf16Index(startCp);
  const match = global.exec(text.raw);
  if (!match) return null;
  return toMatch(text, match);
}

function toMatch(text: UText, match: RegExpExecArray): ReMatch {
  return {
    start: text.cpIndex(match.index),
    end: text.cpIndex(match.index + match[0].length),
    text: match[0],
    groups: match.slice(1),
  };
}

export function bisectRight(values: readonly number[], point: number): number {
  let lo = 0;
  let hi = values.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (point < values[mid]) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

export function inRanges(code: number, ranges: ReadonlyArray<readonly [number, number]>): boolean {
  let lo = 0;
  let hi = ranges.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const [start, end] = ranges[mid];
    if (code < start) hi = mid - 1;
    else if (code > end) lo = mid + 1;
    else return true;
  }
  return false;
}

export function pyCasefold(value: string): string {
  return value.toLowerCase();
}

export function collapseWs(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

export function isPyDigit(character: string): boolean {
  return /^\p{Nd}$/u.test(character);
}

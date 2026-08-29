export function isIPv4Address(value: string): boolean {
  const parts = value.split(".");
  if (parts.length !== 4) return false;
  for (const part of parts) {
    if (!/^[0-9]+$/.test(part)) return false;
    if (part.length > 1 && part.startsWith("0")) return false;
    const n = Number(part);
    if (n > 255) return false;
  }
  return true;
}

export function isIPv6Address(value: string): boolean {
  let addr = value;
  const pct = value.indexOf("%");
  if (pct >= 0) {
    const zone = value.slice(pct + 1);
    if (!zone || /[^A-Za-z0-9._~-]/.test(zone)) return false;
    addr = value.slice(0, pct);
  }
  if (addr.includes(":::")) return false;
  const sides = addr.split("::");
  if (sides.length > 2) return false;

  const countSide = (side: string, allowIPv4: boolean): number | null => {
    if (side === "") return 0;
    const chunks = side.split(":");
    let count = 0;
    for (let i = 0; i < chunks.length; i += 1) {
      const chunk = chunks[i];
      if (chunk === "") return null;
      if (allowIPv4 && i === chunks.length - 1 && chunk.includes(".")) {
        if (!isIPv4Address(chunk)) return null;
        count += 2;
        continue;
      }
      if (!/^[0-9A-Fa-f]{1,4}$/.test(chunk)) return null;
      count += 1;
    }
    return count;
  };

  if (sides.length === 1) {
    const n = countSide(sides[0], true);
    return n === 8;
  }
  const left = countSide(sides[0], false);
  const right = countSide(sides[1], true);
  if (left === null || right === null) return false;
  return left + right < 8;
}

"""H16 exhaustive shaping closure scan.

Cross every assigned Unicode code point against two independent oracles:

1. The H12-H15 required sanitizer bundle treated as a carrier fixed point.
2. A HarfBuzz shaping oracle over the real Chromium ``pre`` font stack.

The shaping oracle replaces per-probe Chromium screenshots. It reports a code
point as invisible only when inserting it leaves both the total advance width
and the inked glyph sequence unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from fuckmark.cycle8.control_carrier import required_sanitizers_keep  # noqa: E402
from fuckmark.cycle8.unicode_meta import is_default_ignorable_v1  # noqa: E402

H16_RESEARCH_EXTRA_INSTALL = 'pip install -e ".[research]"'
CHROMIUM_PRE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
SHAPING_LEFT = "A"
SHAPING_RIGHT = "B"
SCAN_SOURCE = "I do not agree."


def _research_imports():
    try:
        import uharfbuzz as hb
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.ttLib import TTFont
    except ImportError as error:
        raise SystemExit(f"uharfbuzz and fonttools are required: {H16_RESEARCH_EXTRA_INSTALL}") from error
    return hb, BoundsPen, TTFont


class ShapingOracle:
    """Advance-width and ink-preserving invisibility oracle for one font."""

    def __init__(self, path: str) -> None:
        hb, bounds_pen, tt_font = _research_imports()
        self._hb = hb
        self._bounds_pen = bounds_pen
        self._path = path
        blob = hb.Blob.from_file_path(path)
        self._font = hb.Font(hb.Face(blob))
        tt = tt_font(path)
        self._glyph_order = tt.getGlyphOrder()
        self._glyph_set = tt.getGlyphSet()
        self._cmap = tt.getBestCmap() or {}
        self._ink_cache: dict[int, bool] = {}
        self._baseline = self._shape(SHAPING_LEFT + SHAPING_RIGHT)

    @property
    def path(self) -> str:
        return self._path

    def maps(self, codepoint: int) -> bool:
        return codepoint in self._cmap

    def _has_ink(self, gid: int) -> bool:
        cached = self._ink_cache.get(gid)
        if cached is not None:
            return cached
        pen = self._bounds_pen(self._glyph_set)
        try:
            self._glyph_set[self._glyph_order[gid]].draw(pen)
            inked = pen.bounds is not None
        except (KeyError, IndexError):
            inked = True
        self._ink_cache[gid] = inked
        return inked

    def _shape(self, text: str) -> tuple[tuple[int, int], ...]:
        buf = self._hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        self._hb.shape(self._font, buf)
        return tuple(
            (info.codepoint, pos.x_advance)
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions, strict=True)
        )

    def invisible(self, codepoint: int) -> bool:
        run = self._shape(SHAPING_LEFT + chr(codepoint) + SHAPING_RIGHT)
        if sum(advance for _, advance in run) != sum(advance for _, advance in self._baseline):
            return False
        inked = tuple(gid for gid, _ in run if self._has_ink(gid))
        return inked == tuple(gid for gid, _ in self._baseline if self._has_ink(gid))


def iter_assigned_codepoints():
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        if category == "Cn":
            continue
        yield codepoint, character, category


def scan() -> dict[str, object]:
    primary = ShapingOracle(CHROMIUM_PRE_FONT)
    fallbacks = [ShapingOracle(path) for path in FALLBACK_FONTS if Path(path).is_file()]

    survivors: list[dict[str, object]] = []
    assigned = 0
    sanitizer_survivors = 0
    shaping_invisible = 0
    category_counts: dict[str, int] = {}

    for codepoint, character, category in iter_assigned_codepoints():
        assigned += 1
        keeps = required_sanitizers_keep(f"I{character} do not agree.")
        if keeps:
            sanitizer_survivors += 1
        invisible_primary = primary.invisible(codepoint)
        if invisible_primary:
            shaping_invisible += 1
        if not (keeps and invisible_primary):
            continue
        invisible_everywhere = all(
            oracle.invisible(codepoint) for oracle in fallbacks if oracle.maps(codepoint)
        )
        category_counts[category] = category_counts.get(category, 0) + 1
        survivors.append(
            {
                "codepoint": f"U+{codepoint:04X}",
                "category": category,
                "default_ignorable": is_default_ignorable_v1(codepoint),
                "mapped_in_chromium_pre_font": primary.maps(codepoint),
                "invisible_in_every_mapping_fallback": invisible_everywhere,
                "name": _name(codepoint),
            }
        )

    return {
        "assigned_codepoints_scanned": assigned,
        "required_sanitizer_fixed_point_count": sanitizer_survivors,
        "shaping_invisible_count": shaping_invisible,
        "intersection_count": len(survivors),
        "intersection_categories": dict(sorted(category_counts.items())),
        "intersection": survivors,
        "chromium_pre_font": CHROMIUM_PRE_FONT,
        "fallback_fonts": [oracle.path for oracle in fallbacks],
    }


def _name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    payload = scan()
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

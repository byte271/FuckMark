from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from fuckmark.cycle8.control_carrier import required_sanitizers_keep
from fuckmark.cycle8.threat_model_audit import (
    CHROMIUM_PRE_FONT,
    H16_RESEARCH_EXTRA_INSTALL,
    SHAPING_FALLBACK_FONTS,
    SHAPING_LEFT,
    SHAPING_RIGHT,
)
from fuckmark.cycle8.unicode_meta import is_default_ignorable_v1


def _research_imports():
    try:
        import uharfbuzz as harfbuzz
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.ttLib import TTFont
    except ImportError as error:
        raise SystemExit(f"uharfbuzz and fonttools are required: {H16_RESEARCH_EXTRA_INSTALL}") from error
    return harfbuzz, BoundsPen, TTFont


class ShapingOracle:
    def __init__(self, path: str) -> None:
        harfbuzz, bounds_pen, tt_font = _research_imports()
        self._hb = harfbuzz
        self._bounds_pen = bounds_pen
        self._path = path
        self._font = harfbuzz.Font(harfbuzz.Face(harfbuzz.Blob.from_file_path(path)))
        font = tt_font(path)
        self._glyph_order = font.getGlyphOrder()
        self._glyph_set = font.getGlyphSet()
        self._cmap = font.getBestCmap() or {}
        self._ink_cache: dict[int, bool] = {}
        self._baseline = self._shape(SHAPING_LEFT + SHAPING_RIGHT)

    @property
    def path(self) -> str:
        return self._path

    def maps(self, codepoint: int) -> bool:
        return codepoint in self._cmap

    def _has_ink(self, glyph_id: int) -> bool:
        cached = self._ink_cache.get(glyph_id)
        if cached is not None:
            return cached
        pen = self._bounds_pen(self._glyph_set)
        try:
            self._glyph_set[self._glyph_order[glyph_id]].draw(pen)
            inked = pen.bounds is not None
        except (KeyError, IndexError):
            inked = True
        self._ink_cache[glyph_id] = inked
        return inked

    def _shape(self, text: str) -> tuple[tuple[int, int], ...]:
        buffer = self._hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        self._hb.shape(self._font, buffer)
        return tuple(
            (info.codepoint, position.x_advance)
            for info, position in zip(buffer.glyph_infos, buffer.glyph_positions, strict=True)
        )

    def _signature(self, run: tuple[tuple[int, int], ...]) -> tuple[int, tuple[int, ...]]:
        advance = sum(value for _, value in run)
        inked = tuple(glyph_id for glyph_id, _ in run if self._has_ink(glyph_id))
        return advance, inked

    def invisible(self, codepoint: int, left: str = SHAPING_LEFT, right: str = SHAPING_RIGHT) -> bool:
        baseline = self._baseline if (left, right) == (SHAPING_LEFT, SHAPING_RIGHT) else self._shape(left + right)
        return self._signature(self._shape(left + chr(codepoint) + right)) == self._signature(baseline)


def iter_assigned_codepoints():
    for codepoint in range(0x110000):
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        character = chr(codepoint)
        category = unicodedata.category(character)
        if category == "Cn":
            continue
        yield codepoint, character, category


def _name(codepoint: int) -> str | None:
    try:
        return unicodedata.name(chr(codepoint))
    except ValueError:
        return None


def scan() -> dict[str, object]:
    primary = ShapingOracle(CHROMIUM_PRE_FONT)
    fallbacks = [ShapingOracle(path) for path in SHAPING_FALLBACK_FONTS if Path(path).is_file()]

    survivors: list[dict[str, object]] = []
    invisible_codepoints: list[int] = []
    invisible_categories: dict[str, int] = {}
    assigned = 0
    sanitizer_survivors = 0
    intersection_categories: dict[str, int] = {}

    for codepoint, character, category in iter_assigned_codepoints():
        assigned += 1
        keeps = required_sanitizers_keep(f"I{character} do not agree.")
        if keeps:
            sanitizer_survivors += 1
        if not primary.invisible(codepoint):
            continue
        invisible_codepoints.append(codepoint)
        invisible_categories[category] = invisible_categories.get(category, 0) + 1
        if not keeps:
            continue
        intersection_categories[category] = intersection_categories.get(category, 0) + 1
        survivors.append(
            {
                "codepoint": f"U+{codepoint:04X}",
                "category": category,
                "default_ignorable": is_default_ignorable_v1(codepoint),
                "mapped_in_chromium_pre_font": primary.maps(codepoint),
                "invisible_in_every_mapping_fallback": all(
                    oracle.invisible(codepoint) for oracle in fallbacks if oracle.maps(codepoint)
                ),
                "name": _name(codepoint),
            }
        )

    control_survivors = [
        codepoint
        for codepoint in range(0x110000)
        if unicodedata.category(chr(codepoint)) == "Cc"
        and required_sanitizers_keep(f"I{chr(codepoint)} do not agree.")
    ]

    return {
        "assigned_codepoints_scanned": assigned,
        "required_sanitizer_fixed_point_count": sanitizer_survivors,
        "shaping_invisible_count": len(invisible_codepoints),
        "shaping_invisible_categories": dict(sorted(invisible_categories.items())),
        "shaping_invisible_codepoints": [f"U+{value:04X}" for value in invisible_codepoints],
        "intersection_count": len(survivors),
        "intersection_categories": dict(sorted(intersection_categories.items())),
        "intersection": survivors,
        "cc_required_sanitizer_fixed_point_count": len(control_survivors),
        "cc_required_sanitizer_fixed_points": [f"U+{value:04X}" for value in control_survivors],
        "chromium_pre_font": CHROMIUM_PRE_FONT,
        "fallback_fonts": [oracle.path for oracle in fallbacks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="H16 exhaustive shaping closure scan")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()
    payload = scan()
    text = json.dumps(payload, indent=2, sort_keys=True)
    if arguments.out is not None:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

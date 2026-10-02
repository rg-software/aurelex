#!/usr/bin/env python3
"""Build the bundled Material Symbols Outlined subset font.

The app ships a tiny *secondary* icon font (family "Material Symbols
Outlined", ``app/res/fonts/MaterialSymbols-Outlined-subset.ttf``) holding only
the few Material Symbols glyphs the classic Material Icons font does not have.
Bundling the full ~10 MB variable font is pointless, so this script instances
and subsets it.

Recipe (see the groups-tab-polish / tri-state-theme-control designs):

1. Instance the upstream variable font at ``FILL=0, GRAD=0, opsz=24,
   wght=400`` (the app renders at 24 dp, regular weight).
2. Subset to exactly the codepoints in ``GLYPHS``.
3. Re-normalise the vertical metrics to the classic Material Icons font's
   1.0 em box: ``hhea``/OS-2 ``asc = upm``, ``desc = 0``, ``lineGap = 0``,
   ``USE_TYPO_METRICS`` set, ``post`` underline zeroed. Without this the
   subset's taller line box pushes a sibling label down ~11 px wherever the
   two families mix in one Text/Column.

Name -> codepoint authority:
  google/material-design-icons
  variablefont/MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints

Usage:
  python scripts/build_symbol_subset.py
  python scripts/build_symbol_subset.py --source /path/to/variablefont.ttf
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.subset import Options, Subsetter
from fontTools.varLib import instancer

# name -> codepoint, from the upstream .codepoints file. Keep this in sync with
# the symbolIcon() map in app/main.qml.
GLYPHS = {
    "folder_open": 0xE2C8,
    "match_word": 0xF6F0,
    "light_mode_auto": 0xFFF00,
    "text_decrease": 0xEADD,
    "text_increase": 0xEAE2,
}

VAR_SOURCE_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "variablefont/MaterialSymbolsOutlined%5BFILL%2CGRAD%2Copsz%2Cwght%5D.ttf"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "app" / "res" / "fonts" / "MaterialSymbols-Outlined-subset.ttf"


def load_source(path: Path | None) -> TTFont:
    if path is not None:
        return TTFont(path)
    print(f"downloading {VAR_SOURCE_URL}", file=sys.stderr)
    with urllib.request.urlopen(VAR_SOURCE_URL) as resp:
        data = resp.read()
    return TTFont(io.BytesIO(data))


def build(source: TTFont, out: Path, codepoints: dict[str, int]) -> TTFont:
    instance = instancer.instantiateVariableFont(
        source, {"FILL": 0, "GRAD": 0, "opsz": 24, "wght": 400}, inplace=False
    )

    opts = Options()
    opts.layout_features = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.glyph_names = True
    subsetter = Subsetter(options=opts)
    subsetter.populate(unicodes=list(codepoints.values()))
    subsetter.subset(instance)

    # Normalise metrics to a 1.0 em line box (see module docstring).
    upm = instance["head"].unitsPerEm
    instance["hhea"].ascent = upm
    instance["hhea"].descent = 0
    instance["hhea"].lineGap = 0
    instance["OS/2"].sTypoAscender = upm
    instance["OS/2"].sTypoDescender = 0
    instance["OS/2"].sTypoLineGap = 0
    instance["OS/2"].usWinAscent = upm
    instance["OS/2"].usWinDescent = 0
    instance["OS/2"].fsSelection |= 1 << 7  # USE_TYPO_METRICS
    instance["post"].underlinePosition = 0
    instance["post"].underlineThickness = 0

    out.parent.mkdir(parents=True, exist_ok=True)
    instance.save(out)
    return instance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="upstream Material Symbols Outlined variable font; downloaded if omitted",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    font = build(load_source(args.source), args.out, GLYPHS)

    cmap = font.getBestCmap()
    missing = [name for name, cp in GLYPHS.items() if cp not in cmap]
    if missing:
        print(f"ERROR: missing glyphs after subset: {missing}", file=sys.stderr)
        return 1
    print(
        f"wrote {args.out} "
        f"({args.out.stat().st_size} bytes, {len(cmap)} glyphs, upm {font['head'].unitsPerEm})"
    )
    for name, cp in GLYPHS.items():
        print(f"  U+{cp:04X} {name} -> {cmap[cp]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

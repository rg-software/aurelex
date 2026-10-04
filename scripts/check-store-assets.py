#!/usr/bin/env python3
"""Validate the Play store listing assets against the limits Play enforces.

    python scripts/check-store-assets.py [--listing-dir <dir>]

Reads only what is committed and never regenerates an asset, so it runs on a CI
image that has neither ImageMagick nor the Montserrat font the converter needs
(``scripts/make-store-screenshots.ps1``). PNG geometry comes from the IHDR chunk
in the file's first bytes, so there is no image dependency either -- which also
means this script and the converter cannot disagree about how to read a file.

``app/android/store-listing/listing.md`` states the same constraints in prose;
this script is the enforcing copy.

Every violation is reported, not just the first, because fixing assets one error
per run is the loop this exists to end.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path
from typing import NamedTuple

# --- Play's limits ----------------------------------------------------------
# Source for all of them: the Play Console graphic-asset requirements for phone
# screenshots, the app icon and the feature graphic, as documented for the Play
# Console's store-presence pages and mirrored in the Play Developer API's
# `edits.images` resource.
MIN_SCREENSHOTS = 2  # per language, Play asks for at least two
MAX_SCREENSHOTS = 8  # ...and accepts at most eight
MIN_SIDE_PX = 320  # each side must be at least this many pixels
MAX_SIDE_PX = 3840  # ...and at most this many
ACCEPTED_RATIOS = ((16, 9), (9, 16))  # landscape or portrait, nothing between
RATIO_TOLERANCE = 0.01  # relative, so a rounding artefact is not a failure
ICON_SIZE = (512, 512)  # the app-icon slot
FEATURE_GRAPHIC_SIZE = (1024, 500)  # the feature-graphic slot

# The numeric prefix IS the gallery order (hero first): the upload appends in
# file order, so the filename order is the published order. A file without one
# has no defined position in the gallery, which is itself an error.
ORDER_PREFIX = re.compile(r"^(\d+)-.+\.png$", re.IGNORECASE)

SCREENSHOT_DIR = "screenshots"
ICON_FILE = "play-store-icon-512.png"
FEATURE_GRAPHIC_FILE = "feature-graphic-1024x500.png"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class Screenshot(NamedTuple):
    """One committed phone screenshot."""

    path: Path
    width: int
    height: int
    depth: int  # bit depth; read from IHDR, reported for diagnostics
    colour_type: int  # IHDR colour type; ditto
    order: int | None  # the NN- prefix, or None when absent/unparsable
    digest: str  # sha256 of the whole file, for the duplicate rule


def read_geometry(path: Path) -> tuple[int, int, int, int]:
    """Return (width, height, bit depth, colour type) from the IHDR chunk.

    IHDR is required to be the first chunk of a PNG, and its data field is
    13 bytes: width, height, then bit depth and colour type. Only the first ten
    are needed, but the signature and the chunk header are checked too so a
    truncated or mislabelled file is reported as unreadable rather than being
    silently read as some other size.
    """
    with path.open("rb") as handle:
        head = handle.read(33)
    if len(head) < 33 or head[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG (bad or missing signature)")
    if head[12:16] != b"IHDR":
        raise ValueError("not a PNG (first chunk is not IHDR)")
    width, height, depth, colour_type = struct.unpack(">IIBB", head[16:26])
    return width, height, depth, colour_type


def order_of(path: Path) -> int | None:
    """Return the NN- gallery-order prefix of *path*, or None when it has none."""
    match = ORDER_PREFIX.match(path.name)
    return int(match.group(1)) if match else None


def format_ratio(width: int, height: int) -> str:
    """A readable width:height for a failure message."""
    return f"{width}:{height}"


def ratio_label(width: int, height: int) -> str:
    """Name the accepted ratio *width* x *height* is closest to."""
    actual = width / height
    best = min(ACCEPTED_RATIOS, key=lambda r: abs(actual - r[0] / r[1]))
    return f"{best[0]}:{best[1]}"


def load_screenshots(
    directory: Path, violations: list[str]
) -> list[Screenshot]:
    """Read every PNG in the gallery, reporting unreadable ones as violations."""
    if not directory.is_dir():
        violations.append(
            f"{directory}: phone screenshot directory is missing "
            f"(Play accepts {MIN_SCREENSHOTS}-{MAX_SCREENSHOTS} per language)"
        )
        return []

    shots: list[Screenshot] = []
    for path in sorted(directory.glob("*.png")):
        try:
            width, height, depth, colour_type = read_geometry(path)
        except (OSError, ValueError) as exc:
            violations.append(f"{path.name}: cannot read PNG header ({exc})")
            continue
        shots.append(
            Screenshot(
                path=path,
                width=width,
                height=height,
                depth=depth,
                colour_type=colour_type,
                order=order_of(path),
                digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return shots


def check_count(shots: list[Screenshot], violations: list[str]) -> None:
    """The gallery must hold a number of screenshots Play accepts."""
    count = len(shots)
    if not MIN_SCREENSHOTS <= count <= MAX_SCREENSHOTS:
        violations.append(
            f"phone screenshots: {count} file(s) committed, Play accepts "
            f"{MIN_SCREENSHOTS}-{MAX_SCREENSHOTS} per language"
        )


def check_geometry(shots: list[Screenshot], violations: list[str]) -> None:
    """Each screenshot must fit Play's per-side bounds and aspect ratio."""
    for shot in shots:
        for side, value in (("width", shot.width), ("height", shot.height)):
            if not MIN_SIDE_PX <= value <= MAX_SIDE_PX:
                violations.append(
                    f"{shot.path.name}: {side} {value} px is outside Play's "
                    f"{MIN_SIDE_PX}-{MAX_SIDE_PX} px per-side bound"
                )
        actual = shot.width / shot.height
        if all(
            abs(actual - r[0] / r[1]) / (r[0] / r[1]) > RATIO_TOLERANCE
            for r in ACCEPTED_RATIOS
        ):
            accepted = " or ".join(f"{a}:{b}" for a, b in ACCEPTED_RATIOS)
            violations.append(
                f"{shot.path.name}: {shot.width}x{shot.height} is "
                f"{format_ratio(shot.width, shot.height)} "
                f"(~{actual:.4f}), Play accepts {accepted} "
                f"(within {RATIO_TOLERANCE:.0%}); nearest is "
                f"{ratio_label(shot.width, shot.height)}"
            )


def check_uniqueness(shots: list[Screenshot], violations: list[str]) -> None:
    """No two screenshots may be byte-identical.

    This is the rule that catches the orphan a renamed capture leaves behind:
    the name changed, the bytes did not.
    """
    by_digest: dict[str, list[str]] = {}
    for shot in shots:
        by_digest.setdefault(shot.digest, []).append(shot.path.name)
    for names in by_digest.values():
        if len(names) > 1:
            violations.append(
                f"duplicate content: {', '.join(sorted(names))} are "
                f"byte-identical ({len(names)} copies of one screenshot); "
                f"remove the stale one"
            )


def check_order(shots: list[Screenshot], violations: list[str]) -> None:
    """NN- prefixes must be unique and contiguous from 1."""
    unnumbered = [s.path.name for s in shots if s.order is None]
    if unnumbered:
        violations.append(
            f"{', '.join(sorted(unnumbered))}: no NN- gallery-order prefix, "
            f"so it has no defined position in the published gallery"
        )

    numbered = [s for s in shots if s.order is not None]
    by_number: dict[int, list[str]] = {}
    for shot in numbered:
        by_number.setdefault(shot.order, []).append(shot.path.name)
    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            violations.append(
                f"prefix {number}: shared by {', '.join(sorted(names))}; "
                f"the gallery order would not be what the filenames claim"
            )

    present = sorted(by_number)
    if present and present != list(range(1, len(present) + 1)):
        violations.append(
            f"gallery-order prefixes are {', '.join(map(str, present))}, "
            f"expected 1-{len(present)} with no gaps"
        )


def check_fixed_asset(
    path: Path, required: tuple[int, int], label: str, violations: list[str]
) -> tuple[int, int] | None:
    """Assert a fixed-size listing asset is present at exactly its size."""
    if not path.is_file():
        violations.append(
            f"{path.name}: {label} is missing (Play requires "
            f"{required[0]}x{required[1]})"
        )
        return None
    try:
        width, height, _, _ = read_geometry(path)
    except (OSError, ValueError) as exc:
        violations.append(f"{path.name}: {label} cannot be read ({exc})")
        return None
    if (width, height) != required:
        violations.append(
            f"{path.name}: {label} is {width}x{height}, Play requires "
            f"{required[0]}x{required[1]}"
        )
        return None
    return width, height


def validate(listing_dir: Path) -> tuple[list[str], list[Screenshot]]:
    """Run every rule, collecting all violations rather than stopping at one."""
    violations: list[str] = []
    shots = load_screenshots(listing_dir / SCREENSHOT_DIR, violations)
    check_count(shots, violations)
    check_geometry(shots, violations)
    check_uniqueness(shots, violations)
    check_order(shots, violations)
    check_fixed_asset(listing_dir / ICON_FILE, ICON_SIZE, "listing icon", violations)
    check_fixed_asset(
        listing_dir / FEATURE_GRAPHIC_FILE,
        FEATURE_GRAPHIC_SIZE,
        "feature graphic",
        violations,
    )
    return violations, shots


def summarise(shots: list[Screenshot], listing_dir: Path) -> str:
    """One line naming what a passing run actually checked."""
    sizes = sorted({(s.width, s.height) for s in shots})
    gallery = ", ".join(f"{w}x{h}" for w, h in sizes) or "none"
    return (
        f"OK  {len(shots)} phone screenshot(s) at {gallery}, "
        f"listing icon {ICON_SIZE[0]}x{ICON_SIZE[1]}, "
        f"feature graphic {FEATURE_GRAPHIC_SIZE[0]}x{FEATURE_GRAPHIC_SIZE[1]}, "
        f"unique content and contiguous NN- order from 1"
    )


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Check the committed Play store listing assets."
    )
    parser.add_argument(
        "--listing-dir",
        type=Path,
        default=repo_root / "app" / "android" / "store-listing",
        help="store-listing directory to check (default: the repository's)",
    )
    args = parser.parse_args(argv)

    violations, shots = validate(args.listing_dir)
    if violations:
        print(
            f"FAIL  {len(violations)} violation(s) in {args.listing_dir}:",
            file=sys.stderr,
        )
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print(summarise(shots, args.listing_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
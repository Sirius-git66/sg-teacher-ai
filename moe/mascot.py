"""Procedurally generate the teacher mascot as pixel layers.

    python -m moe.mascot          → print an ASCII preview
    python moe/mascot.py > site/mascot-grid.js

Why the artwork is generated rather than drawn
-----------------------------------------------

The reference design used a cat rendered as scanline dithering. That technique
is reusable, but the ART is not ours to copy -- so the teacher is defined here
as geometry (circles, rects, lines) that this project owns outright, and
emitted as three pixel layers:

    base   head, hair, glasses, torso, legs
    arm    the raised arm and its pointer, as a separate layer so it can sway
    eyes   the exact cells that are eyes, so a blink is a two-line mutation

One source of truth. The canvas renderer AND the no-JS SVG fallback are both
generated from these layers, which means the fallback can never drift from the
animated version -- the same rule the whole site follows for its facts.

The cuteness is a proportion problem, not a drawing problem: oversized head,
small body, round glasses, hard 1-bit shading. Cute comes from the silhouette
and the contrast, not from curves or colour.
"""

from __future__ import annotations

import json
import sys

W = H = 32          # source resolution. Small on purpose: dithering needs
                    # room to breathe, and 32px is the poster-era default.

#: character → luminance 0..1. These drive the Bayer threshold, so the values
#: are chosen for how they DITHER, not for how they look flat. Paper is 1.0
#: (never inked) and skin sits high enough to stipple into a light tone, but
#: not so high that it turns into paper -- the face has to be visibly distinct
#: from the background or the character dissolves.
INK = {
    ".": 1.00,   # paper, untouched
    "K": 0.00,   # pure ink: outlines, glasses frames, pupils
    "D": 0.10,   # dark: hair mass
    "M": 0.38,   # mid: shading inside hair, sleeve shadow
    "L": 0.62,   # skin
    "W": 0.80,   # shirt / cloth
    "S": 0.22,   # shoes, pointer
}


class Layer:
    """A mutable 2D character grid."""

    def __init__(self, w: int = W, h: int = H, fill: str = ".") -> None:
        self.w, self.h = w, h
        self.g = [[fill] * w for _ in range(h)]

    def put(self, x: int, y: int, ch: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = ch

    def rect(self, x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, ch)

    def frame(self, x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        for x in range(x0, x1 + 1):
            self.put(x, y0, ch)
            self.put(x, y1, ch)
        for y in range(y0, y1 + 1):
            self.put(x0, y, ch)
            self.put(x1, y, ch)

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, ch: str) -> None:
        """Inclusive bounding box, filled. Integer-only -- no float rounding
        surprises at this resolution."""
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                dx = (x - cx) / max(1, rx)
                dy = (y - cy) / max(1, ry)
                if dx * dx + dy * dy <= 1.05:
                    self.put(x, y, ch)

    def ring(self, cx: int, cy: int, rx: int, ry: int, ch: str,
             top: bool = True) -> None:
        """Ellipse outline. `top=False` skips the crown so a shape can be
        merged into something drawn behind it."""
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                dx = (x - cx) / max(1, rx)
                dy = (y - cy) / max(1, ry)
                d = dx * dx + dy * dy
                if 0.55 <= d <= 1.05 and (top or dy <= 0.15):
                    self.put(x, y, ch)

    def line(self, x0: int, y0: int, x1: int, y1: int, ch: str) -> None:
        n = max(abs(x1 - x0), abs(y1 - y0))
        if n == 0:                      # a "line" from a point to itself
            self.put(x0, y0, ch)        # is a point, not a crash
            return
        for i in range(n + 1):
            self.put(round(x0 + (x1 - x0) * i / n),
                     round(y0 + (y1 - y0) * i / n), ch)

    def rows(self) -> list[str]:
        return ["".join(r) for r in self.g]

    def luminance(self) -> list[list[float]]:
        return [[INK[ch] for ch in row] for row in self.g]


# ---------------------------------------------------------------------------
# The character. Chibi proportions: head is 16px of a 32px figure.
# ---------------------------------------------------------------------------

HEAD_CX, HEAD_CY, HEAD_RX, HEAD_RY = 16, 11, 8, 7
EYE_L, EYE_R = 13, 19
EYE_Y = 11


def build_base() -> tuple[Layer, Layer]:
    """Returns (base, eyes). Eyes are recorded, not drawn -- a blink has to be
    able to restore what it covered."""
    base = Layer()

    # --- torso FIRST, so the head ellipse drawn later cannot erase the ------
    # --- shoulders. Draw order is the whole game at 32px.                 ---
    base.rect(HEAD_CX - 7, 21, HEAD_CX + 7, 27, "W")
    base.frame(HEAD_CX - 7, 21, HEAD_CX + 7, 27, "K")
    base.line(HEAD_CX, 21, HEAD_CX - 2, 27, "M")
    base.line(HEAD_CX, 21, HEAD_CX + 2, 27, "M")

    # --- neck sits between head and collar, so it is drawn after the head ---
    base.rect(HEAD_CX - 2, 18, HEAD_CX + 2, 20, "L")

    # --- hair behind the head: a wider ellipse, so hair reads as volume -----
    base.ellipse(HEAD_CX, HEAD_CY - 1, HEAD_RX + 1, HEAD_RY, "D")

    # --- bun, the single strongest cute signal at this size -----------------
    base.ellipse(24, 5, 3, 3, "D")
    base.ring(24, 5, 3, 3, "K", top=False)

    # --- face ---------------------------------------------------------------
    base.ellipse(HEAD_CX, HEAD_CY + 1, HEAD_RX - 1, HEAD_RY - 1, "L")

    # --- fringe: a hard horizontal edge is what makes it read as a haircut ---
    base.rect(HEAD_CX - 7, 4, HEAD_CX + 7, 6, "D")
    for x in range(HEAD_CX - 6, HEAD_CX + 5):
        base.put(x, 7, "M")

    # --- glasses: two rings and a bridge. Round frames = approachable. ------
    base.ring(EYE_L, EYE_Y, 3, 3, "K")
    base.ring(EYE_R, EYE_Y, 3, 3, "K")
    base.line(EYE_L + 3, EYE_Y, EYE_R - 3, EYE_Y, "K")

    # --- mouth: two pixels. A smile drawn as geometry reads as a frown. ------
    base.put(HEAD_CX, 15, "K")
    base.put(HEAD_CX - 1, 16, "K")
    base.put(HEAD_CX + 1, 16, "K")

    # --- legs + shoes -------------------------------------------------------
    base.rect(HEAD_CX - 5, 28, HEAD_CX - 1, 30, "W")
    base.rect(HEAD_CX + 1, 28, HEAD_CX + 5, 30, "W")
    base.rect(HEAD_CX - 6, 30, HEAD_CX - 1, 31, "S")
    base.rect(HEAD_CX + 1, 30, HEAD_CX + 6, 31, "S")

    # --- hanging arm, on the base layer (it does not gesture) --------------
    base.line(HEAD_CX - 7, 22, HEAD_CX - 9, 27, "K")
    base.ellipse(HEAD_CX - 9, 28, 1, 1, "L")

    # --- eyes ---------------------------------------------------------------
    eyes = Layer()
    eyes.rect(EYE_L - 1, EYE_Y - 1, EYE_L + 1, EYE_Y + 1, "K")
    eyes.rect(EYE_R - 1, EYE_Y - 1, EYE_R + 1, EYE_Y + 1, "K")

    return base, eyes


def build_arm() -> Layer:
    """Raised arm + pointer, isolated so it can sway on its own.

    Swaying a whole arm layer means translating a handful of pixels, which is
    cheap and, unlike redrawing geometry, cannot drift out of alignment.
    """
    arm = Layer()
    arm.line(HEAD_CX + 7, 22, 26, 14, "K")
    arm.ellipse(26, 13, 2, 2, "L")
    arm.line(26, 13, 27, 3, "S")
    return arm


def payload() -> dict:
    base, eyes = build_base()
    arm = build_arm()
    return {
        "w": W, "h": H,
        "lum": INK,
        "base": base.rows(),
        "arm": arm.rows(),
        "eyes": eyes.rows(),
        "eye_l": [EYE_L, EYE_Y],
        "eye_r": [EYE_R, EYE_Y],
    }


RAMP = " .:-=+*#%@"   # paper → full ink, by luminance


def _preview() -> None:
    import math
    base, eyes = build_base()
    arm = build_arm()
    print()
    for y in range(H):
        line = ""
        for x in range(W):
            if arm.g[y][x] != ".":
                line += "+"          # arm layer shown separately
                continue
            ch = base.g[y][x]
            if eyes.g[y][x] != ".":
                line += "O"          # eyes
                continue
            # INK is luminance (1.0 = paper). The ramp is a visual density
            # ramp, so it must be INVERTED: bright pixels get sparse marks.
            i = int((1.0 - INK[ch]) * (len(RAMP) - 1) + 0.5)
            line += RAMP[min(len(RAMP) - 1, i)]
        print(f"  |{line}|")
    print()
    print(f"  eyes at x={EYE_L},{EYE_R} y={EYE_Y}   O=eyes  +=arm layer")
    print(f"  ramp: {RAMP[0]} paper → {RAMP[-1]} solid ink")
    print()
    print("  Note this is FLAT luminance. The ditherer turns these values into")
    print("  scanline dashes, so mid greys stipple rather than fill.")
    print()


if __name__ == "__main__":
    if "--js" in sys.argv:
        sys.stdout.write("window.MOE_MASCOT=" +
                         json.dumps(payload(), ensure_ascii=False) + ";")
    else:
        _preview()

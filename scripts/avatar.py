#!/usr/bin/env python3
"""Render profile-picture options, plus a contact sheet that shows each one at
the size GitHub actually uses most (40px) next to the size people think about.

    python3 scripts/avatar.py [outdir]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 512          # final avatar size
SS = 4           # supersample factor for smooth edges
BG = (13, 17, 23)        # GitHub dark canvas
EMBER_A = (255, 209, 102)
EMBER_B = (255, 140, 66)
GREEN = (63, 185, 80)
WHITE = (230, 237, 243)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

BOLT = [(62, 0), (14, 84), (44, 84), (32, 140), (90, 50), (58, 50), (80, 0)]


def ember(size: int) -> Image.Image:
    """Vertical ember gradient, used as the fill for whatever shape masks it."""
    g = Image.new("RGB", (1, size))
    px = g.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(EMBER_A, EMBER_B))
    return g.resize((size, size))


def fit_bolt(box: int, pad: float) -> list[tuple[float, float]]:
    xs = [p[0] for p in BOLT]
    ys = [p[1] for p in BOLT]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = (box - 2 * pad) / h
    ox = (box - w * scale) / 2 - min(xs) * scale
    oy = pad - min(ys) * scale
    return [(x * scale + ox, y * scale + oy) for x, y in BOLT]


def option_a() -> Image.Image:
    """The bolt. Reads at any size, matches the card's logo."""
    big = S * SS
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon(fit_bolt(big, big * 0.11), fill=255)
    mask = mask.resize((S, S), Image.LANCZOS)
    img = Image.new("RGB", (S, S), BG)
    img.paste(ember(S), (0, 0), mask)
    return img


def option_b() -> Image.Image:
    """A shell prompt. The most legible of the three at 40px, and it is the
    same prompt the README card opens with."""
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(MONO, 250)
    d.text((S * 0.17, S * 0.46), ">", font=f, fill=GREEN, anchor="lm")
    # a block cursor, drawn rather than typed so its weight is deliberate
    bw, bh = S * 0.17, S * 0.27
    bx, by = S * 0.50, S * 0.50
    d.rectangle([bx, by - bh / 2, bx + bw, by + bh / 2], fill=WHITE)
    return img


def option_c() -> Image.Image:
    """The bolt as actual ASCII characters, the same art as the README."""
    # A monospace cell is 0.6em wide and 1em tall, so a 1:1 grid stretches the
    # art sideways. cols/rows has to match the bolt's own 0.54 aspect.
    cols, rows = 13, 18
    glyphs = render_ascii(cols, rows)
    img = Image.new("RGB", (S, S), BG)
    grad = ember(S)
    layer = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(layer)
    cell_h = S * 0.70 / rows
    f = ImageFont.truetype(MONO, int(cell_h * 1.25))
    # ADVANCE width, not the ink bbox. getbbox leaves out side bearings, so the
    # grid came out narrow and the whole bolt drifted right of centre.
    cell_w = f.getlength("@")
    x0 = (S - cols * cell_w) / 2
    y0 = (S - rows * cell_h) / 2
    for r, line in enumerate(glyphs):
        for c, ch in enumerate(line):
            if ch != " ":
                d.text((x0 + c * cell_w, y0 + r * cell_h), ch, font=f, fill=255)
    img.paste(grad, (0, 0), layer)
    return img


def render_ascii(cols: int, rows: int) -> list[str]:
    """Coarse ASCII bolt. Fewer cells than the README card uses, because at
    avatar size dense art turns into noise."""
    ramp = " .:-=+*#%@"
    xs = [p[0] for p in BOLT]
    ys = [p[1] for p in BOLT]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0, max(ys) - y0
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            hits = 0
            for sy in range(4):
                for sx in range(4):
                    px = x0 + (c + (sx + 0.5) / 4) * w / cols
                    py = y0 + (r + (sy + 0.5) / 4) * h / rows
                    hits += inside(px, py)
            cov = hits / 16
            line.append(" " if cov == 0 else ramp[min(9, int(cov * 10))])
        out.append("".join(line))
    return out


def inside(px: float, py: float) -> bool:
    hit = False
    j = len(BOLT) - 1
    for i, (xi, yi) in enumerate(BOLT):
        xj, yj = BOLT[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def circle(img: Image.Image) -> Image.Image:
    """GitHub crops avatars to a circle, so judge them cropped."""
    big = img.size[0] * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big, big], fill=255)
    out = img.copy()
    out.putalpha(mask.resize(img.size, Image.LANCZOS))
    return out


def sheet(opts: list[tuple[str, Image.Image]]) -> Image.Image:
    big, small, gap, pad = 240, 40, 56, 48
    w = pad * 2 + len(opts) * big + (len(opts) - 1) * gap
    h = pad * 2 + big + 96
    img = Image.new("RGB", (w, h), (8, 10, 14))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(MONO, 22)
    fs = ImageFont.truetype(MONO_REG, 15)
    for i, (name, av) in enumerate(opts):
        x = pad + i * (big + gap)
        img.paste(circle(av.resize((big, big), Image.LANCZOS)), (x, pad),
                  circle(av.resize((big, big), Image.LANCZOS)))
        d.text((x, pad + big + 18), name, font=f, fill=WHITE)
        img.paste(circle(av.resize((small, small), Image.LANCZOS)),
                  (x, pad + big + 48),
                  circle(av.resize((small, small), Image.LANCZOS)))
        d.text((x + small + 12, pad + big + 60), "actual size in a\ncommit list",
               font=fs, fill=(120, 128, 140))
    return img


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    opts = [("A  bolt", option_a()),
            ("B  prompt", option_b()),
            ("C  ascii bolt", option_c())]
    for name, img in opts:
        tag = name.split()[0].lower()
        img.save(out / f"avatar-{tag}.png")
    sheet(opts).save(out / "avatar-options.png")
    print(f"wrote {out}/avatar-options.png and avatar-a/b/c.png")


if __name__ == "__main__":
    main()

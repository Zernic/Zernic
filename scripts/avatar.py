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


# ------------------------------------------------- second set (2026-10-04)
# He liked B, so three more in the prompt family plus three from the other
# half of what he does. All judged circle-cropped at 40px, same as the first.

import math


def _prompt(cursor: str, chev: str = ">", chev_col=GREEN, cur_col=WHITE,
            bolt_cursor: bool = False) -> Image.Image:
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(MONO, 250)
    d.text((S * 0.17, S * 0.46), chev, font=f, fill=chev_col, anchor="lm")
    if bolt_cursor:
        big = S * SS
        mask = Image.new("L", (big, big), 0)
        pts = [(x * 0.44 + big * 0.47, y * 0.44 + big * 0.27)
               for x, y in fit_bolt(big, big * 0.12)]
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        img.paste(ember(S), (0, 0), mask.resize((S, S), Image.LANCZOS))
        return img
    if cursor == "block":
        bw, bh = S * 0.17, S * 0.27
        bx, by = S * 0.50, S * 0.50
        d.rectangle([bx, by - bh / 2, bx + bw, by + bh / 2], fill=cur_col)
    else:                                    # underscore
        bw, bh = S * 0.24, S * 0.055
        bx, by = S * 0.50, S * 0.63
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2, fill=cur_col)
    return img


def option_d() -> Image.Image:
    """`>_` - the underscore cursor instead of the block. Lighter."""
    return _prompt("under")


def option_e() -> Image.Image:
    """`$` in ember with a block cursor. Reads as a shell without the chevron
    everyone uses."""
    return _prompt("block", chev="$", chev_col=EMBER_A)


def option_f() -> Image.Image:
    """B, but the cursor is the bolt. Merges the prompt and the logo."""
    return _prompt("block", bolt_cursor=True)


def option_g() -> Image.Image:
    """Camera aperture. The film half, and an iris is geometric enough to
    survive 40px where a camera body would not."""
    big = S * SS
    c, R, r = big / 2, big * 0.38, big * 0.38 * 0.44
    disc = Image.new("L", (big, big), 0)
    ImageDraw.Draw(disc).ellipse([c - R, c - R, c + R, c + R], fill=255)
    d = ImageDraw.Draw(disc)
    hexa = [(c + r * math.cos(math.radians(60 * i - 90)),
             c + r * math.sin(math.radians(60 * i - 90))) for i in range(6)]
    d.polygon(hexa, fill=0)
    for i, (vx, vy) in enumerate(hexa):           # the blade separations
        a = math.radians(60 * i - 90 + 62)
        d.line([vx, vy, c + R * 1.1 * math.cos(a), c + R * 1.1 * math.sin(a)],
               fill=0, width=int(big * 0.016))
    img = Image.new("RGB", (S, S), BG)
    img.paste(ember(S), (0, 0), disc.resize((S, S), Image.LANCZOS))
    return img


def option_h() -> Image.Image:
    """Waveform. The music half, and bars are the most legible thing there is
    at small sizes."""
    heights = [0.30, 0.58, 0.92, 0.46, 0.76, 0.34, 0.62]
    big = S * SS
    layer = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(layer)
    span_w = big * 0.62
    bw = span_w / (len(heights) * 2 - 1)
    x = (big - span_w) / 2
    for h in heights:
        bh = big * 0.62 * h
        d.rounded_rectangle([x, big / 2 - bh / 2, x + bw, big / 2 + bh / 2],
                            radius=bw / 2, fill=255)
        x += bw * 2
    img = Image.new("RGB", (S, S), BG)
    img.paste(ember(S), (0, 0), layer.resize((S, S), Image.LANCZOS))
    return img


def option_i() -> Image.Image:
    """The bolt knocked OUT of a filled ember disc. Same mark, opposite
    weight - a solid shape instead of a thin one, which holds up better when
    the avatar is 20px in a hover card."""
    big = S * SS
    disc = Image.new("L", (big, big), 0)
    dd = ImageDraw.Draw(disc)
    R = big * 0.40
    dd.ellipse([big / 2 - R, big / 2 - R, big / 2 + R, big / 2 + R], fill=255)
    dd.polygon(fit_bolt(big, big * 0.20), fill=0)
    img = Image.new("RGB", (S, S), BG)
    img.paste(ember(S), (0, 0), disc.resize((S, S), Image.LANCZOS))
    return img


SET2 = [("D  >_", option_d), ("E  $ block", option_e), ("F  bolt cursor", option_f),
        ("G  aperture", option_g), ("H  waveform", option_h), ("I  bolt disc", option_i)]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    if "--set2" in sys.argv:
        opts = [(n, fn()) for n, fn in SET2]
        for name, img in opts:
            img.save(out / f"avatar-{name.split()[0].lower()}.png")
        sheet(opts[:3]).save(out / "avatar-options-2a.png")
        sheet(opts[3:]).save(out / "avatar-options-2b.png")
        print(f"wrote {out}/avatar-options-2a.png + 2b.png and avatar-d..i.png")
        return
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

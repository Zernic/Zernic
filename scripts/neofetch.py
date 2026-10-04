#!/usr/bin/env python3
"""Render the neofetch-style card on my profile README.

Pulls what it can from the GitHub API and falls back to scripts/langs-snapshot.json
(byte totals only, no repo names) so the private half of my work still counts.
Writes assets/neofetch-dark.svg and assets/neofetch-light.svg.

Run it with no token and it still works, it just sees the public half.

  python3 scripts/neofetch.py            # write both SVGs
  python3 scripts/neofetch.py --print    # dump the numbers it computed
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = "Zernic"

# utopia (2024) has node_modules committed, which is 7.9MB of vendored
# JavaScript. Counting it makes the language bar a measurement artifact.
SKIP_REPOS = {"utopia"}

GRAPHQL = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        name
        isPrivate
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------- data

def api(token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GRAPHQL, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-neofetch",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def collect() -> dict:
    """Public data from the API, private data from the committed snapshot."""
    snapshot = json.loads((ROOT / "scripts" / "langs-snapshot.json").read_text())
    langs: dict[str, int] = {}
    colors: dict[str, str] = dict(snapshot.get("colors", {}))
    repo_count = snapshot.get("fallbackRepoCount", 0)
    created = snapshot.get("createdAt", "2020-07-30T04:02:31Z")

    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN") or ""
    if token:
        try:
            user = api(token)
            created = user["createdAt"]
            repo_count = user["repositories"]["totalCount"]
            for repo in user["repositories"]["nodes"]:
                if repo["name"] in SKIP_REPOS:
                    continue
                for edge in repo["languages"]["edges"]:
                    name = edge["node"]["name"]
                    langs[name] = langs.get(name, 0) + edge["size"]
                    colors.setdefault(name, edge["node"]["color"] or "#8b8b93")
        except (urllib.error.URLError, RuntimeError, KeyError) as exc:
            print(f"api lookup failed ({exc}), using snapshot only", file=sys.stderr)

    # A token scoped to this repo alone sees only the public half, so the
    # snapshot (full totals, taken by hand with a wider token) wins where it is
    # larger. A real PAT always reports at least as much, so it wins instead.
    for name, size in snapshot["languages"].items():
        if size > langs.get(name, 0):
            langs[name] = size

    total = sum(langs.values()) or 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    return {
        "created": created,
        "repos": max(repo_count, snapshot.get("fallbackRepoCount", 0)),
        "bytes": total,
        "languages": [
            {"name": n, "size": s, "pct": 100 * s / total,
             "color": colors.get(n, "#8b8b93")}
            for n, s in ranked
        ],
    }


def uptime(created_iso: str, now: datetime) -> str:
    born = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
    years = now.year - born.year
    months = now.month - born.month
    days = now.day - born.day
    if days < 0:
        months -= 1
        days += 30
    if months < 0:
        years -= 1
        months += 12
    parts = [f"{years} years"]
    if months:
        parts.append(f"{months} months")
    if days:
        parts.append(f"{days} days")
    return ", ".join(parts)


def human_bytes(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    return f"{n / 1_000:.0f} KB"


# ---------------------------------------------------------------- drawing

DARK = {
    "card": "#161b22",
    "edge": "#30363d",
    "bar": "#21262d",
    "fg": "#e6edf3",
    "key": "#ffa657",
    "val": "#a5d6ff",
    "sect": "#d2a8ff",
    "dim": "#8b949e",
    "faint": "#6e7681",
    "bolt_a": "#ffd166",
    "bolt_b": "#ff8c42",
    "track": "#21262d",
}

LIGHT = {
    "card": "#ffffff",
    "edge": "#d0d7de",
    "bar": "#f6f8fa",
    "fg": "#1f2328",
    "key": "#953800",
    "val": "#0550ae",
    "sect": "#8250df",
    "dim": "#636c76",
    "faint": "#8c959f",
    "bolt_a": "#e3a008",
    "bolt_b": "#bc4c00",
    "track": "#eaeef2",
}

MONO = "ui-monospace,'SF Mono',SFMono-Regular,'JetBrains Mono','Cascadia Mono',Menlo,Consolas,'Liberation Mono',monospace"

# The logo is a real lightning bolt polygon rasterised onto a grid, so it keeps
# the blocky terminal feel without turning into a staircase the way a hand-drawn
# low-resolution one does.
BOLT_POLY = [(62, 0), (14, 84), (44, 84), (32, 140), (90, 50), (58, 50), (80, 0)]
BOLT_COLS, BOLT_ROWS = 15, 23
BOLT_CELL, BOLT_GAP = 7, 1


def _inside(px: float, py: float, poly: list[tuple[int, int]]) -> bool:
    hit = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def bolt_cells() -> list[tuple[int, int]]:
    """Grid cells whose centre falls inside the bolt."""
    xs = [p[0] for p in BOLT_POLY]
    ys = [p[1] for p in BOLT_POLY]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    cells = []
    for r in range(BOLT_ROWS):
        for c in range(BOLT_COLS):
            px = min(xs) + (c + 0.5) * w / BOLT_COLS
            py = min(ys) + (r + 0.5) * h / BOLT_ROWS
            if _inside(px, py, BOLT_POLY):
                cells.append((c, r))
    return cells


SECTION = "\x00section"

W = 1020
PAD = 28
HEAD = 42          # terminal title bar
COL = 268          # where the info column starts
VAL = 488          # where values start
LINE = 25          # row pitch


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(data: dict, rows: list[tuple[str, str]], c: dict, now: datetime) -> str:
    # first key baseline sits at HEAD + 77, then one LINE per row
    extra = sum(10 for k, _ in rows if k == SECTION)
    body = max(77 + (len(rows) - 1) * LINE + extra + 18,
               BOLT_ROWS * (BOLT_CELL + BOLT_GAP) + 26)  # bolt floor
    H = HEAD + body + 98
    o: list[str] = []
    add = o.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="neofetch card for {USER}">')
    add("<defs>")
    add('<linearGradient id="bolt" x1="0" y1="0" x2="0.4" y2="1">'
        f'<stop offset="0" stop-color="{c["bolt_a"]}"/>'
        f'<stop offset="1" stop-color="{c["bolt_b"]}"/></linearGradient>')
    add(f'<clipPath id="barclip"><rect x="0" y="0" width="{W}" height="{H}" rx="5"/></clipPath>')
    add("</defs>")

    # card + terminal chrome
    add(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" '
        f'fill="{c["card"]}" stroke="{c["edge"]}"/>')
    add(f'<path d="M0 14a14 14 0 0 1 14-14h{W-28}a14 14 0 0 1 14 14v{HEAD-14}H0z" fill="{c["bar"]}"/>')
    add(f'<line x1="0" y1="{HEAD}" x2="{W}" y2="{HEAD}" stroke="{c["edge"]}"/>')
    for i, cx in enumerate((22, 42, 62)):
        add(f'<circle cx="{cx}" cy="{HEAD/2}" r="5" fill="{c["faint"]}" '
            f'opacity="{0.9 - i * 0.2:.1f}"/>')
    add(f'<text x="{W/2}" y="{HEAD/2 + 4}" text-anchor="middle" font-family="{MONO}" '
        f'font-size="12" fill="{c["dim"]}">zernic@github: ~</text>')

    # bolt, scaled to the art column and capped so it never outgrows the rows
    bx = PAD + 26
    avail_w = COL - bx - 26
    pitch = min(avail_w // BOLT_COLS, (body - 24) // BOLT_ROWS)
    cell = pitch - BOLT_GAP
    bx += (avail_w - BOLT_COLS * pitch) // 2
    by = HEAD + round((body - BOLT_ROWS * pitch) / 2) + 4
    for col, r in bolt_cells():
        add(f'<rect x="{bx + col * pitch}" y="{by + r * pitch}" '
            f'width="{cell}" height="{cell}" rx="1.5" fill="url(#bolt)"/>')

    # header line
    y = HEAD + 44
    add(f'<text x="{COL}" y="{y}" font-family="{MONO}" font-size="15" font-weight="600" '
        f'fill="{c["key"]}">joseph<tspan fill="{c["faint"]}">@</tspan><tspan fill="{c["val"]}">onblitz</tspan></text>')
    y += 10
    add(f'<line x1="{COL}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{c["edge"]}"/>')

    # key/value rows, with SECTION markers breaking them into blocks
    y += 23
    for key, val in rows:
        if key == SECTION:
            y += 8
            add(f'<text x="{COL}" y="{y}" font-family="{MONO}" font-size="12" '
                f'font-weight="700" letter-spacing="0.6" fill="{c["sect"]}">{esc(val)}</text>')
            add(f'<line x1="{COL}" y1="{y + 7}" x2="{W - PAD}" y2="{y + 7}" '
                f'stroke="{c["edge"]}"/>')
            y += LINE + 2
            continue
        add(f'<text x="{COL}" y="{y}" font-family="{MONO}" font-size="13" font-weight="600" '
            f'fill="{c["key"]}">{esc(key)}<tspan fill="{c["faint"]}">:</tspan></text>')
        add(f'<text x="{VAL}" y="{y}" font-family="{MONO}" font-size="13" '
            f'fill="{c["val"]}">{esc(val)}</text>')
        y += LINE

    # language bar, full width under both columns
    top = HEAD + body + 24
    add(f'<text x="{PAD}" y="{top}" font-family="{MONO}" font-size="11" '
        f'letter-spacing="1.2" fill="{c["faint"]}">LANGUAGES</text>')
    bar_y, bar_h, bar_w = top + 12, 10, W - PAD * 2
    add(f'<g clip-path="url(#barclip)"><rect x="{PAD}" y="{bar_y}" width="{bar_w}" '
        f'height="{bar_h}" rx="5" fill="{c["track"]}"/>')
    x = float(PAD)
    for lang in data["languages"]:
        seg = bar_w * lang["pct"] / 100
        if seg < 0.6:
            continue
        add(f'<rect x="{x:.2f}" y="{bar_y}" width="{seg:.2f}" height="{bar_h}" '
            f'fill="{lang["color"]}"/>')
        x += seg
    add("</g>")

    # legend, doubling as neofetch's colour blocks
    ly = bar_y + 34
    x = float(PAD)
    for lang in data["languages"][:6]:
        add(f'<rect x="{x}" y="{ly - 9}" width="10" height="10" rx="2.5" fill="{lang["color"]}"/>')
        label = f'{lang["name"]} {lang["pct"]:.0f}%'
        add(f'<text x="{x + 16}" y="{ly}" font-family="{MONO}" font-size="12" '
            f'fill="{c["dim"]}">{esc(label)}</text>')
        x += 16 + len(label) * 7.3 + 22

    stamp = now.strftime("%d %b %Y").lstrip("0")
    add(f'<text x="{W - PAD}" y="{ly}" text-anchor="end" font-family="{MONO}" '
        f'font-size="11" fill="{c["faint"]}">refreshed {stamp}</text>')
    add("</svg>")
    return "\n".join(o)


def main() -> None:
    now = datetime.now(timezone.utc)
    data = collect()
    snap = json.loads((ROOT / "scripts" / "langs-snapshot.json").read_text())
    prog = ", ".join(l["name"] for l in data["languages"]
                     if l["name"] in {"Python", "TypeScript", "JavaScript", "Go", "Rust"})

    rows = [
        ("OS", "Ubuntu 26.04, Windows 11, macOS"),
        ("Host", "Longview, Texas"),
        ("Uptime", f'{uptime(data["created"], now)} on GitHub'),
        ("Shell", "bash"),
        ("IDE", "Claude Code"),
        ("Project", "OnBlitz"),
        ("Languages.Programming", prog),
        ("Languages.Computer", "HTML, CSS, Jinja, SQL, YAML"),
        (SECTION, "Contact"),
        ("Email", "jmr62810@gmail.com"),
        ("Website", "onblitz.net"),
        (SECTION, "GitHub Stats"),
        ("Repos", str(data["repos"])),
        ("Commits", f'{snap["commits"]:,}'),
        ("Lines of code", f'{snap["lines"]:,}'),
    ]

    if "--print" in sys.argv:
        print(json.dumps({**data, "rows": rows}, indent=2))
        return

    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    (out / "neofetch-dark.svg").write_text(render(data, rows, DARK, now))
    (out / "neofetch-light.svg").write_text(render(data, rows, LIGHT, now))
    print(f'wrote 2 svgs - {data["repos"]} repos, {snap["commits"]} commits, '
          f'{snap["lines"]:,} lines, {human_bytes(data["bytes"])}')


if __name__ == "__main__":
    main()

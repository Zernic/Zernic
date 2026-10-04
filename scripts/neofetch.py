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

import calendar
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = "Zernic"
BORN = date(2010, 6, 28)

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
    """Public data from the API, the rest from the committed snapshot."""
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
        "commits": snapshot["commits"],
        "lines": snapshot["lines"],
        "languages": [
            {"name": n, "size": s, "pct": 100 * s / total,
             "color": colors.get(n, "#8b8b93")}
            for n, s in ranked
        ],
    }


def ymd(start: date, end: date) -> tuple[int, int, int]:
    """Calendar years, months and days between two dates."""
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    if days < 0:
        months -= 1
        prev = end.month - 1 or 12
        year = end.year if end.month > 1 else end.year - 1
        days += calendar.monthrange(year, prev)[1]
    if months < 0:
        years -= 1
        months += 12
    return years, months, days


def span(start: date, end: date, parts: int = 3) -> str:
    y, m, d = ymd(start, end)
    out = [f"{y} years"]
    if m:
        out.append(f"{m} months")
    if d:
        out.append(f"{d} days")
    return ", ".join(out[:parts])


# ---------------------------------------------------------------- drawing

DARK = {
    "page": "#0d1117",      # GitHub's dark canvas, so the card has no seam
    "key": "#ffa657",
    "val": "#a5d6ff",
    "sect": "#d2a8ff",
    "lead": "#30363d",      # the dotted leaders and the rules
    "dim": "#8b949e",
    "bolt_a": "#ffd166",
    "bolt_b": "#ff8c42",
    "track": "#21262d",
}

LIGHT = {
    "page": "#ffffff",
    "key": "#953800",
    "val": "#0550ae",
    "sect": "#8250df",
    "lead": "#d0d7de",
    "dim": "#656d76",
    "bolt_a": "#e3a008",
    "bolt_b": "#bc4c00",
    "track": "#eaeef2",
}

MONO = ("ui-monospace,'SF Mono',SFMono-Regular,'JetBrains Mono','Cascadia Mono',"
        "Menlo,Consolas,'Liberation Mono',monospace")

# The logo is a real lightning bolt polygon rasterised onto a grid, so it keeps
# the blocky terminal feel without turning into a staircase the way a hand-drawn
# low-resolution one does. Swap this for an ASCII portrait when there is a photo.
BOLT_POLY = [(62, 0), (14, 84), (44, 84), (32, 140), (90, 50), (58, 50), (80, 0)]
BOLT_COLS, BOLT_ROWS = 15, 23

SECTION = "\x00section"

W = 940
PAD = 26
COL = 252          # where the text column starts
FS = 13.5          # row font size
LINE = 24          # row pitch
COLS = 76          # characters per row - this is what aligns the right edge


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    return [(c, r)
            for r in range(BOLT_ROWS) for c in range(BOLT_COLS)
            if _inside(min(xs) + (c + 0.5) * w / BOLT_COLS,
                       min(ys) + (r + 0.5) * h / BOLT_ROWS, BOLT_POLY)]


def render(data: dict, rows: list[tuple[str, str]], c: dict, now: datetime) -> str:
    """Every line in the right column is exactly COLS monospace characters, so
    the values line up on one right edge whatever font the reader actually has.
    No pixel measuring, no textLength, nothing to drift."""
    top = PAD + 16
    n_sect = sum(1 for k, _ in rows if k == SECTION)
    text_h = 28 + (len(rows) - 1) * LINE + n_sect * 12
    bar_h = 34
    H = top + text_h + 28 + bar_h + PAD

    o: list[str] = []
    add = o.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="neofetch card for {USER}">')
    add('<defs><linearGradient id="bolt" x1="0" y1="0" x2="0.4" y2="1">'
        f'<stop offset="0" stop-color="{c["bolt_a"]}"/>'
        f'<stop offset="1" stop-color="{c["bolt_b"]}"/></linearGradient></defs>')
    add(f'<rect width="{W}" height="{H}" fill="{c["page"]}"/>')

    def line(y: float, runs: list[tuple[str, str]]) -> None:
        """One monospace line built from (text, colour) runs."""
        parts = "".join(f'<tspan fill="{col}">{esc(t)}</tspan>' for t, col in runs)
        add(f'<text x="{COL}" y="{y}" font-family="{MONO}" font-size="{FS}" '
            f'xml:space="preserve">{parts}</text>')

    # header: joseph@rodriguez ------------------------------------------------
    y = top + 12
    head = "joseph@rodriguez"
    line(y, [("joseph", c["key"]), ("@", c["dim"]), ("rodriguez", c["val"]),
             (" " + "-" * (COLS - len(head) - 1), c["lead"])])
    y += 28

    for key, val in rows:
        if key == SECTION:
            y += 12
            label = f"- {val} "
            line(y, [("- ", c["lead"]), (val, c["sect"]),
                     (" " + "-" * (COLS - len(label) - 1), c["lead"])])
            y += LINE
            continue
        dots = max(1, COLS - len(key) - 2 - 1 - len(val))
        line(y, [(key, c["key"]), (":", c["dim"]), (" " + "." * dots + " ", c["lead"]),
                 (val, c["val"])])
        y += LINE

    # bolt, sized to the art column and centred against the text block
    art_w = COL - PAD - 34
    pitch = min(art_w // BOLT_COLS, (text_h - 10) // BOLT_ROWS)
    bx = PAD + 17 + (art_w - BOLT_COLS * pitch) // 2
    by = top + (text_h - BOLT_ROWS * pitch) // 2
    for col, r in bolt_cells():
        add(f'<rect x="{bx + col * pitch}" y="{by + r * pitch}" '
            f'width="{pitch - 1}" height="{pitch - 1}" rx="1.5" fill="url(#bolt)"/>')

    # language bar: the neofetch colour blocks, carrying real percentages.
    # Monospace is 0.6em wide in every font in the MONO stack, so this lands on
    # the same right edge as the text above it. A font a hair off moves it a
    # pixel or two, which is why nothing depends on the number being exact.
    bar_y = top + text_h + 28
    bar_w = round(COLS * FS * 0.6)
    add(f'<clipPath id="bc"><rect x="{COL}" y="{bar_y}" width="{bar_w}" '
        f'height="9" rx="4.5"/></clipPath>')
    add(f'<g clip-path="url(#bc)"><rect x="{COL}" y="{bar_y}" width="{bar_w}" '
        f'height="9" fill="{c["track"]}"/>')
    x = float(COL)
    for lang in data["languages"]:
        seg = bar_w * lang["pct"] / 100
        if seg >= 0.6:
            add(f'<rect x="{x:.2f}" y="{bar_y}" width="{seg:.2f}" height="9" '
                f'fill="{lang["color"]}"/>')
        x += seg
    add("</g>")

    ly = bar_y + 30
    x = float(COL)
    for lang in data["languages"][:6]:
        add(f'<rect x="{x:.1f}" y="{ly - 8.5}" width="9" height="9" rx="2" '
            f'fill="{lang["color"]}"/>')
        label = f'{lang["name"]} {lang["pct"]:.0f}%'
        add(f'<text x="{x + 13:.1f}" y="{ly}" font-family="{MONO}" font-size="11.5" '
            f'fill="{c["dim"]}">{esc(label)}</text>')
        x += 13 + len(label) * (11.5 * 0.6) + 16

    add("</svg>")
    return "\n".join(o)


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.date()
    data = collect()
    joined = datetime.fromisoformat(data["created"].replace("Z", "+00:00")).date()
    prog = ", ".join(l["name"] for l in data["languages"]
                     if l["name"] in {"Python", "TypeScript", "JavaScript", "Go", "Rust"})

    rows = [
        ("OS", "Ubuntu 26.04, Windows 11, macOS"),
        ("Uptime", span(BORN, today)),
        ("Host", "Longview, Texas"),
        ("Kernel", "Founder, OnBlitz"),
        ("IDE", "Claude Code"),
        ("Shell", "bash"),
        ("Languages.Programming", prog),
        ("Languages.Computer", "HTML, CSS, Jinja, SQL, YAML"),
        (SECTION, "Contact"),
        ("Email", "jmr62810@gmail.com"),
        ("Website", "onblitz.net"),
        (SECTION, "GitHub Stats"),
        ("Repos", str(data["repos"])),
        ("Commits", f'{data["commits"]:,}'),
        ("Lines of code", f'{data["lines"]:,}'),
        ("On GitHub for", span(joined, today, parts=2)),
    ]

    if "--print" in sys.argv:
        print(json.dumps({**data, "rows": rows}, indent=2))
        return

    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    (out / "neofetch-dark.svg").write_text(render(data, rows, DARK, now))
    (out / "neofetch-light.svg").write_text(render(data, rows, LIGHT, now))
    print(f'wrote 2 svgs - age {span(BORN, today)}, {data["repos"]} repos, '
          f'{data["commits"]} commits, {data["lines"]:,} lines')


if __name__ == "__main__":
    main()

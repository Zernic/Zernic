#!/usr/bin/env python3
"""Render the fastfetch card on my profile README.

It is a terminal transcript, not a graphic: a prompt, the command, the output,
and a prompt waiting underneath. Everything in it is real text in a monospace
font, including the lightning bolt, which is ASCII art generated from a polygon
rather than a picture.

Numbers come from the GitHub API where a token can see them and from
scripts/langs-snapshot.json otherwise, so the private half of my work counts.

  python3 scripts/neofetch.py            # write both SVGs
  python3 scripts/neofetch.py --print    # dump the numbers and the ASCII art
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
            "User-Agent": f"{USER}-fastfetch",
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


# ---------------------------------------------------------------- ascii art

BOLT_POLY = [(62, 0), (14, 84), (44, 84), (32, 140), (90, 50), (58, 50), (80, 0)]
ART_COLS, ART_ROWS = 30, 30
RAMP = " .:-=+*#%@"      # light to dense, the usual ASCII luminance ramp


def _inside(px: float, py: float, poly: list[tuple[int, int]]) -> bool:
    hit = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def bolt_ascii() -> list[str]:
    """The bolt as real characters.

    Each character cell is supersampled against the polygon and the coverage
    picks a glyph off the ramp, so the diagonals shade instead of turning into
    the staircase a hand-drawn low-resolution bolt becomes.
    """
    xs = [p[0] for p in BOLT_POLY]
    ys = [p[1] for p in BOLT_POLY]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0, max(ys) - y0
    sub = 4
    out = []
    for r in range(ART_ROWS):
        line = []
        for c in range(ART_COLS):
            hits = 0
            for sy in range(sub):
                for sx in range(sub):
                    px = x0 + (c + (sx + 0.5) / sub) * w / ART_COLS
                    py = y0 + (r + (sy + 0.5) / sub) * h / ART_ROWS
                    hits += _inside(px, py, BOLT_POLY)
            cov = hits / (sub * sub)
            line.append(" " if cov == 0 else RAMP[min(len(RAMP) - 1,
                                                      int(cov * len(RAMP)))])
        out.append("".join(line).rstrip())
    return out


# ---------------------------------------------------------------- drawing

DARK = {
    "page": "#0d1117",      # GitHub's dark canvas, so the card has no seam
    "key": "#ffa657",
    "val": "#a5d6ff",
    "sect": "#d2a8ff",
    "lead": "#30363d",      # the dotted leaders and the rules
    "dim": "#8b949e",
    "fg": "#e6edf3",
    "prompt": "#3fb950",
    "path": "#58a6ff",
    "art_a": "#ffd166",
    "art_b": "#ff8c42",
}

LIGHT = {
    "page": "#ffffff",
    "key": "#953800",
    "val": "#0550ae",
    "sect": "#8250df",
    "lead": "#d0d7de",
    "dim": "#656d76",
    "fg": "#1f2328",
    "prompt": "#1a7f37",
    "path": "#0969da",
    "art_a": "#e3a008",
    "art_b": "#bc4c00",
}

MONO = ("ui-monospace,'SF Mono',SFMono-Regular,'JetBrains Mono','Cascadia Mono',"
        "Menlo,Consolas,'Liberation Mono',monospace")

SECTION = "\x00section"
HOST = "joseph@rodriguez"

PAD = 26
FS = 13.5          # info font size
LINE = 23          # info row pitch
COLS = 76          # characters per info row - this is what aligns the right edge
AFS = 13           # art font size
ALH = 13.6         # art line pitch
GAP = 26           # between the art column and the info column
CW = 0.6           # a monospace advance is 0.6em in every font in the stack

COL = round(PAD + ART_COLS * CW * AFS + GAP)
W = round(COL + COLS * CW * FS + PAD)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(data: dict, rows: list[tuple[str, str]], art: list[str], c: dict) -> str:
    """Every line in the info column is exactly COLS monospace characters, so
    the values land on one right edge whatever font the reader actually has.
    No pixel measuring, no textLength, nothing to drift."""
    o: list[str] = []
    add = o.append

    def text(x: float, y: float, runs: list[tuple[str, str]], size: float = FS) -> None:
        parts = "".join(f'<tspan fill="{col}">{esc(t)}</tspan>' for t, col in runs)
        add(f'<text x="{x}" y="{y:.1f}" font-family="{MONO}" font-size="{size}" '
            f'xml:space="preserve">{parts}</text>')

    def prompt(y: float, cmd: str) -> None:
        text(PAD, y, [(HOST, c["prompt"]), (":", c["dim"]), ("~", c["path"]),
                      ("$ ", c["dim"]), (cmd, c["fg"])])

    # Walk the rows the same way the drawing loop does rather than guessing a
    # height from a formula. The first version was 16px short and the colour
    # blocks printed on top of the last line.
    h = FS + 24
    for key, _ in rows:
        h += LINE + (11 if key == SECTION else 0)
    info_h = h - LINE + 8
    body_h = max(info_h, ART_ROWS * ALH)
    y_cmd = PAD + 14
    y_body = y_cmd + 30
    y_blocks = y_body + body_h + 16
    y_tail = y_blocks + 30
    H = round(y_tail + PAD)

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="fastfetch output for {USER}">')
    add('<defs><linearGradient id="art" gradientUnits="userSpaceOnUse" '
        f'x1="0" y1="{y_body}" x2="0" y2="{y_body + ART_ROWS * ALH}">'
        f'<stop offset="0" stop-color="{c["art_a"]}"/>'
        f'<stop offset="1" stop-color="{c["art_b"]}"/></linearGradient></defs>')
    add(f'<rect width="{W}" height="{H}" fill="{c["page"]}"/>')

    # the command
    prompt(y_cmd, "fastfetch")

    # the ascii bolt, vertically centred against the info block
    art_y = y_body + AFS
    for i, row in enumerate(art):
        if row:
            text(PAD, art_y + i * ALH, [(row, "url(#art)")], AFS)

    # the output
    y = y_body + FS
    text(COL, y, [("joseph", c["key"]), ("@", c["dim"]), ("rodriguez", c["val"]),
                  (" " + "-" * (COLS - len(HOST) - 1), c["lead"])])
    y += 24

    for key, val in rows:
        if key == SECTION:
            y += 11
            label = f"- {val} "
            text(COL, y, [("- ", c["lead"]), (val, c["sect"]),
                          (" " + "-" * (COLS - len(label) - 1), c["lead"])])
            y += LINE
            continue
        dots = max(1, COLS - len(key) - 2 - 1 - len(val))
        text(COL, y, [(key, c["key"]), (":", c["dim"]),
                      (" " + "." * dots + " ", c["lead"]), (val, c["val"])])
        y += LINE

    # the colour blocks fastfetch prints last, carrying my language colours
    text(COL, y_blocks, [("███", l["color"])
                         for l in data["languages"][:8]], FS)

    # and a prompt waiting underneath, because the command finished
    prompt(y_tail, "█")
    add("</svg>")
    return "\n".join(o)


def main() -> None:
    today = datetime.now(timezone.utc).date()
    data = collect()
    joined = datetime.fromisoformat(data["created"].replace("Z", "+00:00")).date()
    prog = ", ".join(l["name"] for l in data["languages"]
                     if l["name"] in {"Python", "TypeScript", "JavaScript", "Go", "Rust"})

    rows = [
        ("OS", "Ubuntu, Windows 11, macOS"),
        ("Uptime", span(BORN, today)),
        ("Host", "Longview, Texas"),
        ("Kernel", "Full-stack Developer"),
        ("IDE", "Claude Code, VS Code, Roblox Studio"),
        ("Shell", "bash"),
        ("Languages.Programming", prog),
        ("Languages.Computer", "HTML, CSS, Jinja, SQL, YAML"),
        ("Hobbies.Software", "Programming, Web Development, Cybersecurity"),
        ("Hobbies.Hardware", "Homelabbing, PC Building"),
        ("Hobbies.Creative", "Filmmaking, Photography, Music, Saxophone"),
        (SECTION, "Contact"),
        ("Email", "jmr62810@gmail.com"),
        (SECTION, "GitHub Stats"),
        ("Repos", str(data["repos"])),
        ("Commits", f'{data["commits"]:,}'),
        ("Lines of code", f'{data["lines"]:,}'),
        ("On GitHub for", span(joined, today, parts=2)),
    ]

    art = bolt_ascii()
    if "--print" in sys.argv:
        print("\n".join(art))
        print(json.dumps({**data, "rows": rows}, indent=2))
        return

    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    (out / "neofetch-dark.svg").write_text(render(data, rows, art, DARK))
    (out / "neofetch-light.svg").write_text(render(data, rows, art, LIGHT))
    print(f'wrote 2 svgs at {W}x? - age {span(BORN, today)}, {data["repos"]} repos, '
          f'{data["commits"]} commits, {data["lines"]:,} lines')


if __name__ == "__main__":
    main()

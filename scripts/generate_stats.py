#!/usr/bin/env python3
"""Generate the local SVG graphics displayed by the profile README."""

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

WIDTH = 620
OUT_DIR = Path(__file__).resolve().parent.parent
LOGIN = os.environ.get("GH_LOGIN", "dhruvsheth10")
TOKEN = os.environ.get("GITHUB_TOKEN")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def svg(width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<style>
  text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
  .ink {{ fill: #57606a; color: #57606a; }} .muted {{ fill: #8c959f; }} .line {{ stroke: #d0d7de; }}
  @media (prefers-color-scheme: dark) {{
    .ink {{ fill: #c9d1d9; color: #c9d1d9; }} .muted {{ fill: #8b949e; }} .line {{ stroke: #30363d; }}
  }}
</style>{body}</svg>"""


def write(name: str, content: str) -> None:
    (OUT_DIR / name).write_text(content, encoding="utf-8")


def heading(title: str) -> str:
    safe = html.escape(title)
    rule_start = len(title) * 10 + 22
    return svg(WIDTH, 28, f'<text x="0" y="19" class="ink" font-size="16" font-weight="700">{safe}</text><line x1="{rule_start}" y1="13" x2="{WIDTH}" y2="13" class="line" />')


def fade(delay: float, duration: float = 0.35) -> str:
    return f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="{duration:.2f}s" fill="freeze" />'


def wipe(identifier: str, x: float, y: float, width: float, height: float, delay: float, duration: float) -> tuple[str, str]:
    clip = (
        f'<clipPath id="{identifier}"><rect x="{x:.1f}" y="{y:.1f}" width="0" height="{height:.1f}">'
        f'<animate attributeName="width" from="0" to="{width:.1f}" begin="{delay:.2f}s" dur="{duration:.2f}s" fill="freeze" />'
        f'</rect></clipPath>'
    )
    cursor = (
        f'<rect y="{y:.1f}" width="2" height="{height:.1f}" class="ink" opacity="0">'
        f'<animate attributeName="x" from="{x:.1f}" to="{x + width:.1f}" begin="{delay:.2f}s" dur="{duration:.2f}s" fill="freeze" />'
        f'<set attributeName="opacity" to=".55" begin="{delay:.2f}s" />'
        f'<set attributeName="opacity" to="0" begin="{delay + duration:.2f}s" /></rect>'
    )
    return clip, cursor


def hello() -> str:
    glyphs = {
        "H": ("@   @", "@   @", "@   @", "@@@@@", "@   @", "@   @", "@   @"),
        "E": ("@@@@@", "@    ", "@    ", "@@@@ ", "@    ", "@    ", "@@@@@"),
        "L": ("@    ", "@    ", "@    ", "@    ", "@    ", "@    ", "@@@@@"),
        "O": (" @@@ ", "@   @", "@   @", "@   @", "@   @", "@   @", " @@@ "),
        "W": ("@   @", "@   @", "@   @", "@ @ @", "@ @ @", "@ @ @", " @ @ "),
        "R": ("@@@@ ", "@   @", "@   @", "@@@@ ", "@ @  ", "@  @ ", "@   @"),
        "D": ("@@@@ ", "@   @", "@   @", "@   @", "@   @", "@   @", "@@@@ "),
        " ": ("     ",) * 7,
    }
    ramp = "@#+:"
    lines = []
    for row in range(7):
        line = ""
        for column, letter in enumerate("HELLO WORLD"):
            pixels = glyphs[letter][row]
            line += "".join(ramp[(row + column + index) % len(ramp)] if pixel == "@" else " " for index, pixel in enumerate(pixels))
            line += " "
        lines.append(line.rstrip())

    body = []
    x, y, line_height = 80, 18, 12
    for index, line in enumerate(lines):
        delay = 0.24 + index * 0.24
        clip, cursor = wipe(f"hello-{index}", x, y + index * line_height, len(line) * 7.2, line_height, delay, 0.90)
        body.append(clip)
        body.append(f'<text x="{x}" y="{y + index * line_height + 9}" class="ink" font-size="12" xml:space="preserve" clip-path="url(#hello-{index})">{line}</text>')
        body.append(cursor)
    return svg(WIDTH, 116, "".join(body))


def fetch() -> dict:
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required")
    today = datetime.now(timezone.utc).date()
    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "login": LOGIN,
            "from": f"{today - timedelta(days=364)}T00:00:00Z",
            "to": f"{today}T23:59:59Z",
        },
    }).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-readme",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {data.get('errors', 'user not found')}")
    return data["data"]["user"]


def draw_stats(calendar: dict) -> str:
    weeks = calendar["weeks"]
    totals = [sum(day["contributionCount"] for day in week["contributionDays"]) for week in weeks]
    high = max(totals, default=1) or 1
    points = []
    for index, count in enumerate(totals):
        x = index * WIDTH / max(len(totals) - 1, 1)
        y = 128 - count / high * 38
        points.append(f"{x:.1f},{y:.1f}")
    active = sum(day["contributionCount"] > 0 for week in weeks for day in week["contributionDays"])
    chart_clip, chart_cursor = wipe("contributions-chart", 0, 84, WIDTH, 46, 0.84, 2.50)
    return svg(WIDTH, 148, f"""
<g opacity="0"><text x="0" y="52" class="ink" font-size="48" font-weight="700">{calendar["totalContributions"]}</text>
<text x="0" y="73" class="muted" font-size="12">contributions in the last year</text>{fade(0.20, 0.70)}</g>
<g opacity="0"><text x="{WIDTH}" y="32" class="ink" text-anchor="end" font-size="18" font-weight="700">{active}</text>
<text x="{WIDTH}" y="50" class="muted" text-anchor="end" font-size="11">active days</text>{fade(0.48, 0.70)}</g>
{chart_clip}<g clip-path="url(#contributions-chart)">
<polyline points="{' '.join(points)}" fill="none" class="ink" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
<line x1="0" y1="128" x2="{WIDTH}" y2="128" class="line" /></g>{chart_cursor}
""")


def draw_languages(repositories: list[dict]) -> str:
    sizes = Counter()
    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            sizes[edge["node"]["name"]] += edge["size"]
    ranked = sizes.most_common(5)
    maximum = ranked[0][1] if ranked else 1
    rows = []
    for index, (language, size) in enumerate(ranked):
        y = 34 + index * 25
        percentage = size / sum(sizes.values()) * 100 if sizes else 0
        delay = 0.50 + index * 0.20
        bar_width = 420 * size / maximum
        rows.append(f'<g opacity="0"><text x="0" y="{y}" class="ink" font-size="12">{html.escape(language.lower())}</text><text x="{WIDTH}" y="{y}" class="muted" text-anchor="end" font-size="11">{percentage:.0f}%</text>{fade(delay, 0.70)}</g>')
        rows.append(f'<rect x="112" y="{y - 10}" width="0" height="8" rx="4" class="ink" opacity=".8"><animate attributeName="width" from="0" to="{bar_width:.1f}" begin="{delay:.2f}s" dur="1.40s" fill="freeze" /></rect>')
    return svg(WIDTH, 168, '<g opacity="0"><text x="0" y="12" class="muted" font-size="10" letter-spacing="1.2">TOP LANGUAGES BY BYTES</text>' + fade(0.16, 0.70) + '</g>' + "".join(rows))


def draw_year(calendar: dict) -> str:
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    cells = []
    for index, day in enumerate(days):
        count = day["contributionCount"]
        opacity = 0.12 if count == 0 else min(0.25 + count * 0.12, 1)
        x, y = (index % 53) * 11 + 20, (index // 53) * 12 + 34
        delay = 0.56 + (index // 53) * 0.20 + (index % 53) * 0.024
        cells.append(f'<rect x="{x}" y="{y}" width="8" height="8" rx="2" class="ink" opacity="0"><title>{day["date"]}: {count} contributions</title><animate attributeName="opacity" from="0" to="{opacity:.2f}" begin="{delay:.2f}s" dur=".36s" fill="freeze" /></rect>')
    return svg(WIDTH, 132, f'<g opacity="0"><text x="20" y="16" class="muted" font-size="10" letter-spacing="1.2">THE YEAR · {calendar["totalContributions"]} CONTRIBUTIONS</text>{fade(0.16, 0.70)}</g>{"".join(cells)}')


def main() -> None:
    write("hello.svg", hello())
    for title in ("about", "stack", "projects", "stats"):
        write(f"heading-{title}.svg", heading(title))
    user = fetch()
    calendar = user["contributionsCollection"]["contributionCalendar"]
    write("stats.svg", draw_stats(calendar))
    write("langs.svg", draw_languages(user["repositories"]["nodes"]))
    write("year.svg", draw_year(calendar))


if __name__ == "__main__":
    main()

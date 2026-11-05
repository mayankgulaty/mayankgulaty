"""Generate the dynamic profile cards (dark + light):
  assets/generated/contrib-{dark,light}.svg     contribution calendar flowing into a Spark node
  assets/generated/languages-{dark,light}.svg   language donut across public repos
Data comes from the GitHub GraphQL API using the workflow's GITHUB_TOKEN.
"""
import json
import os
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "mayankgulaty")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = "assets/generated"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount contributionLevel } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

THEMES = {
    "dark": {
        "bg0": "#0a0e16", "bg1": "#121a2a", "title": "#e6edf3", "text": "#c9d4e5",
        "muted": "#7d8ba3", "faint": "#5b6b85", "edge": "#ffffff", "node": "#1b2433",
        "levels": ["#161e2c", "#5a2c18", "#9a4220", "#e0581f", "#ff8a4c"],
        "packet": "#FF9F45", "belt": "#ffffff",
    },
    "light": {
        "bg0": "#ffffff", "bg1": "#f3f6fb", "title": "#111827", "text": "#374151",
        "muted": "#6b7280", "faint": "#9ca3af", "edge": "#000000", "node": "#eef2f7",
        "levels": ["#ebedf0", "#ffd9c7", "#ffb08a", "#ff8a4c", "#e5531d"],
        "packet": "#e5531d", "belt": "#000000",
    },
}
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
FONT_SANS = "'Segoe UI', -apple-system, 'Helvetica Neue', Ubuntu, Arial, sans-serif"
FONT_MONO = "'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace"


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": f"{USER}-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def frame(w, h, t, inner):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg0']}"/><stop offset="1" stop-color="{t['bg1']}"/></linearGradient>
    <linearGradient id="brand" x1="0" x2="1"><stop offset="0" stop-color="#FF6B35"/><stop offset="1" stop-color="#29B5E8"/></linearGradient>
    <clipPath id="card"><rect width="{w}" height="{h}" rx="20"/></clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{w}" height="{h}" fill="url(#bg)"/>
{inner}
    <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="19" fill="none" stroke="{t['edge']}" stroke-opacity=".08"/>
  </g>
</svg>
"""


def contrib_svg(cal, t):
    weeks = cal["weeks"][-53:]
    total = cal["totalContributions"]
    cell, gap, x0, y0 = 11, 3, 32, 64
    step = cell + gap
    grid_bottom = y0 + 7 * step
    belt_y = grid_bottom + 44
    node_x = 32 + 53 * step + 70
    parts = [f"""    <style>
      .c {{ animation: glow 4s ease-in-out infinite; }}
      @keyframes glow {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .45; }} }}
      .hub {{ animation: hub 1.2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
      @keyframes hub {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.12); }} }}
    </style>
    <text x="32" y="38" font-family="{FONT_SANS}" font-size="16" font-weight="800" fill="{t['title']}">contributions.parquet</text>
    <text x="222" y="38" font-family="{FONT_MONO}" font-size="12" fill="{t['faint']}">→ spark.readStream</text>
    <text x="868" y="38" text-anchor="end" font-family="{FONT_MONO}" font-size="12" fill="{t['muted']}"><tspan fill="#FF6B35" font-weight="700">{total:,}</tspan> rows processed · last 12 months</text>"""]

    for ci, w in enumerate(weeks):
        x = x0 + ci * step
        for di, d in enumerate(w["contributionDays"]):
            lvl = LEVEL.get(d["contributionLevel"], 0)
            cls = ' class="c"' if lvl else ""
            delay = f' style="animation-delay:{ci * 0.07:.2f}s"' if lvl else ""
            parts.append(f'    <rect{cls}{delay} x="{x}" y="{y0 + di * step}" width="{cell}" height="{cell}" rx="2.5" fill="{t["levels"][lvl]}"/>')

    # conveyor belt + hub
    parts.append(f'    <line x1="{x0}" y1="{belt_y}" x2="{node_x - 26}" y2="{belt_y}" stroke="{t["belt"]}" stroke-opacity=".1" stroke-width="6" stroke-linecap="round"/>')
    parts.append(f'    <line x1="{x0}" y1="{belt_y}" x2="{node_x - 26}" y2="{belt_y}" stroke="url(#brand)" stroke-opacity=".6" stroke-width="1.5" stroke-dasharray="4 6"><animate attributeName="stroke-dashoffset" from="20" to="0" dur=".6s" repeatCount="indefinite"/></line>')

    # one packet per active week, dropping onto the belt and sliding into Spark
    for ci, w in enumerate(weeks):
        n = sum(d["contributionCount"] for d in w["contributionDays"])
        if not n:
            continue
        cx = x0 + ci * step + cell / 2
        dist = (node_x - 26) - cx + (belt_y - grid_bottom)
        dur = max(dist / 160, 0.8)
        r = 2.5 + min(n, 30) / 10
        parts.append(
            f'    <circle r="{r:.1f}" fill="{t["packet"]}" opacity=".9">'
            f'<animateMotion path="M{cx:.1f} {grid_bottom} L{cx:.1f} {belt_y} L{node_x - 26} {belt_y}" '
            f'dur="{dur:.2f}s" begin="{(ci % 13) * 0.45:.2f}s" repeatCount="indefinite"/></circle>')

    parts.append(f"""    <circle class="hub" cx="{node_x}" cy="{belt_y}" r="24" fill="{t['node']}" stroke="url(#brand)" stroke-width="2.5"/>
    <text x="{node_x}" y="{belt_y + 4}" text-anchor="middle" font-family="{FONT_MONO}" font-size="11" font-weight="700" fill="#FF6B35">spark</text>
    <text x="{node_x}" y="{y0 + 10}" text-anchor="middle" font-family="{FONT_MONO}" font-size="10" fill="{t['muted']}">less</text>""")
    for i, c in enumerate(t["levels"]):
        parts.append(f'    <rect x="{node_x - 6}" y="{y0 + 18 + i * 13}" width="11" height="11" rx="2.5" fill="{c}"/>')
    parts.append(f'    <text x="{node_x}" y="{y0 + 96}" text-anchor="middle" font-family="{FONT_MONO}" font-size="10" fill="{t["muted"]}">more</text>')
    return frame(900, belt_y + 40, t, "\n".join(parts))


def languages_svg(repos, t):
    totals = {}
    for repo in repos["nodes"]:
        for e in repo["languages"]["edges"]:
            name, color = e["node"]["name"], e["node"]["color"] or "#8b949e"
            size, _ = totals.get(name, (0, color))
            totals[name] = (size + e["size"], color)
    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)
    top, rest = ranked[:6], ranked[6:]
    if rest:
        top.append(("Other", (sum(v[0] for _, v in rest), "#8b949e")))
    grand = sum(v[0] for _, v in top) or 1

    cx, cy, r, sw = 130, 120, 62, 22
    circ = 2 * 3.14159265 * r
    parts = [f"""    <style>
      .seg {{ animation: grow 1.4s cubic-bezier(.2,.8,.2,1) forwards; }}
      @keyframes grow {{ from {{ stroke-dasharray: 0 {circ:.1f}; }} }}
      .lg {{ opacity: 0; animation: fade .5s ease-out forwards; }}
      @keyframes fade {{ from {{ opacity: 0; transform: translateX(-8px); }} to {{ opacity: 1; transform: none; }} }}
    </style>
    <text x="32" y="38" font-family="{FONT_SANS}" font-size="16" font-weight="800" fill="{t['title']}">SELECT language, SUM(bytes)</text>
    <text x="868" y="38" text-anchor="end" font-family="{FONT_MONO}" font-size="12" fill="{t['muted']}">FROM my_public_repos GROUP BY 1</text>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t['edge']}" stroke-opacity=".06" stroke-width="{sw}"/>"""]

    offset = 0.0
    for i, (name, (size, color)) in enumerate(top):
        length = circ * size / grand
        parts.append(
            f'    <circle class="seg" style="animation-delay:{i * 0.12:.2f}s" cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-dasharray="{max(length - 2, 0.1):.1f} {circ:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += length
    lead = escape(top[0][0]) if top else "n/a"
    parts.append(f'    <text x="{cx}" y="{cy - 2}" text-anchor="middle" font-family="{FONT_SANS}" font-size="15" font-weight="800" fill="{t["title"]}">{lead}</text>')
    parts.append(f'    <text x="{cx}" y="{cy + 15}" text-anchor="middle" font-family="{FONT_MONO}" font-size="10" fill="{t["muted"]}">top language</text>')

    # legend in two columns with bars
    for i, (name, (size, color)) in enumerate(top):
        col, row = divmod(i, 4)
        x, y = 260 + col * 320, 78 + row * 36
        pct = 100 * size / grand
        bar = 180 * size / top[0][1][0]
        parts.append(f"""    <g class="lg" style="animation-delay:{0.3 + i * 0.1:.2f}s">
      <circle cx="{x + 6}" cy="{y - 4}" r="5" fill="{color}"/>
      <text x="{x + 18}" y="{y}" font-family="{FONT_SANS}" font-size="13" font-weight="600" fill="{t['text']}">{escape(name)}</text>
      <text x="{x + 280}" y="{y}" text-anchor="end" font-family="{FONT_MONO}" font-size="12" fill="{t['muted']}">{pct:.1f}%</text>
      <rect x="{x + 18}" y="{y + 7}" width="180" height="4" rx="2" fill="{t['edge']}" fill-opacity=".06"/>
      <rect x="{x + 18}" y="{y + 7}" width="{bar:.1f}" height="4" rx="2" fill="{color}"/>
    </g>""")
    return frame(900, 230, t, "\n".join(parts))


def write(path, content):
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    user = fetch()
    os.makedirs(OUT, exist_ok=True)
    cal = user["contributionsCollection"]["contributionCalendar"]
    for mode, theme in THEMES.items():
        write(f"{OUT}/contrib-{mode}.svg", contrib_svg(cal, theme))
        write(f"{OUT}/languages-{mode}.svg", languages_svg(user["repositories"], theme))


if __name__ == "__main__":
    main()

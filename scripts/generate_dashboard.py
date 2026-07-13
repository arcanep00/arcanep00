"""
Generates dashboard.svg — a monitoring-style dashboard where each card
is a GitHub stat (commits, PRs, issues, repos, followers, stars) shown
as a circular gauge, like a Grafana/Datadog panel.
"""

import os
import sys
import math

import requests

GH_TOKEN = os.environ.get("GH_TOKEN")
GH_USERNAME = os.environ.get("GH_USERNAME")

if not GH_TOKEN or not GH_USERNAME:
    print("Missing GH_TOKEN or GH_USERNAME env vars")
    sys.exit(1)

QUERY = """
query($userName: String!) {
  user(login: $userName) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""


def fetch_stats():
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"userName": GH_USERNAME}},
        headers={"Authorization": f"bearer {GH_TOKEN}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        print(data["errors"])
        sys.exit(1)
    return data["data"]["user"]


def gauge(cx, cy, r, ratio, color):
    circumference = 2 * math.pi * r
    dash = max(2, ratio * circumference)
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#21262d" stroke-width="8"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="8" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference:.1f}" '
        f'transform="rotate(-90 {cx} {cy})" opacity="0.95"/>'
    )


def build_svg(username, metrics):
    card_w, card_h = 220, 140
    gap = 20
    cols = 3
    rows = math.ceil(len(metrics) / cols)
    header_h = 60
    width = cols * card_w + (cols + 1) * gap
    height = header_h + rows * card_h + (rows + 1) * gap + 30

    parts = []
    parts.append(
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="16" fill="#c9d1d9">{username}&#8217;s System Dashboard</text>'
    )
    active = sum(1 for _, v, *_ in metrics if v > 0)
    parts.append(
        f'<text x="{width/2}" y="46" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="10" fill="#3fb950">&#9679; {active}/{len(metrics)} SERVICES ACTIVE</text>'
    )

    for idx, (name, value, color, cap) in enumerate(metrics):
        col = idx % cols
        row = idx // cols
        x = gap + col * (card_w + gap)
        y = header_h + gap + row * (card_h + gap)

        parts.append(
            f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="8" '
            f'fill="#161b22" stroke="#30363d" stroke-width="1.2"/>'
        )

        status_color = "#3fb950" if value > 0 else "#565d66"
        parts.append(f'<circle cx="{x+card_w-16}" cy="{y+16}" r="4" fill="{status_color}"/>')

        gx, gy, gr = x + 58, y + card_h / 2, 38
        ratio = min(1.0, math.log1p(value) / math.log1p(cap)) if cap > 0 else 0
        parts.append(gauge(gx, gy, gr, ratio, color))
        parts.append(
            f'<text x="{gx}" y="{gy+5}" text-anchor="middle" font-family="Consolas, monospace" '
            f'font-size="14" font-weight="bold" fill="#c9d1d9">{value}</text>'
        )

        parts.append(
            f'<text x="{x+112}" y="{y+card_h/2-4}" font-family="Consolas, monospace" '
            f'font-size="12" fill="#8b949e">{name}</text>'
        )
        parts.append(
            f'<text x="{x+112}" y="{y+card_h/2+14}" font-family="Consolas, monospace" '
            f'font-size="10" fill="#565d66">status: {"online" if value>0 else "idle"}</text>'
        )

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">' \
          + "".join(parts) + "</svg>"
    return svg


def main():
    user = fetch_stats()
    cc = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]
    repo_count = user["repositories"]["totalCount"]
    followers = user["followers"]["totalCount"]
    stars = sum(r["stargazerCount"] for r in repos)

    metrics = [
        ("Commits", cc["totalCommitContributions"], "#58a6ff", 500),
        ("Pull Requests", cc["totalPullRequestContributions"], "#bc8cff", 50),
        ("Issues", cc["totalIssueContributions"], "#ffa657", 50),
        ("Repositories", repo_count, "#e3b341", 30),
        ("Followers", followers, "#ff7b72", 100),
        ("Stars", stars, "#39d2c0", 200),
    ]

    svg = build_svg(GH_USERNAME, metrics)

    with open("dashboard.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("dashboard.svg generated —", {m[0]: m[1] for m in metrics})


if __name__ == "__main__":
    main()

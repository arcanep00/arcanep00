"""
Generates bonsai.svg — a bonsai tree whose shape and leaf colors are
driven by real GitHub contribution data.

- Tree size/branch depth  -> total contributions this year
- Leaf colors             -> weekly contribution intensity (GitHub-style scale)
- Blossom (pink) leaves   -> exceptionally active weeks
- Label at the bottom     -> total contributions + longest current streak
"""

import os
import math
import random
import sys
from datetime import date, timedelta

import requests

GH_TOKEN = os.environ.get("GH_TOKEN")
GH_USERNAME = os.environ.get("GH_USERNAME")

if not GH_TOKEN or not GH_USERNAME:
    print("Missing GH_TOKEN or GH_USERNAME env vars")
    sys.exit(1)

QUERY = """
query($userName: String!) {
  user(login: $userName) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


def fetch_contributions():
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
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def longest_current_streak(days):
    streak = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            streak += 1
        else:
            break
    return streak


def weekly_totals(weeks):
    totals = []
    for w in weeks:
        totals.append(sum(d["contributionCount"] for d in w["contributionDays"]))
    return totals


def color_for(value, max_value):
    if max_value == 0:
        return "#2d3339"
    ratio = value / max_value
    if value == 0:
        return "#2d3339"
    elif ratio < 0.25:
        return "#9be9a8"
    elif ratio < 0.5:
        return "#40c463"
    elif ratio < 0.75:
        return "#30a14e"
    elif ratio < 0.95:
        return "#216e39"
    else:
        return "#ff6fae"  # blossom for standout weeks


class Bonsai:
    def __init__(self, leaf_colors, depth):
        self.leaf_colors = leaf_colors
        self.leaf_idx = 0
        self.depth = depth
        self.elements = []

    def next_color(self):
        if not self.leaf_colors:
            return "#40c463"
        c = self.leaf_colors[self.leaf_idx % len(self.leaf_colors)]
        self.leaf_idx += 1
        return c

    def branch(self, x, y, angle, length, depth, width):
        x2 = x + length * math.cos(angle)
        y2 = y - length * math.sin(angle)

        self.elements.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#8a5a3c" stroke-width="{max(width,1.2):.1f}" stroke-linecap="round"/>'
        )

        if depth == 0:
            color = self.next_color()
            r = random.uniform(4.5, 7)
            self.elements.append(
                f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="{r:.1f}" fill="{color}" opacity="0.92"/>'
            )
            return

        spread = math.radians(random.uniform(22, 34))
        branches = 2 if depth < self.depth - 1 else 3

        offsets = [-spread, spread] if branches == 2 else [-spread, 0, spread]
        for off in offsets:
            self.branch(
                x2, y2,
                angle + off + random.uniform(-0.05, 0.05),
                length * random.uniform(0.68, 0.78),
                depth - 1,
                width * 0.68,
            )


def build_svg(total, streak, weekly, username):
    random.seed(username)  # stable tree shape per user, leaves still update

    max_w = max(weekly) if weekly else 0
    leaf_colors = [color_for(v, max_w) for v in weekly]

    if total < 150:
        depth = 4
    elif total < 400:
        depth = 5
    elif total < 800:
        depth = 6
    else:
        depth = 7

    width, height = 800, 560
    base_x, base_y = width / 2, height - 90

    tree = Bonsai(leaf_colors, depth)
    trunk_width = min(10 + total / 120, 22)
    tree.branch(base_x, base_y, math.pi / 2, 70, depth, trunk_width)

    ground = f'<ellipse cx="{base_x}" cy="{base_y+6}" rx="160" ry="14" fill="#1c2128"/>'
    pot = (
        f'<path d="M {base_x-70} {base_y} L {base_x+70} {base_y} '
        f'L {base_x+55} {base_y+55} L {base_x-55} {base_y+55} Z" '
        f'fill="#b5651d" stroke="#7a4118" stroke-width="3"/>'
        f'<rect x="{base_x-80}" y="{base_y-10}" width="160" height="14" rx="4" fill="#c9762a" stroke="#7a4118" stroke-width="2"/>'
    )

    label = (
        f'<text x="{width/2}" y="{height-20}" text-anchor="middle" '
        f'font-family="Segoe UI, sans-serif" font-size="16" fill="#c9d1d9">'
        f'{total} contributions this year &#8226; {streak} day streak</text>'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
<rect width="{width}" height="{height}" fill="none"/>
{ground}
{"".join(tree.elements)}
{pot}
{label}
</svg>'''
    return svg


def main():
    calendar = fetch_contributions()
    total = calendar["totalContributions"]
    all_days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    streak = longest_current_streak(all_days)
    weekly = weekly_totals(calendar["weeks"])

    svg = build_svg(total, streak, weekly, GH_USERNAME)

    with open("bonsai.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"bonsai.svg generated — {total} contributions, {streak} day streak")


if __name__ == "__main__":
    main()

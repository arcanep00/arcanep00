"""
Generates river.svg — a flowing river whose width and glow are driven by
real GitHub contribution data.

- River width at any point x -> smoothed (7-day avg) contribution count that day
- Glowing bubbles                -> standout high-activity days
- Center-line sway                -> gentle organic wave, seeded per user (stable shape)
- Month ticks + totals label      -> readability
"""

import os
import sys
import math
import random

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


def moving_average(values, window=7):
    out = []
    n = len(values)
    for i in range(n):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def percentile(values, pct):
    if not values:
        return 0
    s = sorted(values)
    idx = min(int(len(s) * pct), len(s) - 1)
    return s[idx]


def curve_commands(points):
    cmds = ""
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        cmds += f"C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {p2[0]:.1f} {p2[1]:.1f} "
    return cmds


def build_svg(total, streak, all_days, username):
    random.seed(username)

    width, height = 900, 320
    margin_x = 30
    plot_w = width - 2 * margin_x
    center_y = height / 2 - 10

    counts = [d["contributionCount"] for d in all_days]
    smoothed = moving_average(counts, window=7)

    # sample every 2 days to keep the path light
    idxs = list(range(0, len(all_days), 2))
    if idxs[-1] != len(all_days) - 1:
        idxs.append(len(all_days) - 1)

    max_ref = percentile(smoothed, 0.93) or 1
    min_w, max_w = 6, 78

    phase = random.uniform(0, math.pi * 2)
    amplitude = 16
    freq = 2.4 * math.pi / plot_w

    top_points, bottom_points = [], []
    bubble_threshold = percentile(smoothed, 0.9)
    bubbles = []

    for i in idxs:
        x = margin_x + (i / (len(all_days) - 1)) * plot_w
        clipped = min(smoothed[i], max_ref)
        w = min_w + (clipped / max_ref) * (max_w - min_w)
        cy = center_y + amplitude * math.sin(freq * (x - margin_x) + phase)
        top_points.append((x, cy - w / 2))
        bottom_points.append((x, cy + w / 2))
        if smoothed[i] >= bubble_threshold and smoothed[i] > 0:
            bubbles.append((x, cy, w))

    path = f"M {top_points[0][0]:.1f} {top_points[0][1]:.1f} "
    path += curve_commands(top_points)
    path += f"L {bottom_points[-1][0]:.1f} {bottom_points[-1][1]:.1f} "
    path += curve_commands(list(reversed(bottom_points)))
    path += "Z"

    # inner current lines (texture)
    current_lines = []
    for offset, opacity in [(-0.25, 0.35), (0.0, 0.5), (0.25, 0.35)]:
        pts = []
        for i in idxs:
            x = margin_x + (i / (len(all_days) - 1)) * plot_w
            clipped = min(smoothed[i], max_ref)
            w = min_w + (clipped / max_ref) * (max_w - min_w)
            cy = center_y + amplitude * math.sin(freq * (x - margin_x) + phase)
            pts.append((x, cy + offset * w))
        d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} " + curve_commands(pts)
        current_lines.append(
            f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="1.2" opacity="{opacity}"/>'
        )

    # bubbles (glowing highlight days), thin out so they don't crowd
    bubble_svgs = []
    last_x = -999
    for bx, by, bw in bubbles:
        if bx - last_x < 22:
            continue
        last_x = bx
        r = min(6, bw / 4)
        bubble_svgs.append(
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r+4:.1f}" fill="#7ef9ff" opacity="0.18"/>'
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="#e8feff" opacity="0.9"/>'
        )

    # month ticks
    ticks = []
    last_month = None
    for i in idxs:
        m = all_days[i]["date"][:7]
        if m != last_month:
            last_month = m
            x = margin_x + (i / (len(all_days) - 1)) * plot_w
            month_label = all_days[i]["date"][5:7]
            month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            label = month_names[int(month_label)]
            ticks.append(
                f'<text x="{x:.1f}" y="{height-14}" text-anchor="middle" '
                f'font-family="Segoe UI, sans-serif" font-size="11" fill="#7d8590">{label}</text>'
            )

    title = (
        f'<text x="{width/2}" y="30" text-anchor="middle" '
        f'font-family="Segoe UI, sans-serif" font-size="17" fill="#c9d1d9">'
        f"{username}&#8217;s Contribution River</text>"
    )
    label = (
        f'<text x="{width/2}" y="{height-38}" text-anchor="middle" '
        f'font-family="Segoe UI, sans-serif" font-size="13" fill="#8b949e">'
        f"{total} contributions this year &#8226; {streak} day streak</text>"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="riverGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0b3d63"/>
      <stop offset="45%" stop-color="#0e7490"/>
      <stop offset="75%" stop-color="#22c1dc"/>
      <stop offset="100%" stop-color="#7ef9ff"/>
    </linearGradient>
  </defs>
  {title}
  <path d="{path}" fill="url(#riverGrad)" opacity="0.95"/>
  {"".join(current_lines)}
  {"".join(bubble_svgs)}
  {"".join(ticks)}
  {label}
</svg>'''
    return svg


def main():
    calendar = fetch_contributions()
    total = calendar["totalContributions"]
    all_days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    streak = longest_current_streak(all_days)

    svg = build_svg(total, streak, all_days, GH_USERNAME)

    with open("river.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"river.svg generated — {total} contributions, {streak} day streak")


if __name__ == "__main__":
    main()

"""
Generates pipeline.svg — a straight data pipeline with joints/stages,
where packets flowing through it represent days of GitHub activity.
Bigger/brighter packets = more contributions that day.
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

STAGES = ["INGEST", "VALIDATE", "PROCESS", "QUEUE", "COMMIT", "DEPLOY"]


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


def moving_average(values, window=3):
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


def packet_color(ratio):
    if ratio < 0.25:
        return "#1f4e8c"
    elif ratio < 0.5:
        return "#1f6feb"
    elif ratio < 0.75:
        return "#39c5f2"
    else:
        return "#7ef9ff"


def build_svg(username, total, streak, all_days):
    width, height = 900, 260
    margin_x = 40
    pipe_y = 120
    pipe_h = 40
    plot_w = width - 2 * margin_x

    counts = [d["contributionCount"] for d in all_days]
    smoothed = moving_average(counts, window=3)
    max_ref = percentile(smoothed, 0.93) or 1

    parts = []
    parts.append(
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="16" fill="#c9d1d9">{username}&#8217;s Data Pipeline</text>'
    )

    # pipe body
    parts.append(
        f'<rect x="{margin_x}" y="{pipe_y - pipe_h/2}" width="{plot_w}" height="{pipe_h}" rx="{pipe_h/2}" '
        f'fill="#132433" stroke="#1f6feb" stroke-width="1.5" opacity="0.9"/>'
    )
    parts.append(
        f'<rect x="{margin_x}" y="{pipe_y - pipe_h/2 + 4}" width="{plot_w}" height="4" rx="2" '
        f'fill="#39c5f2" opacity="0.35"/>'
    )

    # joints + stage labels
    n_joints = 6
    for j in range(n_joints):
        x = margin_x + (plot_w / (n_joints - 1)) * j
        parts.append(
            f'<rect x="{x-6:.1f}" y="{pipe_y - pipe_h/2 - 6}" width="12" height="{pipe_h+12}" rx="3" '
            f'fill="#1c2733" stroke="#30363d" stroke-width="1.5"/>'
        )
        parts.append(f'<circle cx="{x:.1f}" cy="{pipe_y - pipe_h/2 - 10}" r="1.8" fill="#565d66"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{pipe_y + pipe_h/2 + 10}" r="1.8" fill="#565d66"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{pipe_y + pipe_h/2 + 34}" text-anchor="middle" '
            f'font-family="Consolas, monospace" font-size="10" fill="#6e7681">{STAGES[j % len(STAGES)]}</text>'
        )

    # direction chevrons (static, faint)
    for x in range(int(margin_x + 20), int(margin_x + plot_w - 10), 46):
        parts.append(
            f'<path d="M {x} {pipe_y-5} L {x+8} {pipe_y} L {x} {pipe_y+5}" '
            f'fill="none" stroke="#7ef9ff" stroke-width="1.4" opacity="0.25"/>'
        )

    # packets
    idxs = list(range(0, len(all_days), 3))
    last_x = -999
    for i in idxs:
        val = smoothed[i]
        if val <= 0:
            continue
        x = margin_x + (i / (len(all_days) - 1)) * plot_w
        if x - last_x < 16:
            continue
        last_x = x
        ratio = min(1.0, val / max_ref)
        size = 5 + ratio * 11
        color = packet_color(ratio)
        glow = ratio > 0.8
        if glow:
            parts.append(f'<circle cx="{x:.1f}" cy="{pipe_y}" r="{size+6:.1f}" fill="{color}" opacity="0.18"/>')
        parts.append(
            f'<rect x="{x-size/2:.1f}" y="{pipe_y-size/2:.1f}" width="{size:.1f}" height="{size:.1f}" '
            f'rx="{size*0.3:.1f}" fill="{color}" transform="rotate(45 {x:.1f} {pipe_y})" opacity="0.95"/>'
        )

    parts.append(
        f'<text x="{width/2}" y="{height-16}" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="12" fill="#8b949e">PACKETS PROCESSED: {total} &#8226; ACTIVE UPTIME: {streak}d</text>'
    )

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">' \
          + "".join(parts) + "</svg>"
    return svg


def main():
    calendar = fetch_contributions()
    total = calendar["totalContributions"]
    all_days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    streak = longest_current_streak(all_days)

    svg = build_svg(GH_USERNAME, total, streak, all_days)

    with open("pipeline.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"pipeline.svg generated — {total} contributions, {streak} day streak")


if __name__ == "__main__":
    main()

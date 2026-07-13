"""
Generates rack.svg — a server rack where each rack unit (U) represents
one week of GitHub contributions. Brighter/longer activity bars and LEDs
= busier weeks. Most recent week sits at the top of the rack.
"""

import os
import sys

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


def led_color(ratio):
    if ratio <= 0:
        return "#2a2f38"
    elif ratio < 0.3:
        return "#1f6feb"
    elif ratio < 0.6:
        return "#3fb950"
    elif ratio < 0.85:
        return "#56d364"
    else:
        return "#39d2c0"


def build_svg(username, total, streak, uptime_pct, weekly_totals):
    unit_w = 340
    unit_h = 11
    header_h = 56
    footer_h = 70
    margin = 14

    weeks = list(reversed(weekly_totals))  # newest week on top
    n = len(weeks)
    max_val = max(weeks) if weeks else 1
    max_val = max(max_val, 1)

    height = header_h + n * unit_h + footer_h
    width = unit_w + margin * 2

    parts = []
    parts.append(
        f'<text x="{width/2}" y="26" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="15" fill="#c9d1d9">{username}&#8217;s Server Rack</text>'
    )
    parts.append(
        f'<text x="{width/2}" y="42" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="10" fill="#6e7681">// contribution infrastructure</text>'
    )

    # rack frame
    frame_y = header_h - 6
    frame_h = n * unit_h + 10
    parts.append(
        f'<rect x="{margin-6}" y="{frame_y}" width="{unit_w+12}" height="{frame_h}" rx="6" '
        f'fill="#12151a" stroke="#3a3f47" stroke-width="2"/>'
    )
    # mounting holes
    for i in range(0, frame_h, 26):
        y = frame_y + 8 + i
        parts.append(f'<circle cx="{margin-1}" cy="{y}" r="1.6" fill="#050608" stroke="#444a52" stroke-width="0.6"/>')
        parts.append(f'<circle cx="{margin+unit_w+1}" cy="{y}" r="1.6" fill="#050608" stroke="#444a52" stroke-width="0.6"/>')

    max_bar = unit_w - 90

    for i, val in enumerate(weeks):
        y = header_h + i * unit_h
        ratio = val / max_val if max_val else 0
        color = led_color(ratio)

        parts.append(f'<rect x="{margin}" y="{y}" width="{unit_w}" height="{unit_h-1.5}" rx="2" fill="#1a1e24"/>')
        parts.append(f'<rect x="{margin}" y="{y}" width="{unit_w}" height="1" fill="#2a2f38" opacity="0.6"/>')

        label_num = n - i
        parts.append(
            f'<text x="{margin+8}" y="{y+8}" font-family="Consolas, monospace" font-size="7.5" '
            f'fill="#565d66">U{label_num:02d}</text>'
        )

        bar_w = max(2, ratio * max_bar)
        parts.append(
            f'<rect x="{margin+46}" y="{y+2}" width="{bar_w:.1f}" height="{unit_h-5.5}" rx="1.5" fill="{color}" opacity="0.9"/>'
        )

        led_x = margin + unit_w - 14
        parts.append(f'<circle cx="{led_x}" cy="{y+4.5}" r="2.4" fill="{color}"/>')

    footer_y = header_h + n * unit_h + 26
    parts.append(
        f'<text x="{width/2}" y="{footer_y}" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="11" fill="#8b949e">THROUGHPUT: {total} commits/yr &#8226; UPTIME STREAK: {streak}d</text>'
    )
    parts.append(
        f'<text x="{width/2}" y="{footer_y+18}" text-anchor="middle" font-family="Consolas, monospace" '
        f'font-size="11" fill="#3fb950">SYSTEM UPTIME: {uptime_pct}%</text>'
    )

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">' \
          + "".join(parts) + "</svg>"
    return svg


def main():
    calendar = fetch_contributions()
    total = calendar["totalContributions"]
    weeks_data = calendar["weeks"]
    all_days = [d for w in weeks_data for d in w["contributionDays"]]
    streak = longest_current_streak(all_days)

    weekly_totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks_data]
    active_days = sum(1 for d in all_days if d["contributionCount"] > 0)
    uptime_pct = round(100 * active_days / len(all_days), 1) if all_days else 0

    svg = build_svg(GH_USERNAME, total, streak, uptime_pct, weekly_totals)

    with open("rack.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"rack.svg generated — {total} contributions, {streak} day streak, {uptime_pct}% uptime")


if __name__ == "__main__":
    main()

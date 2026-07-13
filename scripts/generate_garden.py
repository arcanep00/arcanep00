"""
Generates garden.svg — a small garden where each flower represents a
GitHub stat (commits, PRs, issues, repos, followers, stars), and a
grass strip at the bottom shows your language mix.

- Flower bloom size -> that metric's value (log-scaled, so it stays
  readable whether you have 5 or 5000 of something)
- Grass patch widths -> proportion of each language across your repos
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
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        primaryLanguage { name color }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""

LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "HTML": "#e34c26", "CSS": "#563d7c", "Go": "#00ADD8", "Rust": "#dea584",
    "PHP": "#4F5D95", "Ruby": "#701516", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "Swift": "#F05138", "Kotlin": "#A97BFF",
}


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


def bloom_radius(value, cap, min_r=7, max_r=26):
    ratio = min(1.0, math.log1p(value) / math.log1p(cap)) if cap > 0 else 0
    return min_r + ratio * (max_r - min_r)


def flower(cx, base_y, height, radius, color, seed_offset, stem_only=False):
    sway = 10 * math.sin(seed_offset)
    top_x = cx + sway
    top_y = base_y - height

    elems = [
        f'<path d="M {cx:.1f} {base_y:.1f} Q {cx + sway/2:.1f} {base_y - height/2:.1f} '
        f'{top_x:.1f} {top_y:.1f}" fill="none" stroke="#3a7d44" stroke-width="3.5" stroke-linecap="round"/>'
    ]
    # a couple of small leaves on the stem
    leaf_y = base_y - height * 0.4
    elems.append(
        f'<ellipse cx="{cx + sway*0.3 - 10:.1f}" cy="{leaf_y:.1f}" rx="9" ry="4.5" '
        f'fill="#4f9d5a" transform="rotate(-25 {cx + sway*0.3 - 10:.1f} {leaf_y:.1f})"/>'
    )
    elems.append(
        f'<ellipse cx="{cx + sway*0.3 + 10:.1f}" cy="{leaf_y - 8:.1f}" rx="9" ry="4.5" '
        f'fill="#4f9d5a" transform="rotate(25 {cx + sway*0.3 + 10:.1f} {leaf_y - 8:.1f})"/>'
    )

    if stem_only:
        return "".join(elems)

    # petals arranged radially + center
    petal_count = 6
    for i in range(petal_count):
        ang = (2 * math.pi / petal_count) * i
        px = top_x + math.cos(ang) * radius * 0.85
        py = top_y + math.sin(ang) * radius * 0.85
        elems.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius*0.62:.1f}" fill="{color}" opacity="0.92"/>'
        )
    elems.append(f'<circle cx="{top_x:.1f}" cy="{top_y:.1f}" r="{radius*0.5:.1f}" fill="#fff6b7"/>')

    return "".join(elems)


def build_svg(username, metrics, languages):
    random.seed(username)

    n = len(metrics)
    width = max(760, n * 150 + 60)
    height = 420
    base_y = height - 90
    spacing = (width - 120) / (n - 1) if n > 1 else 0

    parts = []
    parts.append(
        f'<text x="{width/2}" y="34" text-anchor="middle" font-family="Segoe UI, sans-serif" '
        f'font-size="18" fill="#c9d1d9">{username}&#8217;s Stat Garden</text>'
    )

    # ground
    parts.append(f'<rect x="0" y="{base_y}" width="{width}" height="6" fill="#5b3a24" opacity="0.5"/>')

    for i, (name, value, color, cap) in enumerate(metrics):
        cx = 60 + spacing * i
        r = bloom_radius(value, cap)
        stem_height = 90 + r * 2.4
        seed = random.uniform(0, math.pi * 2)
        parts.append(flower(cx, base_y, stem_height, r, color, seed))
        parts.append(
            f'<text x="{cx:.1f}" y="{base_y+26}" text-anchor="middle" '
            f'font-family="Segoe UI, sans-serif" font-size="12" fill="#8b949e">{name}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{base_y+42}" text-anchor="middle" '
            f'font-family="Segoe UI, sans-serif" font-size="13" font-weight="bold" fill="#c9d1d9">{value}</text>'
        )

    # language grass strip
    strip_y = height - 22
    strip_x = 40
    strip_w = width - 80
    if languages:
        total = sum(v for _, v in languages)
        x = strip_x
        for lang, count in languages:
            seg_w = (count / total) * strip_w if total else 0
            color = LANGUAGE_COLORS.get(lang, "#6e7681")
            parts.append(f'<rect x="{x:.1f}" y="{strip_y}" width="{seg_w:.1f}" height="10" rx="3" fill="{color}"/>')
            x += seg_w
        legend_items = []
        for lang, count in languages[:5]:
            pct = round(100 * count / total) if total else 0
            legend_items.append(f"{lang} {pct}%")
        parts.append(
            f'<text x="{width/2}" y="{strip_y+26}" text-anchor="middle" '
            f'font-family="Segoe UI, sans-serif" font-size="11" fill="#8b949e">'
            f'{"   &#8226;   ".join(legend_items)}</text>'
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

    lang_counts = {}
    for r in repos:
        lang = r["primaryLanguage"]["name"] if r["primaryLanguage"] else None
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    languages = sorted(lang_counts.items(), key=lambda x: -x[1])

    metrics = [
        ("Commits", cc["totalCommitContributions"], "#ff6b81", 500),
        ("Pull Requests", cc["totalPullRequestContributions"], "#a78bfa", 50),
        ("Issues", cc["totalIssueContributions"], "#ffb454", 50),
        ("Repositories", repo_count, "#facc15", 30),
        ("Followers", followers, "#ff8fd6", 100),
        ("Stars", stars, "#7ef9ff", 200),
    ]

    svg = build_svg(GH_USERNAME, metrics, languages)

    with open("garden.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("garden.svg generated —", {m[0]: m[1] for m in metrics})


if __name__ == "__main__":
    main()

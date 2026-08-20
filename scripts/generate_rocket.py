"""
Generates an animated SVG of a rocket flying over the GitHub contribution
graph, flashing each contributed day as it passes. Meant to be run on a
schedule (see .github/workflows/rocket.yml) and committed back to the repo,
the same way the snake / 3D-contrib generators work.

Requires a token with access to the GraphQL `contributionsCollection` field
for the target user (a classic PAT with `read:user`, stored as a repo
secret, is the safest bet -- the default GITHUB_TOKEN's access to this
field is inconsistent across accounts).
"""

import json
import os
import urllib.request


def gh_graphql(token: str, username: str):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
                color
                weekday
              }
            }
          }
        }
      }
    }
    """
    body = json.dumps({"query": query, "variables": {"login": username}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "rocket-contrib-svg",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def build_svg(weeks, out_path: str):
    cell, gap = 11, 3
    step = cell + gap
    margin = 20
    n_weeks = len(weeks)
    width = margin * 2 + n_weeks * step
    height = margin * 2 + 7 * step

    cell_defs = []
    flight_points = []

    # Zigzag down each week's column, alternating direction column to
    # column -- a rocket diving through each week, then jumping to the top
    # of the next one.
    for wi, week in enumerate(weeks):
        days = week["contributionDays"]
        ordered = days if wi % 2 == 0 else list(reversed(days))
        for day in ordered:
            x = margin + wi * step
            y = margin + day["weekday"] * step
            lit = day["contributionCount"] > 0
            cell_defs.append({"x": x, "y": y, "color": day["color"], "lit": lit})
            if lit:
                flight_points.append((x + cell / 2, y + cell / 2))

    if not flight_points:
        flight_points = [(margin + cell / 2, margin + cell / 2)]

    per_cell_time = 0.12
    total_dur = max(len(flight_points) * per_cell_time, 4)

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']

    lit_index = 0
    for c in cell_defs:
        base = c["color"] if c["lit"] else "#161b22"
        if c["lit"]:
            arrive = lit_index * per_cell_time
            lit_index += 1
            parts.append(
                f'<rect x="{c["x"]}" y="{c["y"]}" width="{cell}" height="{cell}" rx="2" fill="{base}">'
                f'<animate attributeName="fill" values="{base};#00d4ff;{base}" '
                f'keyTimes="0;0.5;1" dur="{total_dur}s" begin="{arrive}s" repeatCount="indefinite"/>'
                f"</rect>"
            )
        else:
            parts.append(f'<rect x="{c["x"]}" y="{c["y"]}" width="{cell}" height="{cell}" rx="2" fill="{base}"/>')

    path_d = "M " + " L ".join(f"{x},{y}" for x, y in flight_points)
    parts.append(f'<path id="flightpath" d="{path_d}" fill="none" stroke="none"/>')
    parts.append(
        '<polygon points="0,-6 4,4 0,2 -4,4" fill="#00d4ff">'
        f'<animateMotion dur="{total_dur}s" repeatCount="indefinite" rotate="auto">'
        '<mpath href="#flightpath"/>'
        "</animateMotion>"
        "</polygon>"
    )
    parts.append("</svg>")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(parts))


def main():
    token = os.environ["GITHUB_TOKEN"]
    username = os.environ["USERNAME"]
    out_path = os.environ.get("OUT_PATH", "rocket-contrib/rocket.svg")
    weeks = gh_graphql(token, username)
    build_svg(weeks, out_path)


if __name__ == "__main__":
    main()

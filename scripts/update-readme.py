#!/usr/bin/env python3
"""Update the live status section in the profile README."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

USERNAME = os.environ.get("GITHUB_USERNAME", "mehdi-tahmasebi")
README_PATH = os.environ.get("README_PATH", "README.md")
START_MARKER = "<!-- LIVING-README:START -->"
END_MARKER = "<!-- LIVING-README:END -->"


def fetch_json(url: str, token: str | None = None) -> dict | list:
    headers = {
        "User-Agent": "profile-readme-updater",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def italy_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Rome"))


def format_italy_time(moment: datetime) -> str:
    return moment.strftime("%A, %d %B %Y · %H:%M") + " CET"


def current_streak(contributions: list[dict]) -> int:
    counts = {entry["date"]: entry["count"] for entry in contributions}
    streak = 0
    day = date.today()

    while counts.get(day.isoformat(), 0) > 0:
        streak += 1
        day -= timedelta(days=1)

    return streak


def longest_streak(contributions: list[dict]) -> int:
    longest = 0
    running = 0

    for entry in contributions:
        if entry["count"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    return longest


def year_contributions(totals: dict[str, int]) -> int:
    year = str(date.today().year)
    return totals.get(year, 0)


def latest_activity(token: str | None) -> str:
    try:
        events = fetch_json(
            f"https://api.github.com/users/{USERNAME}/events/public?per_page=10",
            token,
        )
    except urllib.error.URLError:
        events = []

    for event in events:
        event_type = event.get("type")
        repo = event.get("repo", {}).get("name", USERNAME)

        if event_type == "PushEvent":
            commits = event.get("payload", {}).get("commits", [])
            if commits:
                message = commits[-1]["message"].split("\n")[0][:72]
                return f"`{repo}` — _{message}_"

        if event_type == "CreateEvent":
            ref_type = event.get("payload", {}).get("ref_type", "resource")
            return f"`{repo}` — _created {ref_type}_"

        if event_type == "PullRequestEvent":
            action = event.get("payload", {}).get("action", "updated")
            return f"`{repo}` — _pull request {action}_"

    try:
        repos = fetch_json(
            f"https://api.github.com/users/{USERNAME}/repos?sort=updated&per_page=1",
            token,
        )
        if repos:
            repo = repos[0]
            return f"[`{repo['name']}`]({repo['html_url']}) — _last updated {repo['pushed_at'][:10]}_"
    except urllib.error.URLError:
        pass

    return "—"


def build_section(token: str | None) -> str:
    now = italy_now()
    updated = format_italy_time(now)

    try:
        contribution_data = fetch_json(
            f"https://github-contributions-api.jogruber.de/v4/{USERNAME}"
        )
        contributions = contribution_data.get("contributions", [])
        totals = contribution_data.get("total", {})
        streak_now = current_streak(contributions)
        streak_best = longest_streak(contributions)
        year_total = year_contributions(totals)
    except urllib.error.URLError:
        streak_now = "—"
        streak_best = "—"
        year_total = "—"

    activity = latest_activity(token)

    return f"""{START_MARKER}
> _Last updated: {updated}_

| Signal | Status |
| :--- | :--- |
| 🕐 **Local time (Italy)** | {updated} |
| 🔥 **Current streak** | {streak_now} days |
| 🏆 **Longest streak** | {streak_best} days |
| 📊 **Contributions ({date.today().year})** | {year_total} |
| 🔨 **Last activity** | {activity} |
{END_MARKER}"""


def update_readme(content: str, section: str) -> str:
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if not pattern.search(content):
        raise ValueError("Live status markers not found in README.md")

    return pattern.sub(section, content, count=1)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")

    with open(README_PATH, encoding="utf-8") as readme_file:
        content = readme_file.read()

    section = build_section(token)
    updated = update_readme(content, section)

    with open(README_PATH, "w", encoding="utf-8") as readme_file:
        readme_file.write(updated)

    print("README live status section updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

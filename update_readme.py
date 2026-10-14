#!/usr/bin/env python3
"""
Rebuilds the project list in README.md between the PROJECTS markers.
Runs daily via GitHub Actions (see .github/workflows/update-projects.yml).

- With a PROFILE_TOKEN secret: lists public AND private repos (private ones
  are shown without a link, since visitors can't open them).
- Without it: lists public repos only.
- Forks (e.g. bootcamp labs) go into a collapsible "archive" section.
- Add the topic "hide-from-profile" to any repo you want to keep off the list.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USERNAME = "MinalBorse"
README = "README.md"
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"
HIDE_TOPIC = "hide-from-profile"
TOKEN = os.getenv("PROFILE_TOKEN", "").strip()
INCLUDE_PRIVATE = os.getenv("INCLUDE_PRIVATE", "true").lower() == "true"
NOW = datetime.now(timezone.utc)


def api(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
    })
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_repos():
    if TOKEN:
        base = "https://api.github.com/user/repos?affiliation=owner&visibility=all"
    else:
        base = f"https://api.github.com/users/{USERNAME}/repos?type=owner"
    repos, page = [], 1
    while True:
        batch = api(f"{base}&per_page=100&page={page}&sort=pushed")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def last_activity(repo):
    stamp = repo.get("pushed_at") or repo.get("updated_at")
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def status(repo):
    days = (NOW - last_activity(repo)).days
    if days <= 7:
        return "🔥 Cooking"
    if days <= 30:
        return "🍲 Simmering"
    if days <= 180:
        return "😴 Resting"
    return "🧊 In the freezer"


def pretty(name):
    return re.sub(r"[-_]+", " ", name).strip()


def clean(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def build_section(repos):
    own = [
        r for r in repos
        if not r["fork"]
        and r["name"].lower() != USERNAME.lower()
        and HIDE_TOPIC not in r.get("topics", [])
        and (INCLUDE_PRIVATE or not r["private"])
    ]
    forks = [r for r in repos if r["fork"] and HIDE_TOPIC not in r.get("topics", [])]
    own.sort(key=last_activity, reverse=True)
    forks.sort(key=last_activity, reverse=True)

    lines = [
        "| Project | What it does | Tech | Status |",
        "|---|---|---|---|",
    ]
    for r in own:
        if r["private"]:
            name = f"🔒 **{pretty(r['name'])}**"
        else:
            name = f"[**{pretty(r['name'])}**]({r['html_url']})"
        desc = clean(r.get("description")) or "_Description loading... (I forgot to write one)_"
        tech = [r["language"]] if r.get("language") else []
        tech += [t for t in r.get("topics", []) if t != HIDE_TOPIC][:3]
        tech_str = " ".join(f"`{t}`" for t in tech) or "`mystery`"
        lines.append(f"| {name} | {desc} | {tech_str} | {status(r)} |")

    lines.append("")
    lines.append(
        f"<sub>{len(own)} projects and counting · 🔒 = private, ask me for a demo · "
        "auto-updated daily by a bot that never sleeps (unlike me)</sub>"
    )

    if forks:
        lines += [
            "",
            "<details>",
            f"<summary>🎓 <b>Bootcamp archive</b> ({len(forks)} labs where it all began)</summary>",
            "",
        ]
        for r in forks:
            lines.append(f"- [{pretty(r['name'])}]({r['html_url']})")
        lines += ["", "</details>"]

    return "\n".join(lines)


def main():
    with open(README, encoding="utf-8") as f:
        content = f.read()
    if START not in content or END not in content:
        raise SystemExit(f"Markers {START} / {END} not found in {README}")

    section = build_section(fetch_repos())
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    new_content = pattern.sub(f"{START}\n{section}\n{END}", content)

    if new_content != content:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("README updated.")
    else:
        print("No changes.")


if __name__ == "__main__":
    main()

"""Refresh the dynamic sections of README.md (latest repos, recent activity, timestamp).

Runs in GitHub Actions; uses GITHUB_TOKEN when present to avoid rate limits.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = os.environ.get("GH_USER", "Kamrul01685")
README = Path(__file__).resolve().parent.parent / "README.md"
TOKEN = os.environ.get("GITHUB_TOKEN")


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "profile-readme-updater"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def ago(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = (datetime.now(timezone.utc) - dt).total_seconds()
    for unit, n in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if s >= n:
            v = int(s // n)
            return f"{v} {unit}{'s' if v != 1 else ''} ago"
    return "just now"


def repos_section():
    repos = get(f"https://api.github.com/users/{USER}/repos?sort=pushed&per_page=30")
    repos = [r for r in repos if not r["fork"] and r["name"].lower() != USER.lower()][:6]
    rows = ["| Repository | Description | Language | ⭐ | Updated |", "|---|---|---|---|---|"]
    for r in repos:
        desc = (r["description"] or "").replace("|", "\\|")
        rows.append(f"| [**{r['name']}**]({r['html_url']}) | {desc} | {r['language'] or '—'} "
                    f"| {r['stargazers_count']} | {ago(r['pushed_at'])} |")
    return "\n".join(rows)


def describe(e):
    repo = e["repo"]["name"]
    link = f"[{repo}](https://github.com/{repo})"
    p = e.get("payload", {})
    t = e["type"]
    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits", [])) or 1
        return f"📝 Pushed {n} commit{'s' if n != 1 else ''} to {link}"
    if t == "CreateEvent":
        return f"🆕 Created {p.get('ref_type', 'repository')} {('`' + p['ref'] + '` in ') if p.get('ref') else ''}{link}"
    if t == "WatchEvent":
        return f"⭐ Starred {link}"
    if t == "ForkEvent":
        return f"🍴 Forked {link}"
    if t == "PullRequestEvent":
        pr = p["pull_request"]
        return f"🔀 {p['action'].capitalize()} PR [#{pr['number']}]({pr['html_url']}) in {link}"
    if t == "IssuesEvent":
        i = p["issue"]
        return f"❗ {p['action'].capitalize()} issue [#{i['number']}]({i['html_url']}) in {link}"
    if t == "ReleaseEvent":
        return f"🚀 Released `{p['release']['tag_name']}` in {link}"
    if t == "PublicEvent":
        return f"🌍 Made {link} public"
    return None


def activity_section():
    events = get(f"https://api.github.com/users/{USER}/events/public?per_page=50")
    lines = []
    for e in events:
        if e["repo"]["name"].lower() == f"{USER}/{USER}".lower():
            continue  # skip the bot's own README commits
        d = describe(e)
        if d:
            lines.append(f"{len(lines) + 1}. {d} · <sub>{ago(e['created_at'])}</sub>")
        if len(lines) == 6:
            break
    return "\n".join(lines) or "_No recent public activity._"


def replace(text, tag, body):
    pat = re.compile(rf"(<!-- {tag}:START -->)(.*?)(<!-- {tag}:END -->)", re.S)
    return pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main():
    text = README.read_text(encoding="utf-8")
    text = replace(text, "REPOS", repos_section())
    text = replace(text, "ACTIVITY", activity_section())
    stamp = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    text = replace(text, "LAST-UPDATED", f'<p align="center"><sub>🔄 Auto-updated {stamp}</sub></p>')
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

"""Rewrite the SPARK_LOG block in README.md with recent public GitHub activity,
formatted like a Spark driver log."""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "mayankgulaty")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
MAX_LINES = 8


def fetch_events():
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=50",
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"{USER}-readme"},
    )
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def describe(e):
    repo = e["repo"]["name"]
    if repo.lower() == f"{USER}/{USER}".lower():
        return None  # skip README bot commits
    t, p = e["type"], e.get("payload", {})
    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits", [])) or 1
        msg = (p.get("commits") or [{}])[-1].get("message", "").splitlines()[0][:48] if p.get("commits") else ""
        tail = f' "{msg}"' if msg else ""
        return "INFO", "DAGScheduler", f"Job finished: pushed {n} commit{'s' if n != 1 else ''} to {repo}{tail}"
    if t == "CreateEvent":
        kind = p.get("ref_type", "repository")
        if kind == "repository":
            return "INFO", "SparkContext", f"New application registered: {repo}"
        return "INFO", "BlockManager", f"Created {kind} {p.get('ref')} in {repo}"
    if t == "PullRequestEvent":
        action = "merged" if p.get("pull_request", {}).get("merged") else p.get("action", "updated")
        return "INFO", "TaskSetManager", f"PR #{p.get('number')} {action} in {repo}"
    if t == "IssuesEvent":
        return "WARN", "TaskSetManager", f"Issue #{p['issue']['number']} {p.get('action')} in {repo}"
    if t == "WatchEvent":
        return "INFO", "BroadcastManager", f"Starred {repo}"
    if t == "ForkEvent":
        return "INFO", "ShuffleManager", f"Forked {repo}"
    if t == "ReleaseEvent":
        tag = p.get("release", {}).get("tag_name", "")
        return "INFO", "SparkContext", f"Shipped release {tag} of {repo}"
    return None


def build_block(events):
    lines = []
    for e in events:
        d = describe(e)
        if not d:
            continue
        ts = datetime.strptime(e["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y/%m/%d %H:%M:%S")
        level, comp, text = d
        lines.append(f"{ts} {level:<4} {comp}: {text}")
        if len(lines) >= MAX_LINES:
            break
    if not lines:
        today = datetime.now(timezone.utc).strftime("%y/%m/%d 06:00:00")
        return "```log\n" + f"{today} INFO DAGScheduler: No public jobs lately. Probably out on a long run." + "\n```"
    last_ts = lines[0][:17]  # newest event; keeps the block stable when nothing new happened
    lines.reverse()
    lines.append(f"{last_ts} INFO SparkContext: Driver still alive. Coffee levels nominal.")
    return "```log\n" + "\n".join(lines) + "\n```"


def main():
    block = build_block(fetch_events())
    with open(README, encoding="utf-8") as f:
        readme = f.read()
    new = re.sub(
        r"(<!--SPARK_LOG:START-->\n).*?(\n<!--SPARK_LOG:END-->)",
        lambda m: m.group(1) + block + m.group(2),
        readme,
        flags=re.S,
    )
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)


if __name__ == "__main__":
    main()

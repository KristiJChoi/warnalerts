#!/usr/bin/env python3
"""
process_subscriptions.py
Reads open GitHub Issues tagged 'subscription', updates data/subscribers.json,
then closes the issue.
"""

import os
import json
import requests
from pathlib import Path

REPO_OWNER = os.environ.get("REPO_OWNER", "")
REPO_NAME  = os.environ.get("REPO_NAME", "")
GH_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
SUBSCRIBERS_FILE = Path("data/subscribers.json")

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def load_subscribers() -> list[dict]:
    if not SUBSCRIBERS_FILE.exists():
        return []
    with open(SUBSCRIBERS_FILE) as f:
        return json.load(f)

def save_subscribers(subs: list[dict]):
    SUBSCRIBERS_FILE.parent.mkdir(exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f, indent=2)

def get_open_subscription_issues() -> list[dict]:
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    params = {"state": "open", "labels": "subscription", "per_page": 100}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()

def close_issue(issue_number: int, comment: str):
    # Post a comment
    requests.post(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments",
        headers=HEADERS,
        json={"body": comment}
    )
    # Close the issue
    requests.patch(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}",
        headers=HEADERS,
        json={"state": "closed"}
    )

def main():
    issues = get_open_subscription_issues()
    print(f"Found {len(issues)} pending subscription issue(s).")
    if not issues:
        return

    subs = load_subscribers()

    for issue in issues:
        try:
            data = json.loads(issue["body"])
        except Exception:
            print(f"  ⚠ Could not parse issue #{issue['number']} — skipping.")
            close_issue(issue["number"], "⚠ Could not parse this request. Please re-submit via the website.")
            continue

        action  = data.get("action")
        email   = data.get("email", "").strip().lower()
        company = data.get("company", "").strip()

        if action == "subscribe":
            # Avoid duplicates
            exists = any(
                s["email"].lower() == email and s["company"].lower() == company.lower()
                for s in subs
            )
            if not exists:
                subs.append({"email": email, "company": company})
                print(f"  ✓ Subscribed {email} → '{company}'")
                close_issue(issue["number"], f"✅ Subscribed `{email}` to alerts for **{company}**.")
            else:
                print(f"  — Already subscribed: {email} → '{company}'")
                close_issue(issue["number"], f"ℹ️ `{email}` is already subscribed to **{company}**.")

        elif action == "unsubscribe":
            before = len(subs)
            if company:
                subs = [s for s in subs if not (s["email"].lower() == email and s["company"].lower() == company.lower())]
            else:
                subs = [s for s in subs if s["email"].lower() != email]
            removed = before - len(subs)
            print(f"  ✓ Removed {removed} subscription(s) for {email}")
            close_issue(issue["number"], f"✅ Removed {removed} alert(s) for `{email}`.")

        else:
            close_issue(issue["number"], "⚠ Unknown action. Please re-submit via the website.")

    save_subscribers(subs)
    print(f"Saved {len(subs)} total subscriber(s).")

if __name__ == "__main__":
    main()

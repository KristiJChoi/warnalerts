#!/usr/bin/env python3
"""
check_warn.py
Downloads the latest CA EDD WARN report XLSX, checks it against subscribers,
and sends email alerts via Resend if a company name matches.
"""

import os
import json
import hashlib
import requests
import openpyxl
import resend
from io import BytesIO
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
WARN_XLSX_URL  = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
WARN_PAGE_URL  = "https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN/"
SUBSCRIBERS_FILE = Path("data/subscribers.json")
HASH_FILE        = Path("data/last_hash.txt")

resend.api_key = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL     = os.environ.get("FROM_EMAIL", "alerts@yourdomain.com")

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_subscribers() -> list[dict]:
    if not SUBSCRIBERS_FILE.exists():
        return []
    with open(SUBSCRIBERS_FILE) as f:
        return json.load(f)

def load_last_hash() -> str:
    if not HASH_FILE.exists():
        return ""
    return HASH_FILE.read_text().strip()

def save_hash(h: str):
    HASH_FILE.write_text(h)

def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def download_warn_xlsx() -> tuple[bytes, str]:
    """Downloads the WARN XLSX and returns (content_bytes, sha256_hash)."""
    print(f"Downloading WARN report from {WARN_XLSX_URL}…")
    headers = {"User-Agent": "Mozilla/5.0 CA-WARN-Tracker/1.0"}
    resp = requests.get(WARN_XLSX_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    content = resp.content
    return content, file_hash(content)

def parse_warn_xlsx(content: bytes) -> list[dict]:
    """
    Parse the WARN XLSX into a list of row dicts.
    EDD's format typically has columns like:
      Notice Date | Effective Date | Received Date | Company | City | County |
      No. of Employees Affected | Layoff/Closure | Industry
    Column positions may shift — we detect the header row.
    """
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))

    # Find the header row (look for a row containing "Company" or "Employer")
    header_idx = None
    headers = []
    for i, row in enumerate(rows):
        row_str = [str(c).lower().strip() if c else "" for c in row]
        if any("company" in c or "employer" in c for c in row_str):
            header_idx = i
            headers = [str(c).strip() if c else f"col_{j}" for j, c in enumerate(row)]
            break

    if header_idx is None:
        print("⚠ Could not find header row in XLSX — using row 0 as header.")
        header_idx = 0
        headers = [str(c).strip() if c else f"col_{j}" for j, c in enumerate(rows[0])]

    entries = []
    for row in rows[header_idx + 1:]:
        if all(c is None for c in row):
            continue
        entry = {headers[j]: (str(v).strip() if v is not None else "") for j, v in enumerate(row)}
        entries.append(entry)

    print(f"  Parsed {len(entries)} WARN entries.")
    return entries

def find_company_key(headers: list[str]) -> str:
    """Return whichever column header looks like the company name."""
    for h in headers:
        if "company" in h.lower() or "employer" in h.lower():
            return h
    return headers[0] if headers else "Company"

def check_matches(entries: list[dict], company_watch: str) -> list[dict]:
    """Return entries where the company name contains company_watch (case-insensitive)."""
    needle = company_watch.lower()
    if not entries:
        return []
    company_key = find_company_key(list(entries[0].keys()))
    return [e for e in entries if needle in e.get(company_key, "").lower()]

def send_alert(subscriber: dict, matches: list[dict]):
    """Send a Resend email alert for matched entries."""
    company_watch = subscriber["company"]
    to_email      = subscriber["email"]

    rows_html = ""
    for m in matches:
        rows_html += "<tr>"
        for k, v in m.items():
            rows_html += f"<td style='padding:6px 10px;border-bottom:1px solid #e8e6e0;font-size:13px'>{v}</td>"
        rows_html += "</tr>"

    headers_html = ""
    if matches:
        for k in matches[0].keys():
            headers_html += f"<th style='padding:8px 10px;text-align:left;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#787878;border-bottom:2px solid #2a2a35'>{k}</th>"

    body_html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0c0c0e;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif">
  <div style="max-width:640px;margin:40px auto;background:#141418;border:1px solid #2a2a35;border-radius:8px;overflow:hidden">
    <div style="background:#e8c547;padding:20px 32px">
      <p style="margin:0;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#0c0c0e;font-weight:600">CA WARN Alert</p>
    </div>
    <div style="padding:32px">
      <h1 style="margin:0 0 8px;font-size:24px;color:#e8e6e0;font-weight:400">
        <em style="font-style:italic;color:#e8c547">{company_watch}</em> appeared in a new WARN filing
      </h1>
      <p style="color:#787878;font-size:14px;line-height:1.6;margin:0 0 28px">
        The California EDD WARN report was updated and contains {len(matches)} notice(s) matching your watch for <strong style="color:#e8e6e0">{company_watch}</strong>.
      </p>

      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
          <thead><tr>{headers_html}</tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>

      <a href="{WARN_PAGE_URL}" style="display:inline-block;background:#e8c547;color:#0c0c0e;text-decoration:none;font-size:12px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;padding:12px 24px;border-radius:6px">
        View Full WARN Report →
      </a>

      <p style="margin:32px 0 0;font-size:12px;color:#787878">
        You're receiving this because you subscribed to WARN alerts for <strong>{company_watch}</strong>.<br>
        Report checked: {datetime.now().strftime('%B %d, %Y at %I:%M %p PT')}
      </p>
    </div>
  </div>
</body>
</html>
"""

    print(f"  → Sending alert to {to_email} for match on '{company_watch}'…")
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to_email,
            "subject": f"⚠ WARN Alert: {company_watch} filed a layoff notice",
            "html": body_html,
        })
        print(f"    ✓ Sent.")
    except Exception as e:
        print(f"    ✗ Failed to send email: {e}")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    subscribers = load_subscribers()
    if not subscribers:
        print("No subscribers — nothing to do.")
        return

    print(f"Loaded {len(subscribers)} subscriber(s).")

    content, current_hash = download_warn_xlsx()
    last_hash = load_last_hash()

    if current_hash == last_hash:
        print("WARN report has not changed since last check. No alerts needed.")
        return

    print(f"New report detected! (hash changed from {last_hash[:8]}… → {current_hash[:8]}…)")
    entries = parse_warn_xlsx(content)

    alert_count = 0
    for sub in subscribers:
        matches = check_matches(entries, sub["company"])
        if matches:
            print(f"  Match found for '{sub['company']}' ({len(matches)} row(s)).")
            send_alert(sub, matches)
            alert_count += 1
        else:
            print(f"  No match for '{sub['company']}'.")

    save_hash(current_hash)
    print(f"\nDone. {alert_count} alert(s) sent.")

if __name__ == "__main__":
    main()

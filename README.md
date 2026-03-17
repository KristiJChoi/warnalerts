# CA WARN Act Alert Tracker

A static website + GitHub Actions pipeline that monitors California's EDD WARN Act report and sends email alerts when a watched company files a layoff notice.

**Live site:** hosted via GitHub Pages  
**Data source:** [CA EDD WARN Report](https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN/) (updated Tue/Thu)

---

## How it works

```
Website (GitHub Pages)
   └── User submits company + email
         └── Creates a GitHub Issue (labeled "subscription")

GitHub Action (runs Tue + Thu @ 10am PT)
   ├── process_subscriptions.py  → reads Issues → updates data/subscribers.json
   └── check_warn.py             → downloads WARN XLSX → checks matches → sends emails via Resend
```

---

## Setup (one-time, ~15 minutes)

### 1. Create the GitHub repo

```bash
# Clone or fork this repo, then push to your own GitHub account
git init warn-tracker
cd warn-tracker
# copy all these files in, then:
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/warn-tracker.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `/ (root)`
4. Save — your site will be live at `https://YOUR_USERNAME.github.io/warn-tracker/`

### 3. Set up Resend (free email sending)

1. Sign up at [resend.com](https://resend.com) (free tier: 3,000 emails/month)
2. Go to **API Keys** → create a new key
3. Under **Domains**, either:
   - Add and verify your own domain (recommended), OR
   - Use `onresend.dev` to test without a domain

### 4. Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret name | Value |
|------------|-------|
| `RESEND_API_KEY` | Your Resend API key (starts with `re_`) |
| `FROM_EMAIL` | e.g. `alerts@yourdomain.com` or `warn@onresend.dev` |

### 5. Update the website config

Open `index.html` and update these two lines near the bottom:

```javascript
const REPO_OWNER = 'YOUR_GITHUB_USERNAME'; // ← your GitHub username
const REPO_NAME  = 'warn-tracker';          // ← your repo name (if different)
```

### 6. Create the "subscription" label

Go to your repo → **Issues** → **Labels** → **New label**
- Name: `subscription`
- Color: any

### 7. Test it manually

Go to your repo → **Actions** → **Check CA WARN Report** → **Run workflow**

This will download the XLSX, process any pending subscriptions, and send alerts if matches are found.

---

## File structure

```
warn-tracker/
├── index.html                          ← The website (served by GitHub Pages)
├── .github/
│   └── workflows/
│       └── check-warn.yml              ← Scheduled GitHub Action (Tue + Thu)
├── scripts/
│   ├── check_warn.py                   ← Downloads XLSX, checks matches, sends emails
│   └── process_subscriptions.py       ← Processes GitHub Issue subscriptions
├── data/
│   ├── subscribers.json                ← List of {email, company} subscriptions
│   └── last_hash.txt                   ← SHA256 of last seen WARN report
└── README.md
```

---

## Privacy notes

- `data/subscribers.json` is stored **publicly** in this repo (since GitHub Pages repos are public). 
- If you want private subscriber data, switch to a private repo and use GitHub Actions with a deploy token for Pages, or use Supabase for storage.
- Emails are never displayed on the website.

---

## Customizing the schedule

Edit `.github/workflows/check-warn.yml`:

```yaml
on:
  schedule:
    - cron: '0 18 * * 2'   # Tuesday  10am PT (UTC-8)
    - cron: '0 18 * * 4'   # Thursday 10am PT (UTC-8)
```

Cron format: `minute hour day-of-month month day-of-week`

---

## Troubleshooting

**Action fails on "pip install"** → Make sure you're on `ubuntu-latest`

**No emails sent** → Check that `RESEND_API_KEY` and `FROM_EMAIL` secrets are set correctly

**XLSX parse error** → EDD occasionally changes column layouts. Open `scripts/check_warn.py` and update the column detection logic in `parse_warn_xlsx()`

**GitHub Issues not processing** → Make sure the `subscription` label exists in your repo

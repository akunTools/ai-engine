"""
reporter.py
Buat laporan harian tentang status staging dan publish log.
"""
import os
import json
import smtplib
import urllib.request
from email.mime.text import MIMEText
from datetime import datetime, timedelta

BRAIN_PAT     = os.environ.get("BRAIN_PAT", "")
BRAIN_REPO    = os.environ.get("BRAIN_REPO", "")
ENGINE_REPO   = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
SMTP_SERVER   = os.environ.get("BREVO_SMTP_SERVER", "smtp-relay.brevo.com")
SMTP_PORT     = int(os.environ.get("BREVO_SMTP_PORT", 587))
SMTP_USER     = os.environ.get("BREVO_USERNAME", "")
SMTP_PASS     = os.environ.get("BREVO_PASSWORD", "")
FROM_EMAIL    = os.environ.get("BREVO_FROM_EMAIL", "")
NOTIFY_EMAIL  = os.environ.get("NOTIFY_EMAIL", "")
API_BASE      = "https://api.github.com"


def _headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-engine"
    }


def count_staging(folder: str) -> dict:
    """Hitung file di staging ready dan drafts."""
    def _count(path):
        url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
        req = urllib.request.Request(url, headers=_headers(BRAIN_PAT))
        try:
            with urllib.request.urlopen(req) as r:
                items = json.loads(r.read())
            return len([i for i in items
                        if i["type"] == "file" and i["name"] != ".gitkeep"])
        except Exception:
            return 0

    return {
        "ready":  _count(f"staging/{folder}/ready"),
        "drafts": _count(f"staging/{folder}/drafts")
    }


def get_recent_publishes() -> list:
    """Ambil daftar file yang dipublish dalam 24 jam terakhir."""
    published = []
    for folder in ["articles", "tools"]:
        url = (f"{API_BASE}/repos/{ENGINE_REPO}/contents/{folder}"
               f"?ref=output")
        req = urllib.request.Request(url, headers=_headers(GITHUB_TOKEN))
        try:
            with urllib.request.urlopen(req) as r:
                items = json.loads(r.read())
            for item in items:
                if item["name"] not in (".gitkeep", "index.html"):
                    published.append({
                        "folder": folder,
                        "name": item["name"]
                    })
        except Exception:
            pass
    return published


def build_report() -> str:
    """Buat teks laporan harian."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    articles = count_staging("articles")
    tools    = count_staging("tools")

    total_ready = articles["ready"] + tools["ready"]

    if total_ready == 0:
        status = "⚠️ STAGING EMPTY"
        action = "Tambah konten baru ke staging/articles/ready/ atau staging/tools/ready/"
    else:
        status = "✅ OPERATIONAL"
        action = "None — system is healthy."

    report = f"""# Daily Report — {today}

## Status
{status}

## Staging Queue
- Articles ready  : {articles['ready']}
- Articles drafts : {articles['drafts']}
- Tools ready     : {tools['ready']}
- Tools drafts    : {tools['drafts']}

## Action Required
{action}

---
Next article publish: automatic (every 2 days at 02:00 UTC)
Next tool publish   : automatic (1st and 15th of each month at 06:00 UTC)
"""
    return report


def send_email(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = NOTIFY_EMAIL

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, [NOTIFY_EMAIL], msg.as_string())
    print(f"Email sent: {subject}")


if __name__ == "__main__":
    report  = build_report()
    subject = "[AI Engine] Daily Report"
    send_email(subject, report)
    print(report)

"""
reporter.py
Generate laporan harian.
Menampilkan: publish kemarin, staging count, failed publish.
"""
import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from loader import fetch_file, update_file, list_folder


def count_staging(folder: str) -> int:
    """Hitung jumlah file HTML di folder staging."""
    try:
        return len([
            f for f in list_folder(folder)
            if f["name"].endswith(".html")
        ])
    except Exception:
        return 0


def run():
    yesterday = datetime.utcnow() - timedelta(days=1)
    date_str  = yesterday.strftime("%Y-%m-%d")

    # Baca log kemarin
    success_count   = 0
    failure_entries = []

    try:
        d = json.loads(fetch_file(f"logs/success/{date_str}.json"))
        success_count = len(d.get("entries", []))
    except Exception:
        pass

    try:
        d = json.loads(fetch_file(f"logs/failures/{date_str}.json"))
        failure_entries = d.get("entries", [])
    except Exception:
        pass

    # Hitung staging
    articles_ready  = count_staging("staging/articles/ready")
    articles_drafts = count_staging("staging/articles/drafts")
    tools_ready     = count_staging("staging/tools/ready")
    tools_drafts    = count_staging("staging/tools/drafts")

    # Status staging
    staging_status = "OK"
    if articles_ready == 0 and tools_ready == 0:
        staging_status = "EMPTY — Write new content and save to staging/ready"
    elif articles_ready == 0:
        staging_status = "Articles empty — Add articles to staging/articles/ready"
    elif tools_ready == 0:
        staging_status = "Tools empty — Add tools to staging/tools/ready"

    failure_lines = "\n".join([
        f"- {e.get('task_type','?')}: "
        f"{e.get('result', {}).get('issues', [])}"
        for e in failure_entries
    ]) or "None"

    report = f"""# Daily Report — {date_str}

## Published Yesterday
- Success : {success_count}
- Failed  : {len(failure_entries)}

## Staging Queue
- Articles ready  : {articles_ready} waiting to publish
- Articles drafts : {articles_drafts} in progress
- Tools ready     : {tools_ready} waiting to publish
- Tools drafts    : {tools_drafts} in progress
- Status          : {staging_status}

## Publish Failures
{failure_lines}

## Action Required
{"Review publish failures. Check Actions tab for error details." if failure_entries else "None — system healthy."}

---
Generated at {datetime.utcnow().isoformat()}
"""

    update_file(
        f"logs/reports/{date_str}-daily.md",
        report,
        f"[reporter] Daily report {date_str}"
    )

    with open("/tmp/daily_report.txt", "w") as f:
        f.write(report)

    if failure_entries:
        with open("/tmp/has_failures.flag", "w") as f:
            f.write(str(len(failure_entries)))

    print(report)


if __name__ == "__main__":
    run()

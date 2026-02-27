"""
monitor.py
Pantau halaman affiliate dan sumber data.
Deteksi perubahan signifikan dan simpan ke pending_updates/.
Kirim notifikasi jika ada perubahan.
"""
import os
import sys
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from loader import fetch_file, fetch_json, update_file


def fetch_page_text(url: str) -> str:
    """
    Fetch halaman web dan return sebagai plain text.
    Raise Exception jika gagal.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
            # Hapus tag HTML, ambil teks saja
            text = re.sub(r'<style[^>]*>.*?</style>',
                          ' ', html, flags=re.DOTALL)
            text = re.sub(r'<script[^>]*>.*?</script>',
                          ' ', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            # Ambil 5000 karakter pertama yang relevan
            return text[:5000]
    except Exception as e:
        raise Exception(f"Failed to fetch {url}: {e}")


def diff_percentage(old: str, new: str) -> float:
    """
    Hitung persentase perubahan antara dua teks.
    Return: float persentase (0-100).
    """
    if not old:
        return 100.0
    old_words = set(old.lower().split())
    new_words = set(new.lower().split())
    if not old_words:
        return 100.0
    changed = len(old_words.symmetric_difference(new_words))
    return (changed / len(old_words)) * 100


def run():
    pages_config = fetch_json("config/monitored_pages.json")
    changes_found = []
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    for page in pages_config["pages"]:
        page_id = page["id"]
        print(f"\nChecking: {page_id}")
        print(f"URL: {page['url']}")

        # Coba fetch halaman
        try:
            current_text = fetch_page_text(page["url"])
            print(f"Fetched: {len(current_text)} chars")
        except Exception as e:
            print(f"Skip {page_id}: {e}")
            continue

        # Baca snapshot lama
        old_text = ""
        try:
            old_text = fetch_file(page["snapshot_file"])
        except Exception:
            print("No previous snapshot found — creating first snapshot")

        # Hitung perubahan
        pct = diff_percentage(old_text, current_text)
        print(f"Change: {pct:.1f}%")

        if pct > 5.0 and old_text:
            # Perubahan signifikan terdeteksi
            print(f"Significant change detected!")
            diff_note = f"""# Change Detected: {page_id}
Date: {date_str}
URL: {page['url']}
Change percentage: {pct:.1f}%
Knowledge file to update: {page['knowledge_file']}

## NEW CONTENT (first 2000 chars):
{current_text[:2000]}

## ACTION REQUIRED:
Review the above and update {page['knowledge_file']}
via webhook command update_knowledge if data has changed.
Use action: replace for JSON files, append for .txt files.
"""
            # Simpan ke pending_updates
            update_file(
                f"pending_updates/{date_str}-{page_id}.md",
                diff_note,
                f"[monitor] Change detected: {page_id}"
            )
            changes_found.append({
                "id": page_id,
                "url": page["url"],
                "change_pct": round(pct, 1),
                "knowledge_file": page["knowledge_file"]
            })

        # Update snapshot dengan teks terbaru
        update_file(
            page["snapshot_file"],
            current_text,
            f"[monitor] Snapshot: {page_id}"
        )

        # Update last_checked
        page["last_checked"] = datetime.utcnow().isoformat()

    # Simpan timestamp last_checked yang sudah diupdate
    update_file(
        "config/monitored_pages.json",
        json.dumps(pages_config, indent=2),
        "[monitor] Update last_checked timestamps"
    )

    # Simpan summary perubahan untuk workflow kirim email
    if changes_found:
        summary = json.dumps(changes_found, indent=2)
        with open("/tmp/changes_detected.json", "w") as f:
            f.write(summary)
        print(f"\n{len(changes_found)} change(s) detected.")
        print("Email notification will be sent.")
    else:
        print("\nNo significant changes detected.")


if __name__ == "__main__":
    run()

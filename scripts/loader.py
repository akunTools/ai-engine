"""
loader.py
Fetch dan update file dari repo ai-brain via GitHub API.
Digunakan oleh semua script lain untuk membaca data dari
private repo tanpa perlu akses langsung ke GitHub.
"""
import os
import json
import base64
import urllib.request
import urllib.error

BRAIN_PAT  = os.environ["BRAIN_PAT"]
BRAIN_REPO = os.environ.get("BRAIN_REPO", "YOUR_USERNAME/ai-brain")
API_BASE   = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {BRAIN_PAT}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-engine"
    }


def fetch_file(path: str) -> str:
    """
    Fetch satu file dari ai-brain.
    Return: isi file sebagai string.
    Raise Exception jika file tidak ditemukan.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as r:
            d = json.loads(r.read())
            return base64.b64decode(d["content"]).decode("utf-8")
    except urllib.error.HTTPError as e:
        raise Exception(f"fetch_file failed for {path}: HTTP {e.code}")


def fetch_json(path: str) -> dict:
    """Fetch file JSON dari ai-brain. Return sebagai dict."""
    return json.loads(fetch_file(path))


def update_file(path: str, content: str, message: str) -> bool:
    """
    Buat atau update file di ai-brain.
    Return: True jika berhasil, False jika gagal.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    sha = None

    # Cek apakah file sudah ada untuk mendapatkan SHA
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError:
        pass  # File belum ada, akan dibuat baru

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(f"update_file error for {path}: {e.code} {e.read().decode()}")
        return False


def get_next_pending(task_type: str = None) -> dict | None:
    """
    Ambil topik pertama dengan status 'pending' dari queue.
    Jika task_type diberikan, filter berdasarkan task_type.
    Return: dict topik atau None jika queue kosong.
    """
    schedule = fetch_json("config/schedule.json")
    for t in schedule.get("topic_queue", []):
        if t.get("status") == "pending":
            if task_type is None or t.get("task_type") == task_type:
                return t
    return None


def mark_topic(topic_id: str, status: str) -> bool:
    """Update status topik di schedule.json."""
    schedule = fetch_json("config/schedule.json")
    for t in schedule.get("topic_queue", []):
        if t["id"] == topic_id:
            t["status"] = status
            break
    return update_file(
        "config/schedule.json",
        json.dumps(schedule, indent=2),
        f"[engine] Mark {topic_id} as {status}"
    )


def write_log(date_str: str, entry: dict, status: str) -> bool:
    """Tulis satu entry log ke file log harian."""
    log_path = f"logs/{status}/{date_str}.json"
    try:
        existing = fetch_file(log_path)
        log_data = json.loads(existing)
    except Exception:
        log_data = {"date": date_str, "entries": []}

    log_data["entries"].append(entry)
    return update_file(
        log_path,
        json.dumps(log_data, indent=2),
        f"[engine] Log entry {date_str}"
    )

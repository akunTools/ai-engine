"""
loader.py
Fetch dan update file dari repo ai-brain via GitHub API.
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
    """Fetch satu file dari ai-brain. Return isi sebagai string."""
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


def list_folder(path: str) -> list:
    """
    Ambil daftar semua file dalam folder di ai-brain.
    Return: list dict berisi name, path, sha.
    Berguna untuk membaca isi folder staging/.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as r:
            items = json.loads(r.read())
            return [
                {
                    "name": i["name"],
                    "path": i["path"],
                    "sha":  i["sha"]
                }
                for i in items
                if i["type"] == "file" and i["name"] != ".gitkeep"
            ]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise Exception(f"list_folder failed for {path}: HTTP {e.code}")


def update_file(path: str, content: str, message: str) -> bool:
    """Buat atau update file di ai-brain."""
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    sha = None

    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError:
        pass

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


def delete_file(path: str, sha: str, message: str) -> bool:
    """
    Hapus file dari ai-brain.
    Dipanggil setelah file staging berhasil dipublish.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    payload = {"message": message, "sha": sha}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        print(f"delete_file error for {path}: {e.code}")
        return False


def get_next_pending(task_type: str = None) -> dict | None:
    """Ambil topik pertama dengan status pending dari queue."""
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

def list_folder(path: str) -> list:
    """
    Ambil daftar file dalam satu folder di ai-brain.
    Return: list dict berisi name, path, sha.
    Return list kosong jika folder tidak ada.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as r:
            items = json.loads(r.read())
            return [
                {
                    "name": i["name"],
                    "path": i["path"],
                    "sha":  i["sha"]
                }
                for i in items
                if i["type"] == "file" and i["name"] != ".gitkeep"
            ]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise Exception(f"list_folder failed for {path}: HTTP {e.code}")


def delete_file(path: str, sha: str, message: str) -> bool:
    """
    Hapus satu file dari ai-brain.
    Dipanggil setelah file staging berhasil dipublish.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    payload = {"message": message, "sha": sha}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        print(f"delete_file error for {path}: {e.code}")
        return False

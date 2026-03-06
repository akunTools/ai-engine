"""
loader.py
Ambil file dari repo ai-brain via GitHub API.
"""
import os
import json
import base64
import urllib.request
import urllib.error

BRAIN_PAT  = os.environ.get("BRAIN_PAT", "")
BRAIN_REPO = os.environ.get("BRAIN_REPO", "YOUR_USERNAME/ai-brain")
API_BASE   = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {BRAIN_PAT}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def fetch_file(path: str) -> str:
    """Ambil isi file teks dari ai-brain."""
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    return base64.b64decode(data["content"]).decode("utf-8")


def fetch_json(path: str) -> dict:
    """Ambil dan parse file JSON dari ai-brain."""
    return json.loads(fetch_file(path))


def update_file(path: str, content: str, message: str) -> bool:
    """Update atau buat file di ai-brain."""
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    sha = None
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
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
    with urllib.request.urlopen(req) as r:
        return r.status in (200, 201)


def list_folder(path: str) -> list:
    """
    Daftar semua file dalam sebuah folder di ai-brain.
    Return: [{name, path, sha}] atau [] jika folder tidak ada.
    """
    url = f"{API_BASE}/repos/{BRAIN_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req) as r:
            items = json.loads(r.read())
        return [
            {"name": i["name"], "path": i["path"], "sha": i["sha"]}
            for i in items
            if i["type"] == "file" and i["name"] != ".gitkeep"
        ]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def delete_file(path: str, sha: str, message: str) -> bool:
    """Hapus file dari ai-brain (dipakai setelah konten dipublish)."""
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
    except Exception:
        return False

"""
publisher.py
Commit file output ke branch 'output' di repo ai-engine.
"""
import os
import json
import base64
import urllib.request
import urllib.error

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "YOUR_USERNAME/ai-engine")
ENGINE_TOKEN  = os.environ.get("GITHUB_TOKEN")
OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {ENGINE_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "ai-engine"
    }


def publish(filename: str, content: str,
            subfolder: str = "articles") -> bool:
    """
    Publish file ke branch output di ai-engine.
    subfolder: 'articles' atau 'tools'
    Return: True jika berhasil, False jika gagal.
    """
    path = f"{subfolder}/{filename}"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"
    sha  = None

    # Cek apakah file sudah ada
    try:
        req = urllib.request.Request(
            f"{url}?ref={OUTPUT_BRANCH}",
            headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError:
        pass  # File baru

    payload = {
        "message": f"[engine] Publish {path}",
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("utf-8"),
        "branch": OUTPUT_BRANCH
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as r:
            ok = r.status in (200, 201)
            if ok:
                print(f"Published: {path}")
            return ok
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Publish failed for {path}: {e.code} {body}")
        return False

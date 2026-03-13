"""
publisher.py
Publish file HTML ke branch output di repo ai-engine.
"""
import os
import json
import base64
import urllib.request

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def publish_html(folder: str, filename: str, html: str) -> bool:
    """
    Publish file HTML ke folder articles/ atau tools/ di branch output.
    Return True jika berhasil.
    """
    path = f"{folder}/{filename}"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"
    sha  = None

    try:
        req = urllib.request.Request(
            f"{url}?ref={OUTPUT_BRANCH}", headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[pipeline] Publish {folder}/{filename}",
        "content": base64.b64encode(html.encode("utf-8")).decode("utf-8"),
        "branch":  OUTPUT_BRANCH
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


def publish_binary(folder: str, filename: str, data: bytes) -> bool:
    """
    Publish file binary (PNG, dll) ke folder di branch output.
    Sama dengan publish_html tapi menerima bytes, bukan string.
    Return True jika berhasil.
    """
    path = f"{folder}/{filename}"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"
    sha  = None

    try:
        req = urllib.request.Request(
            f"{url}?ref={OUTPUT_BRANCH}", headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[pipeline] Publish {folder}/{filename}",
        "content": base64.b64encode(data).decode("utf-8"),
        "branch":  OUTPUT_BRANCH
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

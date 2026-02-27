"""
sitemap_gen.py
Generate sitemap.xml dari semua file di branch output.
Dipanggil setelah setiap konten baru dipublish.
"""
import os
import sys
import re
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

ENGINE_REPO  = os.environ.get("ENGINE_REPO", "YOUR_USERNAME/ai-engine")
ENGINE_TOKEN = os.environ.get("GITHUB_TOKEN")
SITE_URL     = os.environ.get(
    "SITE_BASE_URL", "https://saas.blogtrick.eu.org"
)
OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {ENGINE_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-engine"
    }


def get_output_files() -> list:
    """
    Ambil daftar semua file di branch output.
    Return: list dict berisi info setiap file.
    """
    files = []
    for folder in ["articles", "tools"]:
        url = (
            f"{API_BASE}/repos/{ENGINE_REPO}/contents/"
            f"{folder}?ref={OUTPUT_BRANCH}"
        )
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req) as r:
                items = json.loads(r.read())
                for item in items:
                    name = item.get("name", "")
                    if name not in (".gitkeep", "README.md", ""):
                        files.append({
                            "path": item["path"],
                            "folder": folder,
                            "name": name
                        })
        except Exception as e:
            print(f"Could not list {folder}: {e}")
    return files


def file_to_url(folder: str, filename: str) -> str:
    """Convert nama file ke URL yang sesuai."""
    # Hapus ekstensi
    slug = filename.replace(".md", "").replace(".html", "")
    # Hapus prefix tanggal dari artikel (format: YYYY-MM-DD-slug)
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return f"{SITE_URL}/{folder}/{slug}"


def build_sitemap(files: list) -> str:
    """Build isi sitemap.xml dari daftar file."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url_entries = [f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""]

    for f in files:
        loc = file_to_url(f["folder"], f["name"])
        priority = "0.8" if f["folder"] == "tools" else "0.6"
        url_entries.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{priority}</priority>
  </url>""")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries)
        + "\n</urlset>"
    )


def publish_sitemap(content: str):
    """Publish sitemap.xml ke branch output."""
    url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/sitemap.xml"
    sha = None

    try:
        req = urllib.request.Request(
            f"{url}?ref={OUTPUT_BRANCH}",
            headers=_headers()
        )
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[sitemap] Update {datetime.utcnow().strftime('%Y-%m-%d')}",
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
    with urllib.request.urlopen(req) as r:
        print(f"Sitemap published: HTTP {r.status}")


if __name__ == "__main__":
    print("Generating sitemap...")
    files = get_output_files()
    print(f"Found {len(files)} files in output branch")
    sitemap = build_sitemap(files)
    publish_sitemap(sitemap)
    print("Done")

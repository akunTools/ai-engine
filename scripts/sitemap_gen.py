"""
sitemap_gen.py
Generate sitemap.xml dan index pages dari semua file di branch output.
Dipanggil setelah setiap konten baru dipublish.
"""
import os
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
                    if name not in (".gitkeep", "README.md",
                                    "index.html", ""):
                        files.append({
                            "path":   item["path"],
                            "folder": folder,
                            "name":   name
                        })
        except Exception as e:
            print(f"Could not list {folder}: {e}")
    return files


def file_to_slug(filename: str) -> str:
    """Hapus ekstensi dan prefix tanggal dari nama file."""
    slug = filename.replace(".md", "").replace(".html", "")
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug


def file_to_url(folder: str, filename: str) -> str:
    """Convert nama file ke URL publik."""
    return f"{SITE_URL}/{folder}/{file_to_slug(filename)}"


def slug_to_title(slug: str) -> str:
    """Convert slug ke judul yang readable."""
    return slug.replace("-", " ").title()


# ─────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────

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
        loc      = file_to_url(f["folder"], f["name"])
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


# ─────────────────────────────────────────────
# INDEX PAGES
# ─────────────────────────────────────────────

def build_articles_index(files: list) -> str:
    """Build articles/index.html dari daftar file artikel."""
    article_files = [f for f in files if f["folder"] == "articles"]
    # Urutkan terbaru dulu (nama file dimulai dengan tanggal)
    article_files.sort(key=lambda x: x["name"], reverse=True)

    items_html = ""
    for f in article_files:
        slug  = file_to_slug(f["name"])
        url   = f"{SITE_URL}/articles/{slug}"
        title = slug_to_title(slug)
        # Ambil tanggal dari nama file jika ada prefix tanggal
        date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', f["name"])
        date_str = date_match.group(1) if date_match else ""
        items_html += f"""
    <li class="item">
      <a href="{url}">{title}</a>
      {f'<span class="date">{date_str}</span>' if date_str else ''}
    </li>"""

    if not items_html:
        items_html = "\n    <li>No articles yet. Check back soon.</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Articles — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="Guides and analysis for bootstrapped SaaS founders.">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 680px; margin: 0 auto; padding: 32px 16px;
           color: #1e293b; line-height: 1.6; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 8px; }}
    .subtitle {{ color: #64748b; margin-bottom: 32px; }}
    ul {{ list-style: none; padding: 0; }}
    .item {{ border-bottom: 1px solid #e2e8f0; padding: 16px 0; }}
    .item a {{ font-size: 1.05rem; font-weight: 500; color: #0f172a;
               text-decoration: none; }}
    .item a:hover {{ color: #6366f1; }}
    .date {{ display: block; font-size: 0.8rem; color: #94a3b8;
             margin-top: 4px; }}
    .back {{ display: inline-block; margin-bottom: 24px; font-size: 0.9rem;
             color: #6366f1; text-decoration: none; }}
    .back:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <a href="/" class="back">← Home</a>
  <h1>Articles</h1>
  <p class="subtitle">Guides and analysis for bootstrapped SaaS founders.</p>
  <ul>{items_html}
  </ul>
</body>
</html>"""


def build_tools_index(files: list) -> str:
    """Build tools/index.html dari daftar file tools."""
    tool_files = [f for f in files if f["folder"] == "tools"]
    tool_files.sort(key=lambda x: x["name"])

    items_html = ""
    for f in tool_files:
        slug  = file_to_slug(f["name"])
        url   = f"{SITE_URL}/tools/{slug}"
        title = slug_to_title(slug)
        items_html += f"""
    <li class="item">
      <a href="{url}">{title}</a>
    </li>"""

    if not items_html:
        items_html = "\n    <li>No tools yet. Check back soon.</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tools — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="Free calculators for bootstrapped SaaS founders.">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 680px; margin: 0 auto; padding: 32px 16px;
           color: #1e293b; line-height: 1.6; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 8px; }}
    .subtitle {{ color: #64748b; margin-bottom: 32px; }}
    ul {{ list-style: none; padding: 0; }}
    .item {{ border-bottom: 1px solid #e2e8f0; padding: 16px 0; }}
    .item a {{ font-size: 1.05rem; font-weight: 500; color: #0f172a;
               text-decoration: none; }}
    .item a:hover {{ color: #6366f1; }}
    .back {{ display: inline-block; margin-bottom: 24px; font-size: 0.9rem;
             color: #6366f1; text-decoration: none; }}
    .back:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <a href="/" class="back">← Home</a>
  <h1>Tools</h1>
  <p class="subtitle">Free calculators built for bootstrapped SaaS founders.</p>
  <ul>{items_html}
  </ul>
</body>
</html>"""


# ─────────────────────────────────────────────
# PUBLISH HELPER
# ─────────────────────────────────────────────

def publish_file(path: str, content: str, label: str):
    """Publish satu file ke branch output."""
    url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"
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
        "message": f"[sitemap] {label} {datetime.utcnow().strftime('%Y-%m-%d')}",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
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
        print(f"{label} published: HTTP {r.status}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating sitemap and index pages...")
    files = get_output_files()
    print(f"Found {len(files)} content files in output branch")

    sitemap = build_sitemap(files)
    publish_file("sitemap.xml", sitemap, "Sitemap")

    articles_index = build_articles_index(files)
    publish_file("articles/index.html", articles_index, "Articles index")

    tools_index = build_tools_index(files)
    publish_file("tools/index.html", tools_index, "Tools index")

    print("Done")

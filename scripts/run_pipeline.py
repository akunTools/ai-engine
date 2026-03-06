"""
run_pipeline.py
Pipeline utama: ambil konten dari staging, wrap template,
publish ke output branch, update tracking files.
"""
import os
import re
import sys
import json
import base64
import urllib.request
from datetime import datetime

from loader    import fetch_file, fetch_json, update_file, list_folder, delete_file
from postprocess import wrap_article_html, wrap_tool_html
from publisher  import publish_html

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
TASK_TYPE     = os.environ.get("TASK_TYPE", "article")


def sync_manifest(staging_ready_path: str, manifest_path: str) -> tuple:
    """
    Sinkronisasi manifest dengan file aktual di staging.
    - File baru (tidak di manifest) → tambah ke akhir antrian
    - File yang sudah dihapus → hapus dari manifest
    - File yang dimodifikasi → posisi tidak berubah

    Return: (queue list, actual_files dict {filename: sha})
    """
    # Ambil file aktual
    actual_files_list = list_folder(staging_ready_path)
    actual_files = {f["name"]: f["sha"] for f in actual_files_list}

    # Ambil manifest
    try:
        manifest = fetch_json(manifest_path)
        queue = manifest.get("queue", [])
    except Exception:
        queue = []

    # Hapus entri untuk file yang sudah tidak ada
    queue = [e for e in queue if e["filename"] in actual_files]

    # Tambah file baru ke akhir antrian
    queued_names = {e["filename"] for e in queue}
    new_files = sorted(
        [f for f in actual_files if f not in queued_names]
    )
    for filename in new_files:
        queue.append({
            "filename": filename,
            "added_at": datetime.utcnow().isoformat()
        })

    # Simpan manifest yang sudah disinkron
    update_file(
        manifest_path,
        json.dumps({"queue": queue}, indent=2),
        "[pipeline] Sync manifest"
    )

    return queue, actual_files


def slug_from_filename(filename: str) -> str:
    """Konversi nama file ke slug URL."""
    slug = filename.replace(".html", "").replace(".md", "")
    # Hapus prefix tanggal jika ada (contoh: 2025-01-15-)
    slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
    return slug


def update_editorial_memory(slug: str, body_html: str,
                             content_type: str) -> None:
    """Update editorial_memory.json setelah konten dipublish."""
    try:
        memory = fetch_json("editorial_memory.json")
    except Exception:
        memory = {
            "last_updated": "",
            "published_articles": [],
            "published_tools": []
        }

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
             if h1_match else slug.replace("-", " ").title())

    entry = {
        "slug":           slug,
        "title":          title,
        "published_date": date_str
    }

    if content_type == "article":
        existing = {a["slug"] for a in memory.get("published_articles", [])}
        if slug not in existing:
            memory.setdefault("published_articles", []).append(entry)
    else:
        existing = {t["slug"] for t in memory.get("published_tools", [])}
        if slug not in existing:
            memory.setdefault("published_tools", []).append(entry)

    memory["last_updated"] = date_str

    update_file(
        "editorial_memory.json",
        json.dumps(memory, indent=2),
        f"[pipeline] Update editorial memory: {slug}"
    )
    print(f"Editorial memory updated: {slug}")


def update_tool_registry(slug: str, body_html: str) -> None:
    """Update tool_registry.json setelah tool dipublish."""
    try:
        registry = fetch_json("tool_registry.json")
    except Exception:
        registry = {"last_updated": "", "tools": []}

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
             if h1_match else slug.replace("-", " ").title())

    existing = {t.get("slug") for t in registry.get("tools", [])}
    if slug not in existing:
        registry.setdefault("tools", []).append({
            "slug":           slug,
            "title":          title,
            "published_date": date_str,
            "url":            f"/tools/{slug}"
        })
        registry["last_updated"] = date_str

        update_file(
            "tool_registry.json",
            json.dumps(registry, indent=2),
            f"[pipeline] Register tool: {slug}"
        )
        print(f"Tool registry updated: {slug}")


def extract_cluster(body_html: str) -> str:
    """Ekstrak cluster_id dari meta tag di body HTML staging."""
    match = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def update_content_index(slug: str, title: str, cluster_id: str,
                          content_type: str, date_str: str) -> None:
    """
    Update content-index.json di branch output ENGINE_REPO.
    File ini dibaca oleh JavaScript di setiap halaman untuk
    menampilkan Related Articles dan Related Tools secara otomatis.
    """
    path    = "content-index.json"
    api_url = f"https://api.github.com/repos/{ENGINE_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }

    # Baca content-index.json yang sudah ada
    sha   = None
    index = {"articles": [], "tools": []}
    try:
        req = urllib.request.Request(
            f"{api_url}?ref=output", headers=headers
        )
        with urllib.request.urlopen(req) as r:
            data    = json.loads(r.read())
            sha     = data.get("sha")
            raw     = base64.b64decode(data["content"]).decode("utf-8")
            index   = json.loads(raw)
    except Exception:
        pass  # File belum ada → mulai dari kosong

    # Tambah entry baru (skip jika slug sudah ada)
    key            = "articles" if content_type == "article" else "tools"
    existing_slugs = {e["slug"] for e in index.get(key, [])}
    if slug not in existing_slugs:
        index.setdefault(key, []).append({
            "slug":    slug,
            "title":   title,
            "cluster": cluster_id,
            "date":    date_str
        })

    # Simpan kembali ke branch output
    payload = {
        "message": f"[pipeline] Update content index: {slug}",
        "content": base64.b64encode(
            json.dumps(index, indent=2).encode("utf-8")
        ).decode("utf-8"),
        "branch":  "output"
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"Content index updated: {slug} (HTTP {r.status})")
    except Exception as e:
        print(f"Warning: Could not update content index: {e}")


def run_pipeline(task_type: str) -> None:
    is_article  = (task_type == "article")
    folder_type = "articles" if is_article else "tools"
    output_dir  = folder_type

    staging_ready = f"staging/{folder_type}/ready"
    manifest_path = f"staging/{folder_type}/manifest.json"

    print(f"Task type: {task_type}")
    print("Syncing manifest...")

    queue, actual_files = sync_manifest(staging_ready, manifest_path)

    if not queue:
        print(f"STAGING_EMPTY: No {folder_type} in staging/ready.")
        sys.exit(2)

    # Ambil item pertama dari antrian
    next_item = queue[0]
    filename  = next_item["filename"]
    file_sha  = actual_files[filename]
    slug      = slug_from_filename(filename)

    print(f"Publishing: {filename} → slug: {slug}")

    # Ambil body HTML dari staging
    body_html = fetch_file(f"{staging_ready}/{filename}")

    # Wrap dengan template
    if is_article:
        full_html = wrap_article_html(body_html, slug)
    else:
        full_html = wrap_tool_html(body_html, slug)

    # Publish ke branch output
    success = publish_html(output_dir, f"{slug}.html", full_html)
    if not success:
        print(f"PUBLISH_FAILED: Could not publish {slug}.html")
        sys.exit(1)

    print(f"Published successfully: {output_dir}/{slug}.html")

    # Hapus dari staging
    delete_file(
        f"{staging_ready}/{filename}",
        file_sha,
        f"[pipeline] Remove published: {filename}"
    )
    print(f"Removed from staging: {filename}")

    # Update tracking files
    update_editorial_memory(slug, body_html, task_type)
    if not is_article:
        update_tool_registry(slug, body_html)

    # Update content-index.json untuk related content otomatis
    h1_match   = re.search(r'<h1[^>]*>(.*?)</h1>', body_html,
                            re.IGNORECASE | re.DOTALL)
    page_title = (re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                  if h1_match else slug.replace("-", " ").title())
    cluster_id = extract_cluster(body_html)
    date_str   = datetime.utcnow().strftime("%Y-%m-%d")
    update_content_index(slug, page_title, cluster_id, task_type, date_str)

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    run_pipeline(TASK_TYPE)

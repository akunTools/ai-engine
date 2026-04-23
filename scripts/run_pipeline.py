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
import urllib.parse
from datetime import datetime

from loader    import fetch_file, fetch_json, update_file, list_folder, delete_file
from postprocess import wrap_article_html, wrap_tool_html
from publisher  import publish_html, publish_binary
from og_gen     import generate_og_image

ENGINE_REPO   = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
TASK_TYPE     = os.environ.get("TASK_TYPE", "article")
WORKER_URL    = os.environ.get("WORKER_URL", "").rstrip("/") + "/"
BRIEF_TOKEN   = os.environ.get("BRIEF_TOKEN", "")


def notify_keyword_done(slug: str) -> None:
    """
    Set status keyword ke DONE di keyword_stock.json via Worker.
    Lookup dilakukan berdasarkan slug (bukan keyword text) untuk
    menghindari mismatch jika user mengubah slug di BriefActivity.
    Non-fatal: jika gagal, sync_check akan jadi fallback.
    """
    if not WORKER_URL or not BRIEF_TOKEN:
        print("Warning: WORKER_URL atau BRIEF_TOKEN tidak di-set, skip update status keyword.")
        return
    try:
        params = urllib.parse.urlencode({"slug": slug, "status": "DONE"})
        url = f"{WORKER_URL}update_keyword?{params}"
        req = urllib.request.Request(
            url,
            headers={"X-Brief-Token": BRIEF_TOKEN, "User-Agent": "ai-engine"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = r.read().decode()
            print(f"Keyword status → DONE: {slug} (HTTP {r.status}, response: {resp})")
    except Exception as e:
        print(f"Warning: Gagal update status keyword (non-fatal, sync_check sebagai fallback): {e}")


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



def extract_cluster(body_html: str) -> str:
    """Ekstrak cluster_id dari meta tag di body HTML staging."""
    match = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def warm_facebook_cache(url: str) -> None:
    """
    Paksa Facebook crawl ulang OG meta tag untuk URL yang baru dipublish.
    Menggunakan Facebook Graph API publik — tidak butuh token atau akun developer.
    Non-fatal: jika gagal, pipeline tetap lanjut.
    Berlaku untuk semua platform yang pakai Facebook crawler (FB, Instagram link preview).
    """
    try:
        encoded = urllib.parse.quote(url, safe="")
        api_url = f"https://graph.facebook.com/?id={encoded}&scrape=true"
        req = urllib.request.Request(
            api_url,
            data=b"",
            method="POST",
            headers={"User-Agent": "ai-engine"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"Facebook cache warmed: {url} (HTTP {r.status})")
    except Exception as e:
        print(f"Warning: Facebook cache warm failed (non-fatal): {e}")


def update_content_index(slug: str, title: str, cluster_id: str,
                          content_type: str, date_str: str,
                          excerpt: str = "") -> None:
    """
    Update content-index.json di branch output ENGINE_REPO.
    File ini dibaca oleh JavaScript di setiap halaman untuk
    menampilkan Related Articles dan Related Tools secara otomatis.
    Field excerpt digunakan oleh sitemap_gen.py untuk menampilkan
    deskripsi singkat di artikel list (homepage dan articles index).
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
            "date":    date_str,
            "excerpt": excerpt
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
        # Tulis flag agar workflow bisa membedakan staging kosong vs error
        open("/tmp/staging_empty", "w").close()
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
    notify_keyword_done(slug)
    update_editorial_memory(slug, body_html, task_type)
    
    # Update content-index.json untuk related content otomatis
    h1_match   = re.search(r'<h1[^>]*>(.*?)</h1>', body_html,
                            re.IGNORECASE | re.DOTALL)
    page_title = (re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
                  if h1_match else slug.replace("-", " ").title())
    cluster_id = extract_cluster(body_html)
    date_str   = datetime.utcnow().strftime("%Y-%m-%d")

    # Ekstrak excerpt dari meta description (diisi Claude saat authoring)
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    excerpt = desc_match.group(1).strip() if desc_match else ""

    update_content_index(slug, page_title, cluster_id, task_type, date_str,
                         excerpt)

    # Generate dan publish OG image (hanya untuk artikel)
    # Ditempatkan di sini karena page_title sudah tersedia
    if is_article:
        try:
            og_path = generate_og_image(page_title, slug, "/tmp/og")
            with open(og_path, "rb") as f:
                og_data = f.read()
            og_ok = publish_binary("og", f"{slug}.png", og_data)
            if og_ok:
                print(f"OG image published: og/{slug}.png")
                warm_facebook_cache(
                    f"https://saas.blogtrick.eu.org/articles/{slug}"
                )
            else:
                print(f"Warning: OG image publish failed (non-fatal)")
        except Exception as e:
            print(f"Warning: OG image generation failed (non-fatal): {e}")

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    run_pipeline(TASK_TYPE)

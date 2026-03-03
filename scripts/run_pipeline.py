"""
run_pipeline.py
Pipeline publish konten dari staging/ready/.

CARA KERJA:
1. Baca manifest.json (antrian berurutan)
2. Sync manifest dengan file aktual di ready/:
   - File baru → tambah ke akhir antrian
   - File terhapus → hapus dari antrian
   - File dimodifikasi → posisi antrian tidak berubah
3. Publish file pertama di antrian
4. Hapus file dari staging setelah berhasil
5. Update editorial_memory.json otomatis

FORMAT FILE DI STAGING:
- Artikel : body HTML saja (mulai dari <h1>)
- Tools   : body HTML saja (gunakan CSS classes dari postprocess.py)
"""
import os
import sys
import re
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from loader import (
    list_folder, fetch_json, update_file,
    delete_file, write_log
)
from postprocess import wrap_article_html, wrap_tool_html
from publisher import publish
import sitemap_gen


# ─────────────────────────────────────────────
# MANIFEST
# ─────────────────────────────────────────────

def sync_manifest(staging_ready: str, manifest_path: str) -> tuple:
    """
    Sync manifest dengan file aktual di staging/ready.

    Return: (queue, actual_files)
      queue        : list of dict {filename, added_at} — urut terbit
      actual_files : dict {filename: {name, path, sha}}
    """
    # Ambil file aktual di folder ready
    actual_files = {
        f["name"]: f
        for f in list_folder(staging_ready)
        if f["name"].endswith(".html")
    }

    # Baca manifest yang ada
    try:
        manifest = fetch_json(manifest_path)
        queue = manifest.get("queue", [])
    except Exception:
        queue = []

    # Hapus dari antrian jika file sudah tidak ada (terhapus)
    queue = [item for item in queue
             if item["filename"] in actual_files]

    # Tambah file baru ke akhir antrian
    # File baru = ada di actual_files tapi belum ada di queue
    # Urut alfabetis untuk konsistensi saat banyak file baru sekaligus
    # (gunakan prefix 01-, 02-, dst jika ingin kontrol urutan spesifik)
    existing = {item["filename"] for item in queue}
    for filename in sorted(actual_files.keys()):
        if filename not in existing:
            queue.append({
                "filename": filename,
                "added_at": datetime.utcnow().isoformat()
            })

    # Simpan manifest yang sudah disync
    update_file(
        manifest_path,
        json.dumps({"queue": queue}, indent=2),
        "[pipeline] Sync manifest"
    )

    return queue, actual_files


# ─────────────────────────────────────────────
# EDITORIAL MEMORY
# ─────────────────────────────────────────────

def update_editorial_memory(slug: str, body_html: str,
                             content_type: str) -> None:
    """
    Tambah entry ke editorial_memory.json setelah konten dipublish.
    Dijalankan otomatis — tidak perlu update manual.

    content_type: 'articles' atau 'tools'
    """
    try:
        memory = fetch_json("editorial_memory.json")
    except Exception:
        memory = {
            "last_updated":      "",
            "published_articles": [],
            "published_tools":    []
        }

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Ekstrak judul dari <h1>
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
             if h1_match else slug.replace("-", " ").title())

    entry = {
        "slug":           slug,
        "title":          title,
        "published_date": date_str
    }

    if content_type == "articles":
        existing = {a.get("slug") for a in
                    memory.get("published_articles", [])}
        if slug not in existing:
            memory.setdefault("published_articles", []).append(entry)
    else:
        existing = {t.get("slug") for t in
                    memory.get("published_tools", [])}
        if slug not in existing:
            memory.setdefault("published_tools", []).append(entry)

    memory["last_updated"] = date_str

    update_file(
        "editorial_memory.json",
        json.dumps(memory, indent=2),
        f"[pipeline] Add to editorial memory: {slug}"
    )
    print(f"Editorial memory updated: {slug}")


# ─────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────

def refresh_sitemap(output_folder: str) -> None:
    """Update sitemap.xml dan halaman index setelah publish."""
    try:
        files = sitemap_gen.get_output_files()
        sitemap_gen.publish_file(
            "sitemap.xml",
            sitemap_gen.build_sitemap(files),
            "Sitemap"
        )
        if output_folder == "articles":
            sitemap_gen.publish_file(
                "articles/index.html",
                sitemap_gen.build_articles_index(files),
                "Articles index"
            )
        else:
            sitemap_gen.publish_file(
                "tools/index.html",
                sitemap_gen.build_tools_index(files),
                "Tools index"
            )
        print("Sitemap and index updated")
    except Exception as e:
        # Jangan gagalkan pipeline hanya karena sitemap error
        print(f"Warning: sitemap update failed: {e}")


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(task_type: str) -> dict:
    """
    Ambil file pertama dari antrian dan publish ke branch output.

    task_type: 'article' atau 'calculator_tool'
    """
    if task_type == "article":
        staging_ready   = "staging/articles/ready"
        manifest_path   = "staging/articles/manifest.json"
        output_folder   = "articles"
        is_article      = True
    elif task_type == "calculator_tool":
        staging_ready   = "staging/tools/ready"
        manifest_path   = "staging/tools/manifest.json"
        output_folder   = "tools"
        is_article      = False
    else:
        print(f"Unknown task_type: {task_type}")
        sys.exit(1)

    print(f"\n=== PIPELINE: {task_type.upper()} ===")
    print(f"Staging folder : {staging_ready}")

    # Sync manifest dengan file aktual
    queue, actual_files = sync_manifest(staging_ready, manifest_path)

    if not queue:
        print("Staging is empty. Nothing to publish.")
        with open("/tmp/queue_empty.flag", "w") as f:
            f.write(task_type)
        return {"success": False, "issues": [f"Staging empty: {staging_ready}"]}

    # Ambil file pertama dari antrian
    next_item = queue[0]
    filename  = next_item["filename"]
    file_info = actual_files[filename]

    # Slug = nama file tanpa ekstensi, tanpa prefix angka opsional
    slug = re.sub(r'^\d+-', '', filename.replace(".html", ""))

    print(f"Publishing     : {filename}")
    print(f"Slug           : {slug}")
    print(f"Queued at      : {next_item.get('added_at', 'unknown')}")
    print(f"Remaining      : {len(queue) - 1} file(s) in staging")

    # Ambil body HTML dari staging
    from loader import fetch_file
    body_html = fetch_file(file_info["path"])

    # Wrap body ke full HTML page
    if is_article:
        print("Applying article template...")
        final_html      = wrap_article_html(body_html, slug)
        output_filename = f"{slug}.html"
    else:
        print("Applying tool template...")
        final_html      = wrap_tool_html(body_html, slug)
        output_filename = f"{slug}.html"

    # Publish ke branch output
    success = publish(output_filename, final_html, output_folder)

    if success:
        print(f"Published: {output_folder}/{output_filename}")

        # Hapus file dari staging
        delete_file(
            file_info["path"],
            file_info["sha"],
            f"[staging] Published: {filename}"
        )
        print(f"Removed from staging: {filename}")

        # Update editorial_memory otomatis
        update_editorial_memory(slug, body_html, output_folder)

        # Update sitemap dan index
        refresh_sitemap(output_folder)

        return {
            "success":  True,
            "filename": output_filename,
            "slug":     slug
        }
    else:
        return {"success": False, "issues": ["Publishing failed"]}


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

def main():
    print(f"Pipeline started at {datetime.utcnow().isoformat()}")

    task_type = os.environ.get("TASK_TYPE", "article")
    date_str  = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        result   = run_pipeline(task_type)
        is_empty = "Staging empty" in str(result.get("issues", []))

        # Log hanya jika bukan sekadar staging kosong
        if not is_empty:
            write_log(date_str, {
                "timestamp": datetime.utcnow().isoformat(),
                "task_type": task_type,
                "result":    result
            }, "success" if result.get("success") else "failures")

        if result.get("success"):
            print(f"\nSUCCESS: {result.get('filename')}")
        elif is_empty:
            print("\nStaging is empty — nothing to publish.")
        else:
            print(f"\nFAILED: {result.get('issues')}")
            with open("/tmp/pipeline_error.log", "w") as f:
                f.write(str(result.get("issues")))
            sys.exit(1)

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\nUnexpected error:\n{error_msg}")
        with open("/tmp/pipeline_error.log", "w") as f:
            f.write(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()

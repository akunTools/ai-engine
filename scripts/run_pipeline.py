"""
run_pipeline.py
Pipeline publish konten dari staging.
Tidak lagi memanggil AI — hanya mengambil HTML dari
folder staging/ di ai-brain dan mempublishnya ke branch output.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from loader import list_folder, fetch_file, delete_file, write_log
from publisher import publish
import sitemap_gen


def _update_sitemap_and_index(content_type: str):
    """Update sitemap.xml dan halaman index setelah publish."""
    try:
        files = sitemap_gen.get_output_files()
        sitemap_gen.publish_file(
            "sitemap.xml",
            sitemap_gen.build_sitemap(files),
            "Sitemap"
        )
        if content_type == "articles":
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
        print(f"Warning: sitemap update failed: {e}")


def run_pipeline(task_type: str) -> dict:
    """
    Ambil file pertama dari staging dan publish.
    task_type: 'article' atau 'calculator_tool'
    """
    # Tentukan folder staging dan folder output berdasarkan task_type
    if task_type == "article":
        staging_folder = "staging/articles"
        output_folder  = "articles"
    elif task_type == "calculator_tool":
        staging_folder = "staging/tools"
        output_folder  = "tools"
    else:
        print(f"Unknown task_type: {task_type}")
        sys.exit(1)

    print(f"\n=== PIPELINE: {task_type.upper()} ===")
    print(f"Checking staging folder: {staging_folder}")

    # Ambil daftar file di staging
    files = list_folder(staging_folder)

    # Filter: hanya .html, urutkan dari yang paling lama (nama = tanggal)
    html_files = sorted(
        [f for f in files if f["name"].endswith(".html")],
        key=lambda x: x["name"]
    )

    if not html_files:
        print(f"Staging is empty. No {task_type} to publish.")
        with open("/tmp/queue_empty.flag", "w") as f:
            f.write(task_type)
        return {
            "success": False,
            "issues": [f"Staging empty: {staging_folder}"]
        }

    # Ambil file pertama (paling lama menunggu)
    target   = html_files[0]
    filename = target["name"]
    print(f"Publishing: {filename}")
    print(f"Remaining in staging after this: {len(html_files) - 1}")

    # Ambil isi HTML
    content = fetch_file(target["path"])
    print(f"File size: {len(content)} chars")

    # Publish ke branch output
    success = publish(filename, content, output_folder)

    if success:
        print(f"Published successfully: {output_folder}/{filename}")

        # Hapus dari staging
        delete_file(
            target["path"],
            target["sha"],
            f"[staging] Published: {filename}"
        )
        print(f"Removed from staging: {filename}")

        # Update sitemap dan index
        _update_sitemap_and_index(output_folder)

        return {"success": True, "filename": filename}
    else:
        return {"success": False, "issues": ["Publishing failed"]}


def main():
    print(f"Pipeline started at {datetime.utcnow().isoformat()}")

    task_type = os.environ.get("TASK_TYPE", "article")
    date_str  = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        result = run_pipeline(task_type)

        # Tulis log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": task_type,
            "result":    result
        }
        log_status = "success" if result.get("success") else "failures"

        # Jangan log "staging kosong" sebagai failure
        is_empty = "Staging empty" in str(result.get("issues", []))
        if not is_empty:
            write_log(date_str, log_entry, log_status)

        if result.get("success"):
            print(f"\nPipeline SUCCESS: {result.get('filename')}")
        elif is_empty:
            print("\nStaging is empty — nothing to publish.")
        else:
            print(f"\nPipeline FAILED: {result.get('issues')}")
            # Simpan error untuk email notifikasi
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

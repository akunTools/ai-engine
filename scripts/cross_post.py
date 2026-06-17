"""
cross_post.py
Cross-post artikel ke Dev.to dengan canonical URL.
Tools (kalkulator) tidak di-cross-post.
Hashnode dihapus — API berbayar (wajib Pro) per 2026.

Usage: python scripts/cross_post.py articles <slug>
"""
import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

# ── Environment ───────────────────────────────────────────────────────────────
ENGINE_REPO    = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
SITE_URL       = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")
DEV_TO_KEY     = os.environ.get("DEV_TO_API_KEY", "")
OUTPUT_BRANCH  = "output"
API_BASE       = "https://api.github.com"

# Tag tetap untuk semua artikel (relevan untuk niche SaaS metrics)
ARTICLE_TAGS = ["saas", "startup", "metrics", "bootstrapped"]

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def fetch_article_html(slug: str) -> str:
    """Fetch HTML artikel dari output branch."""
    path = f"articles/{slug}.html"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
    req  = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return base64.b64decode(data["content"]).decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gagal fetch {path}: HTTP {e.code}")


def check_already_posted(slug: str) -> dict | None:
    """Return tracking data jika artikel sudah pernah di-cross-post, None jika belum."""
    path = f"cross_posts/{slug}.json"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
    req  = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except Exception:
        return None


def save_tracking(slug: str, results: dict) -> None:
    """Simpan tracking cross_posts/{slug}.json ke output branch."""
    path    = f"cross_posts/{slug}.json"
    api_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}"

    sha = None
    try:
        req = urllib.request.Request(
            f"{api_url}?ref={OUTPUT_BRANCH}", headers=_gh_headers()
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass

    payload = {
        "message": f"[cross-post] Tracking for {slug}",
        "content": base64.b64encode(
            json.dumps(results, indent=2, ensure_ascii=False).encode()
        ).decode(),
        "branch": OUTPUT_BRANCH
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={**_gh_headers(), "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"    Tracking saved: HTTP {r.status}")


# ── Content extraction ─────────────────────────────────────────────────────────

def extract_meta(html: str) -> dict:
    """Ambil title, description, dan cluster dari HTML."""
    title_m   = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    desc_m    = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    cluster_m = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    title = title_m.group(1).strip() if title_m else ""
    title = re.sub(r'\s*[—\-]\s*SaaS Tools.*$', '', title).strip()
    desc  = desc_m.group(1).strip() if desc_m else ""
    cluster = cluster_m.group(1).strip() if cluster_m else ""
    return {"title": title, "description": desc, "cluster": cluster}


def extract_article_body(html: str) -> str:
    """Ambil isi <article> saja, strip navigation dan footer."""
    m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else html


def fix_markdown_formatting(md: str) -> str:
    """
    Perbaiki formatting Markdown dari html2text.
    1. Perbaiki penomoran ganda: '  1. 1' → '  1.'
    2. Perbaiki spacing berlebih pada list items.
    """
    # Fix duplicate numbering from nested lists: "  1. 1" → "  1."
    md = re.sub(r'^(\s*)(\d+)\. \d+\.\s*', r'\1\2. ', md, flags=re.MULTILINE)
    
    # Fix jika ada "1. 1. 1" (tiga level) → "1."
    md = re.sub(r'^(\s*)(\d+)\. \d+\. \d+\.\s*', r'\1\2. ', md, flags=re.MULTILINE)
    
    # Hapus spasi berlebih di dalam list item
    md = re.sub(r'^(\s*)(\d+)\.  ', r'\1\2. ', md, flags=re.MULTILINE)
    
    return md


def html_to_markdown(html: str, base_url: str) -> str:
    """
    Konversi HTML ke Markdown menggunakan html2text.
    Semua link relatif diubah menjadi absolut terlebih dahulu.
    """
    import html2text
    
    # Ubah link relatif menjadi absolut
    def make_abs(match):
        href = match.group(1)
        if href.startswith('/') and not href.startswith('//'):
            return f'href="{base_url}{href}"'
        return match.group(0)
    
    # Cari semua href="..." dan ubah yang relatif
    html = re.sub(r'href="([^"]*)"', make_abs, html)
    # Juga handle href='...' (single quote)
    html = re.sub(r"href='([^']*)'", make_abs, html)
    
    h = html2text.HTML2Text()
    h.ignore_links   = False
    h.ignore_images  = True
    h.body_width     = 0
    h.protect_links  = True
    h.wrap_links     = False
    h.ignore_tables  = False
    
    md = h.handle(html).strip()
    
    # Post-process: perbaiki formatting markdown
    md = fix_markdown_formatting(md)
    
    return md


# ── Dev.to ─────────────────────────────────────────────────────────────────────

def post_to_devto(title: str, markdown: str, canonical_url: str,
                  description: str) -> dict:
    """
    Publish artikel ke Dev.to via REST API.
    canonical_url → link kembali ke saastools.corenk.com.
    """
    if not DEV_TO_KEY:
        print("    SKIP Dev.to: DEV_TO_API_KEY tidak di-set")
        return {"skipped": True, "reason": "missing_key"}

    # Dev.to menerima Markdown murni di body_markdown
    # Tambah disclaimer di awal agar reader tahu ini cross-post
    body = (
        f"*This article was originally published at [{canonical_url}]({canonical_url})*\n\n"
        + markdown
    )

    payload = {
        "article": {
            "title":         title,
            "body_markdown": body,
            "published":     True,
            "canonical_url": canonical_url,
            "description":   description[:160] if description else "",
            "tags":          ARTICLE_TAGS
        }
    }

    req = urllib.request.Request(
        "https://dev.to/api/articles",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key":      DEV_TO_KEY,
            "Content-Type": "application/json",
            "User-Agent":   "ai-engine"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            url    = result.get("url", "")
            print(f"    Dev.to posted: {url}")
            return {"url": url, "id": result.get("id")}
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")
        raise RuntimeError(f"Dev.to API {e.code}: {err[:300]}")


# Hashnode dihapus — API berbayar (wajib Pro) per 2026.


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/cross_post.py articles <slug>")
        sys.exit(1)

    folder = sys.argv[1]
    slug   = sys.argv[2]

    if folder != "articles":
        print(f"INFO: cross-posting hanya untuk articles, bukan '{folder}' — skip")
        sys.exit(0)

    # Validasi env
    missing = [k for k, v in {
        "ENGINE_REPO":  ENGINE_REPO,
        "GITHUB_TOKEN": GITHUB_TOKEN
    }.items() if not v]
    if missing:
        print(f"FATAL: Env tidak di-set: {', '.join(missing)}")
        sys.exit(1)

    canonical_url = f"{SITE_URL}/articles/{slug}"
    print(f"[cross_post] {slug}")
    print(f"    Canonical URL: {canonical_url}")

    # 1. Cek apakah sudah pernah di-cross-post
    existing = check_already_posted(slug)
    if existing:
        print(f"    Already cross-posted — skip")
        print(f"    Dev.to: {existing.get('devto', {}).get('url', 'n/a')}")
        sys.exit(0)

    # 2. Fetch HTML
    print("1/3 Fetch article HTML...")
    html = fetch_article_html(slug)
    print(f"    Fetched: {len(html):,} chars")

    # 3. Convert ke Markdown
    print("2/3 Convert HTML → Markdown...")
    meta    = extract_meta(html)
    body    = extract_article_body(html)
    md      = html_to_markdown(body, SITE_URL)
    print(f"    Markdown: {len(md):,} chars | Title: {meta['title'][:60]}")

    # 4. Cross-post ke Dev.to
    results = {
        "slug":          slug,
        "canonical_url": canonical_url,
        "title":         meta["title"],
        "posted_at":     datetime.utcnow().isoformat() + "Z",
        "devto":         {}
    }

    print("3/3 Post to Dev.to...")
    try:
        results["devto"] = post_to_devto(
            meta["title"], md, canonical_url, meta["description"]
        )
    except Exception as e:
        print(f"    WARNING: Dev.to failed: {e}")
        results["devto"] = {"error": str(e)}

    # 5. Simpan tracking (selalu, meski gagal)
    print("Saving tracking file...")
    save_tracking(slug, results)

    print(f"\n✓ Done: {slug}")
    print(f"  Dev.to: {results['devto'].get('url', results['devto'].get('error', 'skipped'))}")


if __name__ == "__main__":
    main()
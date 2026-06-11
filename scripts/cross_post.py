"""
cross_post.py
Cross-post artikel ke Dev.to dan Hashnode dengan canonical URL.
Tools (kalkulator) tidak di-cross-post.

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
HASHNODE_KEY   = os.environ.get("HASHNODE_API_KEY", "")
HASHNODE_PUB   = os.environ.get("HASHNODE_PUBLICATION_ID", "")
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


def html_to_markdown(html: str) -> str:
    """
    Konversi HTML ke Markdown menggunakan html2text.
    Dipanggil setelah extract_article_body.
    """
    import html2text
    h = html2text.HTML2Text()
    h.ignore_links   = False
    h.ignore_images  = True   # gambar OG tidak akan tersedia di platform lain
    h.body_width     = 0      # jangan wrap baris
    h.protect_links  = True
    h.wrap_links     = False
    h.ignore_tables  = False
    return h.handle(html).strip()


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


# ── Hashnode ───────────────────────────────────────────────────────────────────

def post_to_hashnode(title: str, markdown: str, canonical_url: str,
                     description: str) -> dict:
    """
    Publish artikel ke Hashnode via GraphQL API.
    canonical_url → link kembali ke saastools.corenk.com.
    """
    if not HASHNODE_KEY:
        print("    SKIP Hashnode: HASHNODE_API_KEY tidak di-set")
        return {"skipped": True, "reason": "missing_key"}
    if not HASHNODE_PUB:
        print("    SKIP Hashnode: HASHNODE_PUBLICATION_ID tidak di-set")
        return {"skipped": True, "reason": "missing_pub_id"}

    # Tambah disclaimer cross-post
    body = (
        f"*This article was originally published at [{canonical_url}]({canonical_url})*\n\n"
        + markdown
    )

    mutation = """
mutation PublishPost($input: PublishPostInput!) {
  publishPost(input: $input) {
    post {
      id
      slug
      url
    }
  }
}"""

    variables = {
        "input": {
            "title":          title,
            "contentMarkdown": body,
            "publicationId":  HASHNODE_PUB,
            "canonicalUrl":   canonical_url,
            "subtitle":       description[:250] if description else "",
            "tags":           []   # Hashnode v2: tags opsional, bisa dikosongkan
        }
    }

    payload = json.dumps({"query": mutation, "variables": variables}).encode("utf-8")

    req = urllib.request.Request(
        "https://gql.hashnode.com",           # ← hapus trailing slash
        data=payload,
        headers={
            "Authorization": f"Bearer {HASHNODE_KEY}",  # ← tambah Bearer
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "User-Agent":    "Mozilla/5.0 (compatible; ai-engine/1.0)"
        },
        method="POST"
    )

    # Jangan follow redirect — kalau ada redirect, berarti auth gagal
    # atau endpoint berubah. Laporkan URL tujuan redirect untuk debug.
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError(
                f"Hashnode redirect HTTP {code} → {newurl}. "
                "Kemungkinan: API key tidak valid atau endpoint berubah."
            )

    opener = urllib.request.build_opener(_NoRedirect())

    try:
        with opener.open(req, timeout=60) as r:
            status = r.status
            raw    = r.read()
    except RuntimeError:
        raise
    except urllib.error.HTTPError as e:
        status  = e.code
        raw     = e.read()
        snippet = raw.decode(errors="replace")[:400]
        raise RuntimeError(f"Hashnode HTTP {status}: {snippet}")
        
    if not raw or not raw.strip():
        raise RuntimeError(
            f"Hashnode empty response (HTTP {status}). "
            "Cek: (1) HASHNODE_PUBLICATION_ID — harus 24-char hex dari blog Settings, "
            "(2) API key punya permission Write di Hashnode Settings > Developer."
        )

    try:
        result = json.loads(raw)
    except Exception:
        snippet = raw.decode(errors="replace")[:300]
        raise RuntimeError(f"Hashnode response bukan JSON (HTTP {status}): {snippet}")

    if "errors" in result and result["errors"]:
        raise RuntimeError(f"Hashnode GraphQL errors: {json.dumps(result['errors'])[:400]}")

    post_data = result.get("data", {}).get("publishPost", {}).get("post", {})
    url       = post_data.get("url", "")
    print(f"    Hashnode posted: {url}")
    return {"url": url, "id": post_data.get("id")}


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
        print(f"    Dev.to:   {existing.get('devto', {}).get('url', 'n/a')}")
        print(f"    Hashnode: {existing.get('hashnode', {}).get('url', 'n/a')}")
        sys.exit(0)

    # 2. Fetch HTML
    print("1/4 Fetch article HTML...")
    html = fetch_article_html(slug)
    print(f"    Fetched: {len(html):,} chars")

    # 3. Convert ke Markdown
    print("2/4 Convert HTML → Markdown...")
    meta    = extract_meta(html)
    body    = extract_article_body(html)
    md      = html_to_markdown(body)
    print(f"    Markdown: {len(md):,} chars | Title: {meta['title'][:60]}")

    # 4. Cross-post
    results = {
        "slug":         slug,
        "canonical_url": canonical_url,
        "title":        meta["title"],
        "posted_at":    datetime.utcnow().isoformat() + "Z",
        "devto":        {},
        "hashnode":     {}
    }

    print("3/4 Post to Dev.to...")
    try:
        results["devto"] = post_to_devto(
            meta["title"], md, canonical_url, meta["description"]
        )
    except Exception as e:
        print(f"    WARNING: Dev.to failed: {e}")
        results["devto"] = {"error": str(e)}

    print("4/4 Post to Hashnode...")
    try:
        results["hashnode"] = post_to_hashnode(
            meta["title"], md, canonical_url, meta["description"]
        )
    except Exception as e:
        print(f"    WARNING: Hashnode failed: {e}")
        results["hashnode"] = {"error": str(e)}

    # 5. Simpan tracking (selalu, meski ada yang gagal)
    print("Saving tracking file...")
    save_tracking(slug, results)

    print(f"\n✓ Done: {slug}")
    print(f"  Dev.to:   {results['devto'].get('url', results['devto'].get('error', 'skipped'))}")
    print(f"  Hashnode: {results['hashnode'].get('url', results['hashnode'].get('error', 'skipped'))}")


if __name__ == "__main__":
    main()

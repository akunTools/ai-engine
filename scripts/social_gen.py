"""
social_gen.py
Generate social media posts dari artikel/tool yang baru dipublish,
lalu post ke Twitter/X via Official API v2 (OAuth 1.0a).

Pola AI call identik dengan auto_generate.py:
  Model priority : gpt-oss-120b:free → llama-3.3-70b:free → hermes-3-405b:free → deepseek-v4-pro (jika key tersedia)
  Platform post  : Bluesky (AT Protocol) · Mastodon (ActivityPub)
                   Twitter/X dihapus — write API berbayar $0.20/post sejak April 2026.
                   LinkedIn dihapus — Company Page creation diblokir (waitlist verifikasi).

Usage: python scripts/social_gen.py <folder> <slug>
  folder : articles | tools
  slug   : slug artikel (tanpa .html, tanpa date prefix)
"""
import os
import re
import sys
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# ── Environment ───────────────────────────────────────────────────────────────
ENGINE_REPO    = os.environ.get("ENGINE_REPO", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
SITE_URL       = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")

# ── Bluesky (AT Protocol — gratis, App Password) ──────────────────────────────
# Setup: bsky.social → Settings → Privacy and Security → App Passwords → Add App Password
# GitHub secret: BSKY_HANDLE (contoh: myaccount.bsky.social), BSKY_APP_PASSWORD
BSKY_HANDLE       = os.environ.get("BSKY_HANDLE", "")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD", "")

# ── Mastodon (ActivityPub — gratis, instance token) ───────────────────────────
# Setup: mastodon.social → Preferences → Development → New Application
#        Scope yang perlu: write:statuses → ambil "Your access token"
# GitHub secret: MASTODON_INSTANCE (contoh: mastodon.social), MASTODON_ACCESS_TOKEN
MASTODON_INSTANCE     = os.environ.get("MASTODON_INSTANCE", "")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN", "")

# LinkedIn dihapus dari scope:
# Company Page creation diblokir LinkedIn (waitlist verifikasi workplace, tanpa ETA).

OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"

# ── AI endpoints & model priority ────────────────────────────────────────────
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
DS_URL = "https://api.deepseek.com/v1/chat/completions"

# Model priority untuk social post (max_tokens=700, task sederhana):
#   1. openai/gpt-oss-120b:free     — instruction following 8.71/10, writing 7.91/10
#   2. meta-llama/llama-3.3-70b:free — dense 70B, reliable untuk short-form
#   3. hermes-3-llama-3.1-405b:free  — dense 405B, fallback kuat
#   4. deepseek-v4-pro               — paid, last resort jika semua free rate-limited
# Secret wajib: OPENROUTER_API_KEY (GitHub Actions secret)
# Secret opsional: DEEPSEEK_API_KEY (GitHub Actions secret, aktifkan entry ke-4)
MODELS = [
    {"model": "openai/gpt-oss-120b:free",                  "url": OR_URL, "key": OPENROUTER_KEY},
    {"model": "meta-llama/llama-3.3-70b-instruct:free",    "url": OR_URL, "key": OPENROUTER_KEY},
    {"model": "nousresearch/hermes-3-llama-3.1-405b:free", "url": OR_URL, "key": OPENROUTER_KEY},
]
if DEEPSEEK_KEY:
    MODELS.append(
        {"model": "deepseek-v4-pro", "url": DS_URL, "key": DEEPSEEK_KEY}
    )

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def fetch_article_html(folder: str, slug: str) -> str:
    """
    Fetch HTML dari output branch.
    Publisher menulis file tanpa date prefix: articles/slug.html
    """
    path = f"{folder}/{slug}.html"
    url  = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
    req  = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return base64.b64decode(data["content"]).decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gagal fetch {path}: HTTP {e.code}")


def save_social_post(slug: str, posts: dict) -> None:
    """Simpan generated posts ke social_posts/{slug}.json di output branch."""
    path    = f"social_posts/{slug}.json"
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
        "message": f"[social] Generated posts for {slug}",
        "content": base64.b64encode(
            json.dumps(posts, indent=2, ensure_ascii=False).encode()
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
        print(f"Social post saved: HTTP {r.status}")


# ── Content extraction ─────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()


def extract_meta(html: str) -> dict:
    title_m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    desc_m  = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    title = title_m.group(1).strip() if title_m else ""
    title = re.sub(r'\s*[—\-]\s*SaaS Tools.*$', '', title).strip()
    desc  = desc_m.group(1).strip() if desc_m else ""
    return {"title": title, "description": desc}


# ── AI call — identik pola dengan auto_generate.py ────────────────────────────

def _should_fallback(code: int, body: str) -> bool:
    """
    Identik dengan auto_generate.py:
    Fallback hanya untuk error yang memang bisa diselesaikan dengan ganti model.

    Fallback jika:
    - 404 → model tidak tersedia di OpenRouter. Endpoint OR di-hardcode, sehingga
            404 selalu berarti model routing failure (bukan URL salah).
            Contoh pesan: "No endpoints found", "unavailable for free"
    - 429 + "upstream" → rate limit di sisi provider, bukan akun kita

    Tidak fallback jika:
    - 401 → API key salah (semua model akan sama-sama gagal)
    - 429 tanpa "upstream" → limit akun kita sendiri
    - 500, 503 → server error, retry bukan fallback yang tepat
    """
    if code == 404:
        return True
    if code == 429 and "upstream" in body.lower():
        return True
    return False


def call_ai(messages: list, label: str = "") -> str:
    """
    Kirim messages ke AI dengan fallback antar model.
    Identik polanya dengan call_openrouter() di auto_generate.py.
    """
    tag        = f" ({label})" if label else ""
    last_error = None

    for entry in MODELS:
        model = entry["model"]
        url   = entry["url"]
        key   = entry["key"]

        if not key:
            print(f"    Skip {model}: key tidak tersedia.")
            continue

        payload = json.dumps({
            "model":      model,
            "messages":   messages,
            "max_tokens": 700,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  SITE_URL,
                "X-Title":       "SaaS Tools Content Engine",
                "User-Agent":    "ai-engine",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if _should_fallback(e.code, body):
                reason = "No endpoints" if e.code == 404 else "upstream rate-limit"
                print(f"    Warning: {model} tidak tersedia ({reason}), coba fallback...")
                last_error = f"HTTP {e.code}{tag} [{model}]: {body[:200]}"
                continue
            raise Exception(f"AI API HTTP {e.code}{tag} [{model}]: {body[:400]}")

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            raise Exception(
                f"Response format tidak terduga{tag} [{model}]: {e}. "
                f"Response: {str(data)[:300]}"
            )

        if not content:
            raise Exception(f"AI mengembalikan konten kosong{tag} [{model}].")

        print(f"    Model dipakai: {model}")
        return content

    raise Exception(
        f"Semua model tidak tersedia{tag}. "
        f"Error terakhir: {last_error}"
    )


# ── Social post generation ─────────────────────────────────────────────────────

def generate_social_posts(folder: str, slug: str, html: str) -> dict:
    """Generate Twitter + LinkedIn post via AI."""
    article_url  = f"{SITE_URL}/{folder}/{slug}"
    content_type = "calculator tool" if folder == "tools" else "article"
    meta         = extract_meta(html)
    plain_text   = strip_html(html)[:3500]

    prompt = f"""You are a copywriter for SaaS metrics content.
Target audience: bootstrapped founders who are busy, data-driven, and skeptical of VC growth narratives.
Tone: peer-to-peer practitioner, not guru. Direct, no fluff.

Newly published {content_type}:
Title: {meta['title']}
Description: {meta['description']}
URL: {article_url}
Content excerpt: {plain_text}

Return ONLY valid JSON (no markdown, no backticks, no preamble):
{{
  "short": "Max 280 chars including URL. ONE sharp insight or counterintuitive stat. End with the URL. A single punchline that makes a founder stop scrolling. No hashtags. Used for Bluesky and Mastodon.",
  "hook_type": "stat | insight | question | counterintuitive"
}}"""

    messages = [{"role": "user", "content": prompt}]
    raw      = call_ai(messages, label="social_gen")

    # Strip markdown fences kalau ada
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '',       raw).strip()

    result = json.loads(raw)
    result.update({
        "url":          article_url,
        "slug":         slug,
        "folder":       folder,
        "title":        meta["title"],
        "generated_at": datetime.utcnow().isoformat() + "Z"
    })
    return result


# ── Multi-platform posting ────────────────────────────────────────────────────

def _build_bluesky_facets(text: str) -> list:
    """
    Build facets untuk URL dalam teks Bluesky.
    AT Protocol pakai UTF-8 byte offset, bukan character offset.
    Tanpa facets, URL tampil sebagai plain text (tidak clickable).
    """
    facets = []
    for match in re.compile(r'https?://[^\s]+').finditer(text):
        url        = match.group()
        byte_start = len(text[:match.start()].encode("utf-8"))
        byte_end   = byte_start + len(url.encode("utf-8"))
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]
        })
    return facets


def post_to_bluesky(text: str) -> dict:
    """
    Post ke Bluesky via AT Protocol (gratis, tanpa billing).
    Alur: createSession → dapat accessJwt + DID → createRecord.
    Non-fatal.
    """
    if not BSKY_HANDLE or not BSKY_APP_PASSWORD:
        print("    SKIP Bluesky: BSKY_HANDLE / BSKY_APP_PASSWORD tidak tersedia.")
        return {"skipped": True}

    base = "https://bsky.social/xrpc"

    # Auth: dapat accessJwt + DID dari App Password
    req = urllib.request.Request(
        f"{base}/com.atproto.server.createSession",
        data=json.dumps({"identifier": BSKY_HANDLE, "password": BSKY_APP_PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            session = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Bluesky auth {e.code}: {e.read().decode(errors='replace')}")

    # Post: limit 295 grapheme (buffer dari limit AT Protocol 300)
    post_text = text[:295]
    facets    = _build_bluesky_facets(post_text)
    record    = {
        "$type":     "app.bsky.feed.post",
        "text":      post_text,
        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if facets:
        record["facets"] = facets

    req = urllib.request.Request(
        f"{base}/com.atproto.repo.createRecord",
        data=json.dumps({
            "repo":       session["did"],
            "collection": "app.bsky.feed.post",
            "record":     record,
        }).encode(),
        headers={
            "Authorization": f"Bearer {session['accessJwt']}",
            "Content-Type":  "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
        print(f"    Bluesky: posted → {result.get('uri', 'unknown')}")
        return result
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Bluesky post {e.code}: {e.read().decode(errors='replace')}")


def post_to_mastodon(text: str) -> dict:
    """
    Post ke Mastodon via ActivityPub API (gratis).
    Token: generate sekali dari Preferences → Development → New Application (scope: write:statuses).
    Non-fatal.
    """
    if not MASTODON_INSTANCE or not MASTODON_ACCESS_TOKEN:
        print("    SKIP Mastodon: MASTODON_INSTANCE / MASTODON_ACCESS_TOKEN tidak tersedia.")
        return {"skipped": True}

    req = urllib.request.Request(
        f"https://{MASTODON_INSTANCE}/api/v1/statuses",
        data=json.dumps({"status": text[:500], "visibility": "public"}).encode(),
        headers={
            "Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}",
            "Content-Type":  "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
        print(f"    Mastodon: posted → {result.get('url', 'unknown')}")
        return result
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Mastodon post {e.code}: {e.read().decode(errors='replace')}")


# post_to_linkedin() dihapus — LinkedIn Company Page creation diblokir waitlist.


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/social_gen.py <folder> <slug>")
        sys.exit(1)

    folder = sys.argv[1]
    slug   = sys.argv[2]

    if folder not in ("articles", "tools"):
        print(f"ERROR: folder harus 'articles' atau 'tools', bukan '{folder}'")
        sys.exit(1)

    # Validasi env wajib
    missing = []
    if not ENGINE_REPO:    missing.append("ENGINE_REPO")
    if not GITHUB_TOKEN:   missing.append("GITHUB_TOKEN")
    if not OPENROUTER_KEY: missing.append("OPENROUTER_API_KEY")
    if missing:
        print(f"FATAL: Env tidak di-set: {', '.join(missing)}")
        print("       Pastikan secret sudah di-set di GitHub Actions → Settings → Secrets.")
        sys.exit(1)

    # Peringatan jika tidak ada platform posting yang dikonfigurasi
    platforms_ok = any([
        BSKY_HANDLE and BSKY_APP_PASSWORD,
        MASTODON_INSTANCE and MASTODON_ACCESS_TOKEN,
    ])
    if not platforms_ok:
        print("Warning: Tidak ada platform posting yang dikonfigurasi.")
        print("         Set minimal satu pasangan secret:")
        print("           Bluesky  → BSKY_HANDLE + BSKY_APP_PASSWORD")
        print("           Mastodon → MASTODON_INSTANCE + MASTODON_ACCESS_TOKEN")

    model_names = " → ".join(e["model"] for e in MODELS)
    print(f"[social_gen] {folder}/{slug}")
    print(f"    Model priority: {model_names}")

    # 1. Fetch HTML
    print("1/4 Fetch article HTML...")
    html = fetch_article_html(folder, slug)
    print(f"    Fetched: {len(html):,} chars")

    # 2. Generate posts
    print("2/4 Generate social posts via AI...")
    posts = generate_social_posts(folder, slug, html)
    hook       = posts.get("hook_type", "unknown")
    short_post = posts.get("short", "")
    print(f"    hook_type: {hook}")
    print(f"    Short    ({len(short_post)} chars): {short_post[:100]}...")
    
    # 3. Simpan ke output branch (selalu, sebelum posting ke Twitter)
    print("3/4 Save to output branch...")
    save_social_post(slug, posts)

    # 4. Post ke semua platform sosial (masing-masing non-fatal)
    print("4/4 Post ke platform sosial...")
    if short_post:
        # Bluesky (pakai short post)
        try:
            result = post_to_bluesky(short_post)
            if not result.get("skipped"):
                posts["bluesky_posted"] = True
                posts["bluesky_result"] = result
        except Exception as e:
            print(f"    WARNING Bluesky: {e}")
            posts["bluesky_posted"] = False
            posts["bluesky_error"]  = str(e)

        # Mastodon (pakai short post)
        try:
            result = post_to_mastodon(short_post)
            if not result.get("skipped"):
                posts["mastodon_posted"] = True
                posts["mastodon_result"] = result
        except Exception as e:
            print(f"    WARNING Mastodon: {e}")
            posts["mastodon_posted"] = False
            posts["mastodon_error"]  = str(e)
    else:
        print("    SKIP: short post kosong — Bluesky dan Mastodon dilewati.")

    platforms_posted = [
        p for p in ["bluesky", "mastodon"]
        if posts.get(f"{p}_posted")
    ]
    posted_str = ", ".join(platforms_posted) if platforms_posted else "none"
    print(f"\n✓ Done: {folder}/{slug} — posted to: {posted_str}")


if __name__ == "__main__":
    main()

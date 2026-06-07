"""
social_gen.py
Generate social media posts dari artikel/tool yang baru dipublish,
lalu post ke Twitter/X via Official API v2 (OAuth 1.0a).

Usage: python scripts/social_gen.py <folder> <slug>
  folder : articles | tools
  slug   : slug artikel tanpa ekstensi dan tanpa date prefix
"""
import os
import re
import sys
import json
import hmac
import uuid
import time
import base64
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# ── Environment ───────────────────────────────────────────────────────────────
ENGINE_REPO               = os.environ.get("ENGINE_REPO", "akunTools/ai-engine")
GITHUB_TOKEN              = os.environ.get("GITHUB_TOKEN", "")
SITE_URL                  = os.environ.get("SITE_BASE_URL", "https://saastools.corenk.com")
ANTHROPIC_API_KEY         = os.environ.get("ANTHROPIC_API_KEY", "")
TWITTER_API_KEY           = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET        = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN      = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

OUTPUT_BRANCH = "output"
API_BASE      = "https://api.github.com"

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "ai-engine"
    }


def fetch_article_html(folder: str, slug: str) -> str:
    """Ambil HTML dari output branch via GitHub API."""
    # Coba dengan nama file eksak dulu, lalu dengan date prefix
    candidates = [
        f"{folder}/{slug}.html",
    ]
    # Cari file dengan date prefix (format: YYYY-MM-DD-slug.html)
    list_url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{folder}?ref={OUTPUT_BRANCH}"
    req = urllib.request.Request(list_url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read())
            for item in items:
                name = item.get("name", "")
                clean = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', name).replace(".html", "")
                if clean == slug:
                    candidates.insert(0, f"{folder}/{name}")
                    break
    except Exception:
        pass

    last_error = None
    for path in candidates:
        url = f"{API_BASE}/repos/{ENGINE_REPO}/contents/{path}?ref={OUTPUT_BRANCH}"
        req = urllib.request.Request(url, headers=_gh_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Gagal fetch {folder}/{slug}: {last_error}")


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
        print(f"Social post saved to output branch: HTTP {r.status}")


# ── Content extraction ─────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    """Hapus script/style blocks, lalu strip semua HTML tags."""
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>',  ' ', html,
                  flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()


def extract_meta(html: str) -> dict:
    """Ambil title dan description dari meta tags."""
    title_m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    desc_m  = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE
    )
    title = title_m.group(1).strip() if title_m else ""
    title = re.sub(r'\s*[—\-]\s*SaaS Tools.*$', '', title).strip()
    desc  = desc_m.group(1).strip() if desc_m else ""
    return {"title": title, "description": desc}


# ── AI post generation ─────────────────────────────────────────────────────────

def generate_social_posts(folder: str, slug: str, html: str) -> dict:
    """
    Call Claude API untuk generate Twitter + LinkedIn post variants.
    Return dict berisi twitter, linkedin, hook_type, metadata.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY tidak di-set")

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

Return ONLY valid JSON (no markdown, no preamble):
{{
  "twitter": "Max 260 chars. ONE sharp insight or counterintuitive stat from this content. End with the URL. Not a summary — a single punchline that makes a founder stop scrolling. No hashtags.",
  "linkedin": "150-180 words. Start with one concrete data point. Explain why it matters for sub-$50K MRR founders. End with rhetorical question or short CTA + URL. No emoji.",
  "hook_type": "stat | insight | question | counterintuitive"
}}"""

    payload = {
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": 700,
        "messages":   [{"role": "user", "content": prompt}]
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())

    raw = data["content"][0]["text"].strip()
    # Strip markdown code fences kalau ada
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$',       '', raw).strip()

    result = json.loads(raw)
    result.update({
        "url":          article_url,
        "slug":         slug,
        "folder":       folder,
        "title":        meta["title"],
        "generated_at": datetime.utcnow().isoformat() + "Z"
    })
    return result


# ── Twitter / X OAuth 1.0a ────────────────────────────────────────────────────

def _oauth1_header(method: str, url: str) -> str:
    """
    Build OAuth 1.0a Authorization header untuk Twitter API v2.
    Pure stdlib — tidak butuh library eksternal.
    POST body JSON tidak di-include dalam signature (bukan form-encoded).
    """
    oauth_params = {
        "oauth_consumer_key":     TWITTER_API_KEY,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            TWITTER_ACCESS_TOKEN,
        "oauth_version":          "1.0"
    }

    # Signature base string — hanya oauth_params (tidak ada URL query params
    # dan body JSON tidak di-include untuk content-type application/json)
    param_str = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_str, safe="")
    ])

    signing_key = (
        urllib.parse.quote(TWITTER_API_SECRET,         safe="") + "&" +
        urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe="")
    )

    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("ascii"),
            base_string.encode("ascii"),
            hashlib.sha1
        ).digest()
    ).decode()

    oauth_params["oauth_signature"] = signature

    header_value = "OAuth " + ", ".join(
        f'{k}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return header_value


def post_to_twitter(text: str) -> dict:
    """
    Post tweet via Twitter API v2.
    Return result dict. Raise RuntimeError jika gagal.
    """
    creds = [TWITTER_API_KEY, TWITTER_API_SECRET,
             TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]
    if not all(creds):
        print("SKIP: Twitter credentials tidak lengkap "
              "(set TWITTER_API_KEY, TWITTER_API_SECRET, "
              "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)")
        return {"skipped": True, "reason": "missing_credentials"}

    tweet_text = text[:280]  # Hard character limit
    url        = "https://api.twitter.com/2/tweets"
    body       = json.dumps({"text": tweet_text}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": _oauth1_header("POST", url),
            "Content-Type":  "application/json",
            "User-Agent":    "ai-engine"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result   = json.loads(r.read())
            tweet_id = result.get("data", {}).get("id", "unknown")
            print(f"Tweet posted successfully: id={tweet_id}")
            return result
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        raise RuntimeError(f"Twitter API error {e.code}: {err_body}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/social_gen.py <folder> <slug>")
        print("  folder : articles | tools")
        print("  slug   : artikel slug (tanpa .html, tanpa date prefix)")
        sys.exit(1)

    folder = sys.argv[1]
    slug   = sys.argv[2]

    if folder not in ("articles", "tools"):
        print(f"ERROR: folder harus 'articles' atau 'tools', bukan '{folder}'")
        sys.exit(1)

    print(f"[social_gen] Processing: {folder}/{slug}")

    # 1. Fetch HTML dari output branch
    print("Fetching article HTML...")
    html = fetch_article_html(folder, slug)
    print(f"Fetched: {len(html):,} chars")

    # 2. Generate posts via Claude API
    print("Generating social posts via Claude API...")
    posts = generate_social_posts(folder, slug, html)
    hook  = posts.get("hook_type", "unknown")
    tw    = posts.get("twitter", "")
    li    = posts.get("linkedin", "")
    print(f"Generated (hook_type: {hook})")
    print(f"  Twitter  ({len(tw)} chars): {tw[:100]}...")
    print(f"  LinkedIn ({len(li)} chars): {li[:100]}...")

    # 3. Simpan ke output branch (selalu — bahkan jika Twitter posting gagal)
    print("Saving generated posts to output branch...")
    save_social_post(slug, posts)

    # 4. Post ke Twitter (non-fatal — failure dicatat tapi workflow tetap sukses)
    if tw:
        print("Posting to Twitter/X...")
        try:
            twitter_result = post_to_twitter(tw)
            posts["twitter_posted"] = True
            posts["twitter_result"] = twitter_result
        except Exception as e:
            print(f"WARNING: Twitter posting failed: {e}")
            posts["twitter_posted"] = False
            posts["twitter_error"]  = str(e)
    else:
        print("WARNING: Twitter post is empty — skip posting")

    print("[social_gen] Done")


if __name__ == "__main__":
    main()

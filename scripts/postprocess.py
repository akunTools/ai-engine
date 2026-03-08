"""
postprocess.py
Validasi dan format output dari AI sebelum dipublish.
Artikel di-convert dari Markdown ke HTML lengkap sebelum dipublish.
"""
import re
from datetime import datetime


def _reading_time(text: str) -> int:
    """Estimasi waktu baca dalam menit (200 kata/menit)."""
    return max(1, round(len(text.split()) / 200))


# ─────────────────────────────────────────────
# SHARED DESIGN SYSTEM
# ─────────────────────────────────────────────

_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,'
    'opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,'
    '400&display=swap" rel="stylesheet">'
)

_BASE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:           #f7f6f3;
    --surface:      #ffffff;
    --text:         #18181b;
    --muted:        #71717a;
    --subtle:       #a1a1aa;
    --border:       #e4e4e7;
    --accent:       #4f46e5;
    --accent-h:     #4338ca;
    --accent-light: #eef2ff;
    --danger:       #ef4444;
    --danger-bg:    #fef2f2;
    --warning:      #f59e0b;
    --warning-bg:   #fffbeb;
    --success:      #10b981;
    --success-bg:   #f0fdf4;
    --r:            10px;
    --shadow:       0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
    --shadow-md:    0 4px 16px rgba(0,0,0,.08);
  }
  body {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-h); }
"""

_NAV_CSS = """
  nav {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 20px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .nav-inner {
    max-width: 720px;
    margin: 0 auto;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .nav-brand {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -.02em;
  }
  .brand-accent { color: var(--accent); }
  .nav-back {
    font-size: .875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 0;
    transition: color .15s;
  }
  .nav-back:hover { color: var(--accent); }
  .nav-links { display: flex; gap: 2px; }
  .nav-links a {
    font-size: .875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 8px;
    transition: all .15s;
  }
  .nav-links a:hover { color: var(--text); background: var(--bg); }
  .nav-links a.active { color: var(--accent); background: var(--accent-light); }
"""

_FOOTER_HTML = """<footer>
  <div class="footer-inner">
    <div class="footer-top">
      <a href="/" class="footer-brand">SaaS<span class="footer-accent">Tools</span></a>
      <nav class="footer-nav">
        <a href="/articles/">Articles</a>
        <a href="/tools/">Tools</a>
      </nav>
    </div>
    <div class="footer-bottom">
      Free calculators and guides for bootstrapped founders.
    </div>
  </div>
</footer>"""

_FOOTER_CSS = """
  footer {
    border-top: 1px solid var(--border);
    background: var(--surface);
    padding: 32px 20px;
    margin-top: 64px;
  }
  .footer-inner {
    max-width: 720px;
    margin: 0 auto;
  }
  .footer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .footer-brand {
    font-size: .95rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -.02em;
  }
  .footer-accent { color: var(--accent); }
  .footer-nav { display: flex; gap: 24px; }
  .footer-nav a {
    font-size: .8rem;
    color: var(--muted);
    text-decoration: none;
    transition: color .15s;
  }
  .footer-nav a:hover { color: var(--accent); }
  .footer-bottom {
    font-size: .75rem;
    color: var(--subtle);
    border-top: 1px solid var(--border);
    padding-top: 16px;
  }
"""

_TOOL_CSS = ""  # CSS disediakan oleh wrap_tool_html — tidak dipakai standalone

# ─────────────────────────────────────────────
# RELATED CONTENT
# Plain strings (NOT f-strings) — brace characters are single { }
# ─────────────────────────────────────────────

_RELATED_CSS = """
    /* ── RELATED CONTENT ── */
    .related-content { margin-bottom: 32px; }
    .related-heading {
      font-size: .75rem;
      font-weight: 600;
      color: var(--subtle);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 10px;
      margin-top: 20px;
    }
    .related-heading:first-child { margin-top: 0; }
    .related-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .related-list li a {
      font-size: .875rem;
      color: var(--accent);
      text-decoration: none;
      display: block;
      padding: 8px 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 7px;
      transition: border-color .15s;
    }
    .related-list li a:hover {
      border-color: var(--accent);
    }
"""

# Plain string — { } are literal JS braces, NOT f-string escapes.
_RELATED_JS = """<script>
(function() {
  var meta    = document.querySelector('meta[name="cluster"]');
  var cluster = meta ? meta.getAttribute('content') : '';
  if (!cluster) return;
  var parts       = window.location.pathname.split('/').filter(Boolean);
  var currentSlug = (parts[parts.length - 1] || '').replace('.html', '');
  fetch('/content-index.json')
    .then(function(r) { return r.json(); })
    .then(function(idx) {
      var articles = (idx.articles || [])
        .filter(function(a) { return a.cluster === cluster && a.slug !== currentSlug; })
        .slice(0, 3);
      var tools = (idx.tools || [])
        .filter(function(t) { return t.cluster === cluster && t.slug !== currentSlug; })
        .slice(0, 2);
      var html = '';
      if (articles.length) {
        html += '<h3 class="related-heading">Related Articles</h3>'
              + '<ul class="related-list">';
        articles.forEach(function(a) {
          html += '<li><a href="/articles/' + a.slug + '">' + a.title + '</a></li>';
        });
        html += '</ul>';
      }
      if (tools.length) {
        html += '<h3 class="related-heading">Related Tools</h3>'
              + '<ul class="related-list">';
        tools.forEach(function(t) {
          html += '<li><a href="/tools/' + t.slug + '">' + t.title + '</a></li>';
        });
        html += '</ul>';
      }
      if (html) {
        var el = document.getElementById('related-content');
        if (el) el.innerHTML = html;
      }
    })
    .catch(function() {});
})();
</script>"""


# ─────────────────────────────────────────────
# ARTICLE TEMPLATE
# ─────────────────────────────────────────────

def _build_article_html(fm: dict, body_html: str,
                        slug: str, date_str: str,
                        cluster_id: str = "") -> str:
    site_url    = "https://saas.blogtrick.eu.org"
    title       = fm.get("title", slug.replace("-", " ").title())
    keyword     = fm.get("primary_keyword", "")
    article_url = f"{site_url}/articles/{slug}"
    read_time   = _reading_time(body_html)

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%B %-d, %Y")
    except Exception:
        display_date = date_str

    kw_meta      = f'<meta name="keywords" content="{keyword}">' if keyword else ""
    cluster_meta = f'<meta name="cluster" content="{cluster_id}">' if cluster_id else ""
    meta_desc    = fm.get("meta_desc", title)

    kw_badge = (
        f'<span class="article-header__kw">'
        f'<span class="kw-badge">{keyword}</span>'
        f'</span>'
    ) if keyword else ""

    title_encoded = title.replace(" ", "%20")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SaaS Tools</title>
  <meta name="description" content="{meta_desc}">
  {kw_meta}
  {cluster_meta}
  <meta property="og:title" content="{title}">
  <meta property="og:url" content="{article_url}">
  <meta property="og:type" content="article">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="{article_url}">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    .article-wrap {{
      max-width: 680px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }}

    .article-header {{
      padding: 3rem 0 2.25rem;
      border-bottom: 1px solid var(--border);
    }}

    .article-header__title {{
      font-size: clamp(1.625rem, 4.5vw, 2.25rem);
      font-weight: 700;
      letter-spacing: -0.025em;
      line-height: 1.18;
      color: var(--text);
      margin-bottom: 1rem;
    }}

    .article-header__meta {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.5rem;
      font-size: 0.8125rem;
      color: var(--subtle);
    }}

    .article-header__meta-sep {{ color: var(--border); user-select: none; }}

    .kw-badge {{
      display: inline-block;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: var(--accent);
      background: var(--accent-light);
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }}

    .article-body {{ padding: 2.25rem 0; }}
    .article-body > * + * {{ margin-top: 1.375rem; }}
    .article-body p {{ font-size: 1rem; line-height: 1.75; color: var(--text); }}

    .article-body h2 {{
      font-size: 1.1875rem;
      font-weight: 700;
      letter-spacing: -0.015em;
      color: var(--text);
      padding-left: 0.875rem;
      border-left: 3px solid var(--accent);
      margin-top: 2.25rem;
    }}

    .article-body h3 {{ font-size: 1rem; font-weight: 600; color: var(--text); margin-top: 1.75rem; }}
    .article-body h4 {{ font-size: .95rem; font-weight: 600; color: var(--text); margin-top: 1.375rem; }}
    .article-body ul, .article-body ol {{ padding-left: 1.375rem; }}
    .article-body li {{ font-size: 1rem; line-height: 1.7; color: var(--text); }}
    .article-body li + li {{ margin-top: 0.375rem; }}

    .article-body blockquote {{
      border-left: 3px solid var(--border);
      padding: 0.5rem 0 0.5rem 1.125rem;
    }}
    .article-body blockquote p {{ font-style: italic; color: var(--muted); }}

    .article-body code {{
      font-family: 'DM Mono', 'Fira Code', monospace;
      font-size: 0.875em;
      background: var(--accent-light);
      color: var(--accent);
      padding: 0.15em 0.4em;
      border-radius: 4px;
    }}

    .article-body pre {{
      background: #18181b;
      border-radius: var(--r);
      padding: 1.125rem 1.25rem;
      overflow-x: auto;
    }}
    .article-body pre code {{
      background: none; color: #e4e4e7; padding: 0;
      font-size: 0.875rem; line-height: 1.65; border-radius: 0;
    }}

    .article-body hr {{ border: none; border-top: 1px solid var(--border); margin: 2rem 0; }}
    .article-body strong {{ font-weight: 600; color: var(--text); }}
    .article-body a {{ color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }}
    .article-body a:hover {{ color: var(--accent-h); }}

    .article-body table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    .article-body th, .article-body td {{
      padding: 0.625rem 0.75rem; border: 1px solid var(--border); text-align: left;
    }}
    .article-body th {{ background: var(--bg); font-weight: 600; font-size: 0.8125rem; }}

    .share-section {{
      border-top: 1px solid var(--border);
      padding: 1.5rem 0;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}

    .share-section__label {{
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--subtle);
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-right: 0.25rem;
    }}

    .share-btn {{
      background: none; border: none; padding: 0;
      font-family: inherit; font-size: 0.9rem;
      color: var(--accent); cursor: pointer;
      text-decoration: underline; text-underline-offset: 3px;
      min-height: 44px; display: inline-flex; align-items: center;
    }}
    .share-btn:hover {{ color: var(--accent-h); }}
    .share-sep {{ color: var(--border); font-size: 0.875rem; user-select: none; }}

    .comments-section {{
      border-top: 1px solid var(--border);
      padding: 2rem 0 3rem;
    }}
    .comments-section__label {{
      font-size: 0.8125rem; font-weight: 700;
      letter-spacing: 0.08em; text-transform: uppercase;
      color: var(--subtle); margin-bottom: 1.375rem;
    }}

{_RELATED_CSS}
{_FOOTER_CSS}

    @media (max-width: 600px) {{
      .article-header {{ padding: 2rem 0 1.75rem; }}
      .article-body h2 {{ font-size: 1.0625rem; }}
      .article-body table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>

<nav>
  <div class="nav-inner">
    <a href="/articles/" class="nav-back">← Articles</a>
    <div class="nav-links">
      <a href="/articles/" class="active">Articles</a>
      <a href="/tools/">Tools</a>
    </div>
  </div>
</nav>

<main class="article-wrap">

  <header class="article-header">
    <h1 class="article-header__title">{title}</h1>
    <div class="article-header__meta">
      <span>{display_date}</span>
      <span class="article-header__meta-sep">·</span>
      <span>{read_time} min read</span>
      {kw_badge}
    </div>
  </header>

  <article class="article-body">
    {body_html}
  </article>

  <div id="related-content" class="related-content"></div>

  <div class="share-section">
    <span class="share-section__label">Share</span>
    <a class="share-btn"
       href="https://twitter.com/intent/tweet?url={article_url}&amp;text={title_encoded}"
       target="_blank" rel="noopener noreferrer">Twitter / X</a>
    <span class="share-sep">·</span>
    <a class="share-btn"
       href="https://www.linkedin.com/sharing/share-offsite/?url={article_url}"
       target="_blank" rel="noopener noreferrer">LinkedIn</a>
    <span class="share-sep">·</span>
    <button class="share-btn" id="copy-btn" onclick="copyLink()">Copy link</button>
  </div>

  <section class="comments-section">
    <div class="comments-section__label">Discussion</div>
    <script src="https://giscus.app/client.js"
      data-repo="akunTools/ai-engine"
      data-repo-id="GANTI_DENGAN_REPO_ID_ANDA"
      data-category="General"
      data-category-id="GANTI_DENGAN_CATEGORY_ID_ANDA"
      data-mapping="pathname"
      data-strict="0"
      data-reactions-enabled="1"
      data-emit-metadata="0"
      data-input-position="top"
      data-theme="light"
      data-lang="en"
      crossorigin="anonymous"
      async>
    </script>
    <noscript>
      <p style="color:var(--muted);font-size:.875rem;">
        Enable JavaScript to load comments.
      </p>
    </noscript>
  </section>

</main>

{_FOOTER_HTML}

<script>
  function copyLink() {{
    navigator.clipboard.writeText("{article_url}").then(function() {{
      var btn = document.getElementById("copy-btn");
      var original = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(function() {{ btn.textContent = original; }}, 2000);
    }});
  }}
</script>

{_RELATED_JS}

</body>
</html>"""


# ─────────────────────────────────────────────
# MANUAL CONTENT WRAPPING
# ─────────────────────────────────────────────

def wrap_article_html(body_html: str, slug: str) -> str:
    """
    Bungkus body artikel ke full HTML page.
    Input : body HTML saja — boleh diawali <meta name="cluster">
            dan/atau <meta name="description"> sebelum <h1>.
            JANGAN sertakan <!DOCTYPE>, <html>, <head>, <nav>,
            atau <footer> — pipeline akan menambahkannya.
    Output: full HTML page siap publish.
    """
    # Ekstrak cluster_id
    cluster_match = re.search(
        r'<meta\s+name=["\'\'\'cluster["\'\'\']\s+content=["\'\'\'([^"\'\'\']*)["\'\'\'"][^>]*/?>',.replace("\\'\\'\\'","'"),
        body_html, re.IGNORECASE
    )
    cluster_id = cluster_match.group(1).strip() if cluster_match else ""
    if cluster_match:
        body_html = body_html[:cluster_match.start()] + body_html[cluster_match.end():]
        body_html = body_html.lstrip("\n")

    # Ekstrak meta description
    desc_match = re.search(
        r'<meta\s+name=["\'\'\'description["\'\'\']\s+content=["\'\'\'([^"\'\'\']*)["\'\'\'"][^>]*/?>',.replace("\\'\\'\\'","'"),
        body_html, re.IGNORECASE
    )
    meta_desc = desc_match.group(1).strip() if desc_match else ""
    if desc_match:
        body_html = body_html[:desc_match.start()] + body_html[desc_match.end():]
        body_html = body_html.lstrip("\n")

    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (h1_match.group(1).strip()
             if h1_match
             else slug.replace("-", " ").title())

    # Strip h1 dari body — judul sudah dirender di page header
    if h1_match:
        body_html = (body_html[:h1_match.start()]
                     + body_html[h1_match.end():]).lstrip("\n")

    title_clean = re.sub(r'<[^>]+>', '', title).strip()
    word_count  = len(re.sub(r'<[^>]+>', '', body_html).split())

    if not meta_desc:
        meta_desc = title_clean

    fm = {
        "title":           title_clean,
        "slug":            slug,
        "date":            date_str,
        "primary_keyword": "",
        "cluster_id":      cluster_id,
        "meta_desc":       meta_desc,
        "word_count":      word_count
    }

    return _build_article_html(fm, body_html, slug, date_str, cluster_id)

def wrap_tool_html(body_html: str, slug: str) -> str:
    """
    Bungkus body tool/kalkulator ke full HTML page.
    Input : body HTML saja — boleh diawali <meta name="cluster">
            sebelum <h1>. Tanpa <html>/<head>/<style>.
            Gunakan CSS class yang tersedia di bawah.
    Output: full HTML page siap publish

    CSS classes yang tersedia:
    .card, .card h2
    .input-group, label, .input-wrapper, .input-prefix
    input[type="number"]
    .result-card, .result-label, .result-number, .result-unit
    .interpretation, .secondary-result
    .formula-box, .formula-box h3, .formula-box p
    .affiliate-box, .affiliate-box a
    .related-link, .related-link a
    .subtitle
    """
    # Ekstrak cluster_id dari meta tag
    cluster_match = re.search(
        r'<meta\s+name=["\']cluster["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    cluster_id = cluster_match.group(1).strip() if cluster_match else ""
    if cluster_match:
        body_html = body_html[:cluster_match.start()] + body_html[cluster_match.end():]
        body_html = body_html.lstrip("\n")

    # Ekstrak meta description
    desc_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\'][^>]*/?>',
        body_html, re.IGNORECASE
    )
    meta_desc = desc_match.group(1).strip() if desc_match else ""
    if desc_match:
        body_html = body_html[:desc_match.start()] + body_html[desc_match.end():]
        body_html = body_html.lstrip("\n")

    site_url     = "https://saas.blogtrick.eu.org"
    tool_url     = f"{site_url}/tools/{slug}"
    cluster_meta = f'<meta name="cluster" content="{cluster_id}">' if cluster_id else ""

    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>',
                         body_html, re.IGNORECASE | re.DOTALL)
    title = (h1_match.group(1).strip()
             if h1_match
             else slug.replace("-", " ").title())
    title_clean = re.sub(r'<[^>]+>', '', title).strip()

    # Fallback: generate deskripsi standar jika Claude tidak menulis meta description
    if not meta_desc:
        meta_desc = f"{title_clean}. Free calculator for bootstrapped SaaS founders."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_clean} — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="{meta_desc}">
  {cluster_meta}
  <link rel="canonical" href="{tool_url}">
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── LAYOUT ── */
    .container {{ max-width: 680px; margin: 0 auto; padding: 40px 20px 80px; }}

    /* ── TYPOGRAPHY ── */
    h1 {{
      font-size: clamp(1.5rem, 4vw, 1.9rem);
      font-weight: 700;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 6px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: .95rem;
      margin-bottom: 28px;
      line-height: 1.5;
    }}

    /* ── CARD ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 24px;
      margin-bottom: 14px;
    }}
    .card h2 {{
      font-size: .9rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 20px;
    }}

    /* ── INPUTS ── */
    .input-group {{ margin-bottom: 18px; }}
    .input-group:last-child {{ margin-bottom: 0; }}
    label {{
      display: block;
      font-size: .85rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 7px;
    }}
    .input-wrapper {{ position: relative; }}
    .input-prefix {{
      position: absolute;
      left: 13px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: .9rem;
      pointer-events: none;
      font-weight: 500;
    }}
    input[type="number"] {{
      width: 100%;
      padding: 10px 14px 10px 30px;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 1rem;
      color: var(--text);
      background: var(--surface);
      font-family: inherit;
      transition: border-color .15s, box-shadow .15s;
      -moz-appearance: textfield;
    }}
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {{ -webkit-appearance: none; }}
    input[type="number"]:focus {{
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(79,70,229,.1);
    }}
    input[type="number"].error-input {{ border-color: var(--danger); }}
    .error-msg {{
      color: var(--danger);
      font-size: .75rem;
      margin-top: 4px;
      display: none;
    }}

    /* ── RESULT ── */
    .result-card {{
      background: var(--accent-light);
      border: 1.5px solid rgba(79,70,229,.2);
      border-radius: var(--r);
      padding: 28px 24px 24px;
      margin-bottom: 14px;
    }}
    .result-label {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 6px;
    }}
    .result-number {{
      font-size: 3.5rem;
      font-weight: 700;
      color: var(--accent);
      line-height: 1;
      letter-spacing: -.04em;
      margin-bottom: 2px;
    }}
    .result-unit {{
      font-size: .875rem;
      color: var(--accent);
      opacity: .7;
      margin-bottom: 16px;
    }}
    .interpretation {{
      background: var(--surface);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: .875rem;
      color: var(--text);
      line-height: 1.5;
      border-left: 3px solid var(--accent);
    }}
    .interpretation.danger {{
      border-color: var(--danger);
      background: var(--danger-bg);
    }}
    .interpretation.warning {{
      border-color: var(--warning);
      background: var(--warning-bg);
    }}
    .interpretation.healthy {{
      border-color: var(--success);
      background: var(--success-bg);
    }}
    .secondary-result {{
      margin-top: 12px;
      font-size: .8rem;
      color: var(--muted);
    }}

    /* ── FORMULA BOX ── */
    .formula-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 20px 24px;
      margin-bottom: 14px;
    }}
    .formula-box h3 {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--subtle);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 10px;
    }}
    .formula-box p {{
      font-size: .875rem;
      color: var(--muted);
      line-height: 1.7;
      font-family: 'SFMono-Regular', Consolas, monospace;
    }}

    /* ── AFFILIATE BOX ── */
    .affiliate-box {{
      background: var(--success-bg);
      border: 1px solid rgba(16,185,129,.25);
      border-radius: var(--r);
      padding: 16px 20px;
      margin-bottom: 14px;
      font-size: .875rem;
      color: var(--text);
      line-height: 1.6;
    }}
    .affiliate-box a {{
      color: var(--success);
      font-weight: 500;
      text-decoration: underline;
      text-decoration-color: rgba(16,185,129,.4);
    }}
    .affiliate-box a:hover {{ color: #059669; }}

    /* ── RELATED LINK ── */
    .related-link {{
      font-size: .85rem;
      color: var(--muted);
      padding: 12px 0;
    }}
    .related-link a {{
      color: var(--accent);
      text-decoration: underline;
      text-decoration-color: rgba(79,70,229,.3);
      font-weight: 500;
    }}
    .related-link a:hover {{ color: var(--accent-h); }}

{_RELATED_CSS}
{_FOOTER_CSS}

    @media (max-width: 600px) {{
      .container {{ padding: 28px 16px 60px; }}
      .result-number {{ font-size: 2.75rem; }}
    }}
  </style>
</head>
<body>

<nav>
  <div class="nav-inner">
    <a href="/tools/" class="nav-back">← All Tools</a>
    <div class="nav-links">
      <a href="/articles/">Articles</a>
      <a href="/tools/" class="active">Tools</a>
    </div>
  </div>
</nav>

<div class="container">
{body_html}
<div id="related-content"></div>
</div>

{_FOOTER_HTML}

{_RELATED_JS}

</body>
</html>"""


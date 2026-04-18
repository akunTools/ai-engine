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

# ── Analytics beacon — injected ke semua halaman ──────────────────────────────
_ANALYTICS = (
    ""
    "<script defer src='https://static.cloudflareinsights.com/beacon.min.js'"
    " data-cf-beacon='{\"token\": \"5833f90d78f645e0819abedd665e5d93\"}'>"
    "</script>"
    ""
)

# ── Affiliate click tracker — injected ke semua halaman ──────────────────────
_AFFILIATE_TRACKER_JS = """<script>
(function () {
  document.addEventListener('click', function (e) {
    var el = e.target.closest('a[href]');
    if (!el) return;
    var href = el.getAttribute('href') || '';
    if (href.indexOf('cloudways.com') === -1 || href.indexOf('id=') === -1) return;
    if (typeof window.cfBeacon === 'undefined' || typeof window.cfBeacon.pushEvent !== 'function') return;
    window.cfBeacon.pushEvent('affiliate_click', {
      affiliate: 'cloudways',
      page: window.location.pathname
    });
  }, true);
})();
</script>"""

_BASE_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:           #fafafa;
    --surface:      #ffffff;
    --text:         #18181b;
    --muted:        #52525b;
    --subtle:       #a1a1aa;
    --border:       #e4e4e7;
    --accent:       #2563eb;
    --accent-h:     #1d4ed8;
    --accent-light: #eff6ff;
    --danger:       #dc2626;
    --danger-bg:    #fef2f2;
    --warning:      #d97706;
    --warning-bg:   #fffbeb;
    --success:      #059669;
    --success-bg:   #f0fdf4;
    --r:            4px;
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
  
  /* Global Focus State for Accessibility */
  *:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
"""

_NAV_CSS = """
  nav.site-nav,
  body > nav:not(.footer-nav) {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  .nav-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 0 24px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .nav-brand {
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    min-height: 44px;
  }
  .brand-accent {
    color: var(--accent);
  }
  .nav-links {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .nav-links a {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 0 12px;
    min-height: 44px;
    display: flex;
    align-items: center;
    border-radius: var(--r);
    transition: color 0.15s ease, background 0.15s ease;
  }
  .nav-links a:hover {
    color: var(--text);
    background: var(--bg);
  }
  .nav-links a.active {
    color: var(--accent);
    background: var(--accent-light);
    border: 1px solid #bfdbfe;
  }
  .nav-back {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 44px;
    padding: 0 8px;
    border-radius: var(--r);
    transition: color 0.15s ease;
  }
  .nav-back:hover {
    color: var(--text);
    background: var(--bg);
  }
  @media (max-width: 640px) {
    .nav-inner { padding: 0 16px; }
    .nav-links a { padding: 0 8px; }
  }
"""

_FOOTER_HTML = """<footer>
  <div class="footer-inner">
    <div class="footer-top">
      <a href="/" class="footer-brand">SaaS<span class="footer-accent">Tools</span></a>
      <nav class="footer-nav">
        <a href="/articles/">Articles</a>
        <a href="/tools/">Tools</a>
        <a href="/about.html">About</a>
        <a href="/privacy">Privacy</a>
      </nav>
    </div>
    <div class="footer-bottom">
      Built for bootstrapped founders. No VC fluff.
    </div>
  </div>
</footer>"""

_FOOTER_CSS = """
  footer {
    background: var(--bg);
    border-top: 1px solid var(--border);
    margin-top: 80px;
  }
  .footer-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 48px 24px;
  }
  .footer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }
  .footer-brand {
    font-size: 1.0625rem;
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    min-height: 44px;
  }
  .footer-accent { color: var(--accent); }
  .footer-nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .footer-nav a {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    padding: 0 12px;
    min-height: 44px;
    display: flex;
    align-items: center;
    border-radius: var(--r);
    transition: color 0.15s ease;
  }
  .footer-nav a:hover { color: var(--text); }
  .footer-bottom {
    margin-top: 32px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    font-size: 0.8125rem;
    color: var(--muted);
    line-height: 1.6;
    font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
  }
  @media (max-width: 640px) {
    footer { margin-top: 48px; }
    .footer-inner { padding: 40px 16px; }
    .footer-top {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
    }
    .footer-nav { margin-left: -12px; }
  }
"""

_ARTICLE_CSS = """
  .article-wrap {
    max-width: 680px;
    margin: 0 auto;
    padding: 0 24px;
  }
  .article-header {
    padding: 64px 0 40px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 48px;
  }
  .article-header__title {
    font-size: clamp(1.75rem, 4vw, 2.5rem);
    font-weight: 700;
    color: var(--text);
    line-height: 1.25;
    letter-spacing: -0.03em;
    margin: 0 0 24px;
  }
  .article-header__meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 0.85rem;
    font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
    color: var(--muted);
    line-height: 1;
  }
  .article-header__meta span {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .article-header__meta-sep { color: var(--border); }
  .kw-badge {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text);
    background: var(--border);
    padding: 4px 8px;
    border-radius: 4px;
  }
  .article-body {
    font-size: 1.0625rem;
    line-height: 1.72;
    color: var(--text);
    overflow-wrap: break-word;
    word-break: break-word;
  }
  .article-body h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
    line-height: 1.3;
    margin: 56px 0 24px;
    border-bottom: 2px solid var(--text);
    padding-bottom: 8px;
  }
  .article-body h3 {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
    line-height: 1.4;
    margin: 40px 0 16px;
  }
  .article-body p { margin: 0 0 24px; }
  .article-body ul, .article-body ol {
    margin: 0 0 24px;
    padding-left: 24px;
  }
  .article-body li { margin-bottom: 8px; }
  .article-body li::marker { color: var(--muted); font-weight: bold; }
  .article-body a {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 4px;
    text-decoration-thickness: 1px;
    transition: color 0.15s ease, text-decoration-color 0.15s ease;
  }
  .article-body a:hover {
    color: var(--text);
    text-decoration-color: var(--text);
  }
  
  /* Utilitarian Blockquote */
  .article-body blockquote {
    margin: 32px 0;
    padding: 20px 24px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 4px solid var(--text);
    color: var(--text);
    font-size: 1.0625rem;
    font-style: normal;
    line-height: 1.72;
  }
  .article-body blockquote p:last-child { margin-bottom: 0; }
  
  /* Micro-details: Inline Code vs Preformatted Code */
  .article-body code {
    font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
    font-size: 0.85em;
    background: #f4f4f5;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.2em 0.4em;
    border-radius: 3px;
  }
  .article-body pre {
    background: #18181b;
    color: #e4e4e7;
    border-radius: var(--r);
    padding: 20px 24px;
    margin: 32px 0;
    font-size: 0.85rem;
    line-height: 1.6;
    border: 1px solid #3f3f46;
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .article-body pre code {
    background: transparent;
    border: none;
    color: inherit;
    padding: 0;
    font-size: inherit;
  }
  
  /* Micro-details: Image & Table Responsiveness */
  .article-body img {
    max-width: 100%;
    height: auto;
    border-radius: var(--r);
    border: 1px solid var(--border);
    display: block;
    margin: 40px 0;
  }
  .article-body table {
    width: 100%;
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border-collapse: collapse;
    margin: 32px 0;
    font-size: 0.9rem;
    border: 1px solid var(--border);
  }
  .article-body th, .article-body td {
    padding: 12px 16px;
    border: 1px solid var(--border);
    color: var(--text);
  }
  .article-body th {
    background: var(--bg);
    font-weight: 600;
    text-align: left;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.8125rem;
    white-space: nowrap;
  }
  .article-body hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 56px 0;
  }
  
  .share-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 32px;
    margin: 56px 0 48px;
  }
  @media (max-width: 640px) {
    .share-box {
      padding: 20px;
      margin: 40px 0 32px;
    }
  }
  .share-label {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 16px;
  }
  .share-buttons { display: flex; flex-wrap: wrap; gap: 12px; }
  .share-btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 0 16px; border-radius: var(--r);
    font-size: 0.875rem; font-weight: 500; text-decoration: none;
    cursor: pointer; border: 1px solid var(--border);
    background: var(--surface); color: var(--text); min-height: 44px;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .share-btn:hover { background: var(--bg); border-color: var(--muted); }
  .comments-box { margin-bottom: 48px; }
  .comments-box h2 {
    font-size: 1.25rem; font-weight: 700; color: var(--text);
    margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid var(--text);
  }
  
  @media (max-width: 640px) {
    .article-wrap { padding: 0 16px; }
    .article-header { padding: 40px 0 32px; }
    .article-body { font-size: 1rem; }
    .article-body pre {
      margin: 32px -16px;
      border-radius: 0;
      border-left: none;
      border-right: none;
    }
    .article-body table {
      margin: 32px -16px;
      width: calc(100% + 32px);
      border-left: none;
      border-right: none;
      border-radius: 0;
    }
  }
"""

_TOOL_CSS = ""  # CSS disediakan oleh wrap_tool_html — tidak dipakai standalone

_RELATED_CSS = """
  .related-content { margin-bottom: 32px; }
  .related-heading {
    font-size: .75rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .05em;
    margin-bottom: 12px; margin-top: 24px;
  }
  .related-heading:first-child { margin-top: 0; }
  .related-list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 8px;
  }
  .related-list li a {
    font-size: .9rem; color: var(--text); text-decoration: none;
    display: block; padding: 12px 16px; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--r);
    transition: border-color .15s, background .15s;
  }
  .related-list li a:hover { border-color: var(--text); background: var(--bg); }
"""

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
    """
    Bungkus article body HTML ke dalam full HTML page.
    """
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
        f'<span class="article-header__meta-sep">·</span>'
        f'<span class="kw-badge">{keyword}</span>'
    ) if keyword else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="{meta_desc}">
  {kw_meta}
  {cluster_meta}
  <meta property="og:title" content="{title}">
  <meta property="og:url" content="{article_url}">
  <meta property="og:type" content="article">
  <meta property="og:image" content="{site_url}/og/{slug}.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="SaaS Tools for Bootstrapped Founders">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:image" content="{site_url}/og/{slug}.png">
  <link rel="canonical" href="{article_url}">
  <link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
  <link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
  <link rel="shortcut icon" href="/favicon/favicon.ico" />
  <link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
  <link rel="manifest" href="/favicon/site.webmanifest" />
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}
{_ARTICLE_CSS}
{_RELATED_CSS}
{_FOOTER_CSS}

    /* ── FOOTER: override global margin-top for article page ── */
    footer {{ margin-top: 0; }}
  </style>
  {_ANALYTICS}
</head>
<body>

<nav class="site-nav">
  <div class="nav-inner">
    <a href="/articles/" class="nav-back">← Articles</a>
    <div class="nav-links">
      <a href="/tools/">Tools</a>
    </div>
  </div>
</nav>

<main class="article-wrap">

  <header class="article-header">
    <h1 class="article-header__title">{title}</h1>
    <div class="article-header__meta">
      <span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/>
          <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        {display_date}
      </span>
      <span class="article-header__meta-sep">·</span>
      <span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        {read_time} min read
      </span>
      {kw_badge}
    </div>
  </header>

  <article class="article-body">
    {body_html}
  </article>

  <div id="related-content" class="related-content"></div>

  <div class="share-box">
    <div class="share-label">Share this article</div>
    <div class="share-buttons">
      <a class="share-btn x-btn"
         href="https://twitter.com/intent/tweet?text={title.replace(' ', '%20')}&url={article_url}"
         target="_blank" rel="noopener">
        𝕏 Post on X
      </a>
      <a class="share-btn li-btn"
         href="https://www.linkedin.com/sharing/share-offsite/?url={article_url}"
         target="_blank" rel="noopener">
        in Share
      </a>
      <button class="share-btn copy-btn" id="copy-btn" onclick="copyLink()">
        🔗 Copy link
      </button>
    </div>
  </div>

  <div class="comments-box">
    <h2>Discussion</h2>
    <script src="https://giscus.app/client.js"
      data-repo="akunTools/ai-engine"
      data-repo-id="R_kgDORZ0kXg"
      data-category="General"
      data-category-id="DIC_kwDORZ0kXs4C3fKy"
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
  </div>

</main>

{_FOOTER_HTML}

<script>
  function copyLink() {{
    navigator.clipboard.writeText("{article_url}").then(function() {{
      var btn = document.getElementById("copy-btn");
      btn.textContent = "✓ Copied!";
      btn.classList.add("copied");
      setTimeout(function() {{
        btn.textContent = "🔗 Copy link";
        btn.classList.remove("copied");
      }}, 2000);
    }});
  }}
</script>

{_RELATED_JS}

{_AFFILIATE_TRACKER_JS}

</body>
</html>"""


# ─────────────────────────────────────────────
# MANUAL CONTENT WRAPPING
# Digunakan untuk konten yang ditulis manual
# dan disimpan sebagai body HTML di staging.
# ─────────────────────────────────────────────

def wrap_article_html(body_html: str, slug: str) -> str:
    """
    Bungkus body artikel ke full HTML page.
    Input : body HTML saja (mulai dari <h1>, boleh diawali
            <meta name="cluster"> dan/atau <meta name="description">
            sebelum <h1>)
    Output: full HTML page siap publish
    """
    # Ekstrak cluster_id
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

    # Fallback: gunakan judul jika Claude tidak menulis meta description
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

    # ── FAQPage JSON-LD schema ────────────────────────────────────────────────
    faq_schema = ""
    faq_pairs = re.findall(
        r'<summary[^>]*>(.*?)</summary>.*?<div[^>]*class=["\']faq-answer["\'][^>]*>(.*?)</div>',
        body_html, re.IGNORECASE | re.DOTALL
    )
    if faq_pairs:
        import json as _json
        qa_list = []
        for q, a in faq_pairs:
            q_clean = re.sub(r'<[^>]+>', '', q).strip()
            a_clean = re.sub(r'<[^>]+>', '', a).strip()
            a_clean = re.sub(r'\s+', ' ', a_clean)
            if q_clean and a_clean:
                qa_list.append({
                    "@type": "Question",
                    "name": q_clean,
                    "acceptedAnswer": {"@type": "Answer", "text": a_clean}
                })
        if qa_list:
            schema_obj = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": qa_list
            }
            faq_schema = (
                '\n  <script type="application/ld+json">\n  '
                + _json.dumps(schema_obj, ensure_ascii=False, indent=2)
                .replace('\n', '\n  ')
                + '\n  </script>'
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_clean} — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="{meta_desc}">
  {cluster_meta}
  <link rel="canonical" href="{tool_url}">
  <link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
  <link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
  <link rel="shortcut icon" href="/favicon/favicon.ico" />
  <link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
  <link rel="manifest" href="/favicon/site.webmanifest" />
  {_FONT}
  <style>
{_BASE_CSS}
{_NAV_CSS}

    /* ── LAYOUT ── */
    .container {{ max-width: 680px; margin: 0 auto; padding: 48px 24px 80px; }}

    /* ── TYPOGRAPHY ── */
    h1 {{
      font-size: clamp(1.75rem, 4vw, 2.25rem);
      font-weight: 700;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 1.0625rem;
      margin-bottom: 40px;
      line-height: 1.6;
    }}

    /* ── CARD ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 32px;
      margin-bottom: 24px;
    }}
    .card h2 {{
      font-size: .875rem;
      font-weight: 600;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 24px;
      border-bottom: 2px solid var(--text);
      padding-bottom: 8px;
    }}

    /* ── INPUTS (UTILITARIAN BRUTALISM) ── */
    .input-group {{ margin-bottom: 20px; }}
    .input-group:last-child {{ margin-bottom: 0; }}
    label {{
      display: block;
      font-size: .875rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 8px;
    }}
    .input-wrapper {{ position: relative; }}
    .input-prefix {{
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
      font-size: 1rem;
      pointer-events: none;
      font-weight: 500;
    }}
    input[type="number"] {{
      width: 100%;
      padding: 12px 14px 12px 32px;
      border: 1px solid var(--border);
      border-radius: var(--r);
      font-size: 16px !important; /* CRITICAL: Mencegah iOS Auto-Zoom */
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
      color: var(--text);
      background: var(--bg);
      transition: border-color .15s, outline .15s;
      -moz-appearance: textfield;
    }}
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button {{ -webkit-appearance: none; }}
    input[type="number"]:focus {{
      outline: 2px solid var(--accent);
      outline-offset: -1px;
      border-color: var(--accent);
      background: var(--surface);
    }}
    input[type="number"].error-input {{ border-color: var(--danger); }}
    .error-msg {{
      color: var(--danger);
      font-size: .8125rem;
      margin-top: 6px;
      display: none;
    }}

    /* ── RESULT (HIGH CONTRAST) ── */
    .result-card {{
      background: var(--surface);
      border: 2px solid var(--text);
      border-radius: var(--r);
      padding: 32px;
      margin-bottom: 24px;
    }}
    .result-label {{
      font-size: .8125rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 8px;
    }}
    .result-number {{
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
      font-size: clamp(1.75rem, 6vw, 4rem);
      font-weight: 700;
      color: var(--text);
      line-height: 1;
      letter-spacing: -.05em;
      margin-bottom: 8px;
      overflow-wrap: break-word;
      word-break: break-all;
    }}
    .result-unit {{
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
      font-size: 1rem;
      color: var(--muted);
      margin-bottom: 24px;
    }}
    .interpretation {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-left: 4px solid var(--text);
      border-radius: 0 var(--r) var(--r) 0;
      padding: 16px 20px;
      font-size: 0.9375rem;
      color: var(--text);
      line-height: 1.6;
    }}
    .interpretation.danger {{ border-color: var(--danger); background: var(--danger-bg); }}
    .interpretation.warning {{ border-color: var(--warning); background: var(--warning-bg); }}
    .interpretation.healthy {{ border-color: var(--success); background: var(--success-bg); }}
    .secondary-result {{
      margin-top: 16px;
      font-size: .875rem;
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
      color: var(--muted);
    }}

    /* ── FORMULA BOX ── */
    .formula-box {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 24px;
      margin-bottom: 24px;
    }}
    .formula-box h3 {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 12px;
    }}
    .formula-box p {{
      font-size: 0.875rem;
      color: var(--text);
      line-height: 1.7;
      font-family: "SFMono-Regular", Consolas, "JetBrains Mono", monospace;
    }}

    /* ── AFFILIATE BOX ── */
    .affiliate-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-left: 4px solid var(--success);
      border-radius: 0 var(--r) var(--r) 0;
      padding: 20px 24px;
      margin-bottom: 24px;
      font-size: 0.9375rem;
      color: var(--text);
      line-height: 1.6;
    }}
    .affiliate-box a {{
      color: var(--success);
      font-weight: 600;
      text-decoration: underline;
      text-decoration-color: rgba(16,185,129,.4);
    }}
    .affiliate-box a:hover {{ color: #059669; text-decoration-color: #059669; }}

    /* ── RELATED LINK ── */
    .related-link {{ font-size: .9375rem; color: var(--muted); padding: 16px 0; }}
    .related-link a {{ color: var(--accent); text-decoration: underline; font-weight: 500; }}
    .related-link a:hover {{ color: var(--accent-h); }}

    /* ── FAQ ── */
    .faq {{ margin-top: 48px; }}
    .faq h3 {{
      font-size: 1.25rem; font-weight: 700; color: var(--text);
      letter-spacing: -.02em; margin-bottom: 20px;
      border-bottom: 2px solid var(--text); padding-bottom: 8px;
    }}
    .faq details {{
      border: 1px solid var(--border);
      border-radius: var(--r);
      margin-bottom: 12px;
      background: var(--surface);
    }}
    .faq summary {{
      padding: 16px 20px; font-size: 1rem; font-weight: 600; color: var(--text);
      cursor: pointer; list-style: none; display: flex;
      justify-content: space-between; align-items: center;
      min-height: 44px;
    }}
    .faq summary::-webkit-details-marker {{ display: none; }}
    .faq summary::after {{
      content: '+'; font-size: 1.2rem; color: var(--muted);
      font-weight: 300; flex-shrink: 0; margin-left: 16px; font-family: monospace;
    }}
    .faq details[open] > summary::after {{ content: '−'; }}
    .faq details[open] > summary {{ border-bottom: 1px solid var(--border); background: var(--bg); }}
    .faq .faq-answer {{
      padding: 20px; font-size: 0.9375rem; color: var(--muted);
      line-height: 1.7; background: var(--surface);
    }}

{_RELATED_CSS}
{_FOOTER_CSS}

    @media (max-width: 640px) {{
      .container {{ padding: 32px 16px 64px; }}
      .card, .result-card, .formula-box, .affiliate-box {{ padding: 20px; }}
    }}
  </style>
  {_ANALYTICS}{faq_schema}
</head>
<body>

<nav class="site-nav">
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
<div id="related-content" class="related-content"></div>
</div>

{_FOOTER_HTML}

{_RELATED_JS}

{_AFFILIATE_TRACKER_JS}

</body>
</html>"""

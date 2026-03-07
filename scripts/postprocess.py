"""
postprocess.py
Validasi dan format output dari AI sebelum dipublish.
Artikel di-convert dari Markdown ke HTML lengkap sebelum dipublish.
"""
import re
from datetime import datetime


# ─────────────────────────────────────────────
# MARKDOWN → HTML CONVERTER (pure Python)
# ─────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    """
    Convert markdown ke HTML.
    Menangani: headings, bold, italic, inline code,
    unordered lists, ordered lists, blockquotes,
    horizontal rules, dan paragraphs.
    """
    lines   = md.split("\n")
    html    = []
    in_ul   = False
    in_ol   = False
    in_p    = False
    p_lines = []

    def flush_p():
        nonlocal in_p, p_lines
        if p_lines:
            content = " ".join(p_lines).strip()
            if content:
                html.append(f"<p>{content}</p>")
        in_p    = False
        p_lines = []

    def flush_ul():
        nonlocal in_ul
        if in_ul:
            html.append("</ul>")
            in_ul = False

    def flush_ol():
        nonlocal in_ol
        if in_ol:
            html.append("</ol>")
            in_ol = False

    def inline(text: str) -> str:
        """Apply inline formatting."""
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_p(); flush_ul(); flush_ol()
            continue

        if stripped.startswith("# "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<h1>{inline(stripped[2:])}</h1>')
            continue
        if stripped.startswith("## "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<h2>{inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith("### "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<h3>{inline(stripped[4:])}</h3>')
            continue
        if stripped.startswith("#### "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<h4>{inline(stripped[5:])}</h4>')
            continue

        if re.match(r'^[-*_]{3,}\$', stripped):
            flush_p(); flush_ul(); flush_ol()
            html.append('<hr>')
            continue

        if stripped.startswith("> "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<blockquote>{inline(stripped[2:])}</blockquote>')
            continue

        ul_match = re.match(r'^[-*+] (.+)', stripped)
        if ul_match:
            flush_p(); flush_ol()
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{inline(ul_match.group(1))}</li>")
            continue

        ol_match = re.match(r'^\d+\. (.+)', stripped)
        if ol_match:
            flush_p(); flush_ul()
            if not in_ol:
                html.append("<ol>")
                in_ol = True
            html.append(f"<li>{inline(ol_match.group(1))}</li>")
            continue

        flush_ul(); flush_ol()
        in_p = True
        p_lines.append(inline(stripped))

    flush_p(); flush_ul(); flush_ol()
    return "\n".join(html)


def _extract_frontmatter(content: str) -> tuple:
    """
    Pisahkan YAML frontmatter dari isi artikel.
    Return: (dict frontmatter, string body)
    """
    fm   = {}
    body = content

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        for line in match.group(1).split("\n"):
            kv = re.match(r'^(\w+):\s*"?([^"]*)"?\s*\$', line.strip())
            if kv:
                fm[kv.group(1)] = kv.group(2).strip()
        body = content[match.end():]

    return fm, body


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
    <div class="footer-brand">SaaS Tools for Bootstrapped Founders</div>
    <div class="footer-links">
      <a href="/">Home</a>
      <a href="/articles/">Articles</a>
      <a href="/tools/">Tools</a>
    </div>
    <div class="footer-copy">Free tools and analysis for independent SaaS founders.</div>
  </div>
</footer>"""

_FOOTER_CSS = """
  footer {
    border-top: 1px solid var(--border);
    padding: 48px 20px;
  }
  .footer-inner {
    max-width: 720px;
    margin: 0 auto;
    text-align: center;
  }
  .footer-brand {
    font-size: .8rem;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 16px;
    letter-spacing: .02em;
    text-transform: uppercase;
  }
  .footer-links {
    display: flex;
    justify-content: center;
    gap: 28px;
    margin-bottom: 16px;
  }
  .footer-links a {
    font-size: .8rem;
    color: var(--muted);
    text-decoration: none;
    transition: color .15s;
  }
  .footer-links a:hover { color: var(--accent); }
  .footer-copy { font-size: .75rem; color: var(--subtle); }
"""

_TOOL_CSS = ""  # CSS disediakan oleh wrap_tool_html — tidak dipakai standalone

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
    }}
    .related-heading:first-child {{ margin-top: 0; }}
    .related-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .related-list li a {{
      font-size: .875rem;
      color: var(--accent);
      text-decoration: none;
      display: block;
      padding: 8px 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 7px;
      transition: border-color .15s;
    }}
    .related-list li a:hover {{
      border-color: var(--accent);
    }}
"""

_RELATED_JS = """<script>
(function() {{
  var meta    = document.querySelector('meta[name="cluster"]');
  var cluster = meta ? meta.getAttribute('content') : '';
  if (!cluster) return;
  var parts       = window.location.pathname.split('/').filter(Boolean);
  var currentSlug = (parts[parts.length - 1] || '').replace('.html', '');
  fetch('/content-index.json')
    .then(function(r) {{ return r.json(); }})
    .then(function(idx) {{
      var articles = (idx.articles || [])
        .filter(function(a) {{ return a.cluster === cluster && a.slug !== currentSlug; }})
        .slice(0, 3);
      var tools = (idx.tools || [])
        .filter(function(t) {{ return t.cluster === cluster && t.slug !== currentSlug; }})
        .slice(0, 2);
      var html = '';
      if (articles.length) {{
        html += '<h3 class="related-heading">Related Articles</h3>'
              + '<ul class="related-list">';
        articles.forEach(function(a) {{
          html += '<li><a href="/articles/' + a.slug + '">' + a.title + '</a></li>';
        }});
        html += '</ul>';
      }}
      if (tools.length) {{
        html += '<h3 class="related-heading">Related Tools</h3>'
              + '<ul class="related-list">';
        tools.forEach(function(t) {{
          html += '<li><a href="/tools/' + t.slug + '">' + t.title + '</a></li>';
        }});
        html += '</ul>';
      }}
      if (html) {{
        var el = document.getElementById('related-content');
        if (el) el.innerHTML = html;
      }}
    }})
    .catch(function() {{}});
}})();
</script>"""


# ─────────────────────────────────────────────
# ARTICLE TEMPLATE
# ─────────────────────────────────────────────

def _build_article_html(fm: dict, body_html: str,
                        slug: str, date_str: str,
                        cluster_id: str = "") -> str:
    """
    Bungkus article body HTML ke dalam full HTML page.
    Menyertakan: navigasi, metadata, share buttons, komentar Giscus,
    dan related content (artikel + tools dalam cluster yang sama).
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
        f'<span class="meta-divider">·</span>'
        f'<span class="meta-tag">{keyword}</span>'
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
  <meta property="og:site_name" content="SaaS Tools for Bootstrapped Founders">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <link rel="canonical" href="{article_url}">
  {_FONT}
  <style>
{{_BASE_CSS}}
{{_NAV_CSS}}

    /* ── LAYOUT ── */
    .container {{
      max-width: 720px;
      margin: 0 auto;
      padding: 48px 20px 80px;
    }}

    /* ── ARTICLE HEADER ── */
    .article-header {{ margin-bottom: 40px; }}
    .article-header h1 {{
      font-size: clamp(1.5rem, 4vw, 2.1rem);
      font-weight: 700;
      line-height: 1.2;
      letter-spacing: -.03em;
      color: var(--text);
      margin-bottom: 16px;
    }}
    .article-meta {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }}
    .meta-item {{
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: .8rem;
      color: var(--muted);
    }}
    .meta-tag {{
      display: inline-block;
      background: var(--accent-light);
      color: var(--accent);
      font-size: .72rem;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 20px;
      letter-spacing: .02em;
    }}
    .meta-divider {{ color: var(--border); font-size: .7rem; }}

    /* ── ARTICLE BODY ── */
    .article-body {{
      font-size: 1.025rem;
      line-height: 1.75;
      margin-bottom: 56px;
    }}
    .article-body h2 {{
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -.02em;
      color: var(--text);
      margin: 44px 0 14px;
      padding-top: 44px;
      border-top: 1px solid var(--border);
    }}
    .article-body h2:first-child {{
      margin-top: 0; padding-top: 0; border-top: none;
    }}
    .article-body h3 {{
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--text);
      margin: 28px 0 10px;
    }}
    .article-body h4 {{
      font-size: .95rem;
      font-weight: 600;
      color: var(--text);
      margin: 22px 0 8px;
    }}
    .article-body p {{ margin-bottom: 20px; }}
    .article-body p:last-child {{ margin-bottom: 0; }}
    .article-body ul, .article-body ol {{
      margin: 0 0 20px 20px;
    }}
    .article-body li {{ margin-bottom: 6px; }}
    .article-body blockquote {{
      border-left: 3px solid var(--accent);
      background: var(--accent-light);
      padding: 14px 20px;
      margin: 24px 0;
      border-radius: 0 var(--r) var(--r) 0;
      color: var(--text);
      font-style: italic;
    }}
    .article-body code {{
      background: #f4f4f5;
      border: 1px solid var(--border);
      padding: 2px 6px;
      border-radius: 5px;
      font-size: .87em;
      font-family: 'SFMono-Regular', Consolas, monospace;
      color: var(--accent);
    }}
    .article-body hr {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 36px 0;
    }}
    .article-body strong {{ font-weight: 600; color: var(--text); }}
    .article-body a {{
      color: var(--accent);
      text-decoration: underline;
      text-decoration-color: rgba(79,70,229,.3);
    }}
    .article-body a:hover {{
      color: var(--accent-h);
      text-decoration-color: var(--accent-h);
    }}

    /* ── SHARE ── */
    .share-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 24px;
      margin-bottom: 48px;
    }}
    .share-label {{
      font-size: .75rem;
      font-weight: 600;
      color: var(--subtle);
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 14px;
    }}
    .share-buttons {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .share-btn {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: .82rem;
      font-weight: 500;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all .15s;
      font-family: inherit;
    }}
    .share-btn.x-btn {{ background: #000; color: white; }}
    .share-btn.x-btn:hover {{ background: #111; color: white; }}
    .share-btn.li-btn {{ background: #0a66c2; color: white; }}
    .share-btn.li-btn:hover {{ background: #004182; color: white; }}
    .share-btn.copy-btn {{
      background: var(--bg);
      color: var(--text);
      border-color: var(--border);
    }}
    .share-btn.copy-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .share-btn.copy-btn.copied {{
      background: var(--success-bg);
      color: var(--success);
      border-color: var(--success);
    }}

    /* ── COMMENTS ── */
    .comments-box {{ margin-bottom: 48px; }}
    .comments-box h2 {{
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }}

{_RELATED_CSS}
{{_FOOTER_CSS}}

    @media (max-width: 600px) {{
      .container {{ padding: 32px 16px 60px; }}
      .article-header h1 {{ font-size: 1.4rem; }}
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

<div class="container">

  <header class="article-header">
    <h1>{title}</h1>
    <div class="article-meta">
      <span class="meta-item">
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
      <span class="meta-divider">·</span>
      <span class="meta-item">
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

  <div id="related-content"></div>

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

</div>

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

</body>
</html>"""


# ─────────────────────────────────────────────
# ARTICLE — validate & format
# ─────────────────────────────────────────────

def validate_article(content: str, task_config: dict,
                     topic_info: dict) -> dict:
    """
    Validasi artikel yang di-generate (sebelum HTML conversion).
    Return: dict dengan keys: valid, issues, word_count, content
    """
    issues     = []
    min_words  = task_config.get("min_words", 400)
    word_count = len(content.split())

    if word_count < min_words:
        issues.append(f"Too short: {word_count} words (minimum: {min_words})")

    if not re.search(r'^# .+', content, re.MULTILINE):
        issues.append("Missing H1 heading")

    h2_count = len(re.findall(r'^## .+', content, re.MULTILINE))
    if h2_count < 2:
        issues.append(f"Too few H2 headings: {h2_count} (minimum: 2)")

    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', content)
    if placeholders:
        issues.append(f"Unfilled placeholders: {placeholders}")

    keywords   = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict)
        else topic_info.get("target_keyword", "")
    )
    if primary_kw and primary_kw.lower() not in content.lower():
        issues.append(f"Primary keyword not found: '{primary_kw}'")

    return {
        "valid":      len(issues) == 0,
        "issues":     issues,
        "word_count": word_count,
        "content":    content
    }


def format_article(content: str, topic_info: dict) -> tuple:
    """
    Format artikel:
    1. Fix frontmatter (date, word_count, slug)
    2. Convert Markdown → full HTML page
    3. Generate nama file .html

    Return: tuple (html_content, filename)
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    keywords   = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict) else ""
    )
    source   = primary_kw if primary_kw else topic_info.get("topic", "untitled")
    slug     = re.sub(r'[^a-z0-9]+', '-', source.lower()).strip('-').rstrip('-')
    filename = f"{slug}.html"

    word_count = len(content.split())

    content = content.replace("{{DATE}}", date_str)
    content = content.replace("{{SLUG}}", slug)
    content = content.replace("{{WORD_COUNT}}", str(word_count))

    content = re.sub(r'date: "[^"]*"',       f'date: "{date_str}"', content)
    content = re.sub(r'word_count: \S+',     f'word_count: {word_count}', content)
    content = re.sub(r'slug: "[^"]*"',       f'slug: "{slug}"', content)

    fm, body_md = _extract_frontmatter(content)
    body_html   = _md_to_html(body_md)
    full_html   = _build_article_html(fm, body_html, slug, date_str)

    return full_html, filename


# ─────────────────────────────────────────────
# TOOL — validate & format
# ─────────────────────────────────────────────

def validate_tool(content: str) -> dict:
    """
    Validasi HTML tool yang sudah di-assemble oleh format_tool.
    Return: dict dengan keys: valid, issues, content
    """
    issues = []

    if "<script" not in content.lower():
        issues.append("No JavaScript found")
    if "<input" not in content.lower():
        issues.append("No input elements found")
    if 'id="result-primary"' not in content:
        issues.append("No result-primary element found")
    if "function calculate" not in content:
        issues.append("No calculate() function found")

    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', content)
    if placeholders:
        issues.append(f"Unfilled placeholders: {placeholders}")

    return {
        "valid":   len(issues) == 0,
        "issues":  issues,
        "content": content
    }


def format_tool(parts: dict, template: str,
                topic_info: dict) -> tuple:
    """
    Inject bagian dinamis dari AI ke dalam HTML template.
    parts    : dict dari generate_tool_parts()
    template : isi file HTML template kalkulator
    Return   : tuple (assembled_html, filename)

    CATATAN v4.0: Fungsi ini adalah sisa dari sistem lama (v3.x).
    Di v4.0, konten tool ditulis manual dan dibungkus dengan
    wrap_tool_html(). Fungsi ini tidak dipanggil oleh run_pipeline.py.
    """
    slug      = topic_info.get("tool_slug", "untitled-tool")
    tool_name = topic_info.get("tool_name", "Calculator")
    filename  = f"{slug}.html"

    linking            = topic_info.get("linking", {}) or {}
    related_article_id = linking.get("link_to_article", "")
    if related_article_id:
        related_url   = f"/articles/{related_article_id}"
        related_title = "Related Article"
    else:
        related_url   = "/articles/"
        related_title = "More SaaS Resources"

    content = template
    content = content.replace("{{TOOL_NAME}}",             tool_name)
    content = content.replace("{{TOOL_SLUG}}",             slug)
    content = content.replace("{{RELATED_ARTICLE_LINK}}", related_url)
    content = content.replace("{{RELATED_ARTICLE_TITLE}}", related_title)
    content = content.replace("{{TOOL_SUBTITLE}}",         parts.get("tool_subtitle", ""))
    content = content.replace("{{META_DESCRIPTION}}",      parts.get("meta_description", ""))
    content = content.replace("{{PRIMARY_UNIT}}",          parts.get("primary_unit", ""))
    content = content.replace("{{FORMULA_COMMENT}}",       parts.get("formula_comment", ""))
    content = content.replace("{{INPUT_FIELDS}}",          parts.get("input_fields_html", ""))
    content = content.replace("{{EXAMPLE_VALUES_INIT}}",   parts.get("example_values_init", ""))
    content = content.replace("{{CALCULATOR_JAVASCRIPT}}", parts.get("calculator_javascript", ""))
    content = content.replace("{{FORMULA_BOX}}",           parts.get("formula_box_html", ""))
    content = content.replace("{{AFFILIATE_BOX}}",         parts.get("affiliate_box_html", ""))

    return content, filename


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

    Judul diambil otomatis dari tag <h1> pertama.
    Cluster diambil dari <meta name="cluster"> jika ada.
    Meta description diambil dari <meta name="description"> jika ada,
    fallback ke judul jika tidak ada.
    Kedua meta tag dihapus dari body sebelum render.
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
{{_BASE_CSS}}
{{_NAV_CSS}}

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
{{_FOOTER_CSS}}

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

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
        # Bold + italic
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Inline code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    for line in lines:
        stripped = line.strip()

        # Blank line — flush paragraph buffer
        if not stripped:
            flush_p()
            flush_ul()
            flush_ol()
            continue

        # Headings
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

        # Horizontal rule
        if re.match(r'^[-*_]{3,}$', stripped):
            flush_p(); flush_ul(); flush_ol()
            html.append('<hr>')
            continue

        # Blockquote
        if stripped.startswith("> "):
            flush_p(); flush_ul(); flush_ol()
            html.append(f'<blockquote>{inline(stripped[2:])}</blockquote>')
            continue

        # Unordered list
        ul_match = re.match(r'^[-*+] (.+)', stripped)
        if ul_match:
            flush_p()
            flush_ol()
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{inline(ul_match.group(1))}</li>")
            continue

        # Ordered list
        ol_match = re.match(r'^\d+\. (.+)', stripped)
        if ol_match:
            flush_p()
            flush_ul()
            if not in_ol:
                html.append("<ol>")
                in_ol = True
            html.append(f"<li>{inline(ol_match.group(1))}</li>")
            continue

        # Regular paragraph line
        flush_ul()
        flush_ol()
        in_p = True
        p_lines.append(inline(stripped))

    flush_p()
    flush_ul()
    flush_ol()

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
            kv = re.match(r'^(\w+):\s*"?([^"]*)"?\s*$', line.strip())
            if kv:
                fm[kv.group(1)] = kv.group(2).strip()
        body = content[match.end():]

    return fm, body


def _reading_time(text: str) -> int:
    """Estimasi waktu baca dalam menit (200 kata/menit)."""
    return max(1, round(len(text.split()) / 200))


def _build_article_html(fm: dict, body_html: str,
                        slug: str, date_str: str) -> str:
    """
    Bungkus article body HTML ke dalam full HTML page.
    Menyertakan: navigasi, metadata, share buttons, komentar Giscus.
    """
    title       = fm.get("title", slug.replace("-", " ").title())
    keyword     = fm.get("primary_keyword", "")
    word_count  = fm.get("word_count", "")
    read_time   = _reading_time(body_html)
    site_url    = "https://saas.blogtrick.eu.org"
    article_url = f"{site_url}/articles/{slug}"

    # Format tanggal tampilan: "March 1, 2026"
    try:
        dt          = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%B %-d, %Y")
    except Exception:
        display_date = date_str

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SaaS Tools for Bootstrapped Founders</title>
  <meta name="description" content="{title}">
  {f'<meta name="keywords" content="{keyword}">' if keyword else ''}
  <meta property="og:title" content="{title}">
  <meta property="og:url" content="{article_url}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="SaaS Tools for Bootstrapped Founders">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <link rel="canonical" href="{article_url}">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f8fafc;
      color: #1e293b;
      line-height: 1.7;
    }}

    /* ── NAV ── */
    nav {{
      background: white;
      border-bottom: 1px solid #e2e8f0;
      padding: 0 16px;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .nav-inner {{
      max-width: 760px;
      margin: 0 auto;
      height: 52px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .nav-left a {{
      font-size: 0.875rem;
      color: #6366f1;
      text-decoration: none;
      font-weight: 500;
    }}
    .nav-left a:hover {{ text-decoration: underline; }}
    .nav-brand {{
      font-size: 0.8rem;
      color: #94a3b8;
      font-weight: 500;
    }}

    /* ── LAYOUT ── */
    .container {{
      max-width: 760px;
      margin: 0 auto;
      padding: 40px 16px 80px;
    }}

    /* ── ARTICLE HEADER ── */
    .article-header {{ margin-bottom: 32px; }}
    .article-header h1 {{
      font-size: 1.9rem;
      font-weight: 800;
      line-height: 1.25;
      color: #0f172a;
      margin-bottom: 16px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      font-size: 0.82rem;
      color: #64748b;
    }}
    .meta span {{ display: flex; align-items: center; gap: 4px; }}

    /* ── ARTICLE BODY ── */
    .article-body {{ margin-bottom: 48px; }}
    .article-body h2 {{
      font-size: 1.35rem;
      font-weight: 700;
      color: #0f172a;
      margin: 36px 0 12px;
      padding-top: 8px;
      border-top: 2px solid #e2e8f0;
    }}
    .article-body h3 {{
      font-size: 1.1rem;
      font-weight: 600;
      color: #1e293b;
      margin: 24px 0 8px;
    }}
    .article-body h4 {{
      font-size: 1rem;
      font-weight: 600;
      color: #374151;
      margin: 20px 0 6px;
    }}
    .article-body p {{
      margin-bottom: 18px;
      font-size: 1.02rem;
    }}
    .article-body ul, .article-body ol {{
      margin: 0 0 18px 24px;
    }}
    .article-body li {{ margin-bottom: 6px; font-size: 1.02rem; }}
    .article-body blockquote {{
      border-left: 4px solid #6366f1;
      background: #f1f5f9;
      padding: 12px 16px;
      margin: 20px 0;
      border-radius: 0 8px 8px 0;
      color: #374151;
      font-style: italic;
    }}
    .article-body code {{
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.88em;
      font-family: 'SFMono-Regular', Consolas, monospace;
    }}
    .article-body hr {{
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 32px 0;
    }}
    .article-body strong {{ font-weight: 600; color: #0f172a; }}

    /* ── SHARE ── */
    .share-section {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 40px;
    }}
    .share-section h3 {{
      font-size: 0.85rem;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 14px;
    }}
    .share-buttons {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .share-btn {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.875rem;
      font-weight: 500;
      text-decoration: none;
      cursor: pointer;
      border: none;
      transition: opacity 0.15s;
    }}
    .share-btn:hover {{ opacity: 0.85; }}
    .share-btn.twitter  {{ background: #000; color: white; }}
    .share-btn.linkedin {{ background: #0077b5; color: white; }}
    .share-btn.copy     {{ background: #f1f5f9; color: #374151;
                           border: 1px solid #e2e8f0; }}
    .share-btn.copy.copied {{ background: #d1fae5; color: #065f46;
                              border-color: #6ee7b7; }}

    /* ── COMMENTS (Giscus) ── */
    .comments-section {{
      margin-bottom: 40px;
    }}
    .comments-section h2 {{
      font-size: 1.2rem;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 20px;
    }}

    /* ── FOOTER ── */
    footer {{
      border-top: 1px solid #e2e8f0;
      padding: 24px 16px;
      text-align: center;
    }}
    .footer-inner {{
      max-width: 760px;
      margin: 0 auto;
      font-size: 0.8rem;
      color: #94a3b8;
    }}
    .footer-inner a {{ color: #6366f1; text-decoration: none; }}
    .footer-inner a:hover {{ text-decoration: underline; }}

    @media (max-width: 600px) {{
      .article-header h1 {{ font-size: 1.5rem; }}
      .container {{ padding: 24px 16px 60px; }}
    }}
  </style>
</head>
<body>

  <!-- NAV -->
  <nav>
    <div class="nav-inner">
      <div class="nav-left">
        <a href="/articles/">← All Articles</a>
      </div>
      <div class="nav-brand">
        <a href="/" style="color:#94a3b8;text-decoration:none;">
          SaaS Tools for Bootstrapped Founders
        </a>
      </div>
    </div>
  </nav>

  <!-- MAIN -->
  <div class="container">

    <!-- HEADER -->
    <header class="article-header">
      <h1>{title}</h1>
      <div class="meta">
        <span>📅 {display_date}</span>
        <span>⏱ {read_time} min read</span>
        {f'<span>🏷 {keyword}</span>' if keyword else ''}
      </div>
    </header>

    <!-- BODY -->
    <article class="article-body">
      {body_html}
    </article>

    <!-- SHARE -->
    <div class="share-section">
      <h3>Share this article</h3>
      <div class="share-buttons">
        <a class="share-btn twitter"
           href="https://twitter.com/intent/tweet?text={title.replace(' ', '%20')}&url={article_url}"
           target="_blank" rel="noopener">
          𝕏 Share on X
        </a>
        <a class="share-btn linkedin"
           href="https://www.linkedin.com/sharing/share-offsite/?url={article_url}"
           target="_blank" rel="noopener">
          in Share on LinkedIn
        </a>
        <button class="share-btn copy" id="copy-btn"
                onclick="copyLink()">
          🔗 Copy Link
        </button>
      </div>
    </div>

    <!-- COMMENTS -->
    <div class="comments-section">
      <h2>Comments</h2>
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
        <p style="color:#64748b;font-size:0.9rem;">
          Enable JavaScript to load comments.
        </p>
      </noscript>
    </div>

  </div><!-- /.container -->

  <!-- FOOTER -->
  <footer>
    <div class="footer-inner">
      <a href="/">Home</a> ·
      <a href="/articles/">Articles</a> ·
      <a href="/tools/">Tools</a>
      <br><br>
      Built for bootstrapped SaaS founders.
    </div>
  </footer>

  <script>
    function copyLink() {{
      navigator.clipboard.writeText("{article_url}").then(function() {{
        var btn = document.getElementById("copy-btn");
        btn.textContent = "✓ Copied!";
        btn.classList.add("copied");
        setTimeout(function() {{
          btn.textContent = "🔗 Copy Link";
          btn.classList.remove("copied");
        }}, 2000);
      }});
    }}
  </script>

</body>
</html>"""


# ─────────────────────────────────────────────
# ARTICLE
# ─────────────────────────────────────────────

def validate_article(content: str, task_config: dict,
                     topic_info: dict) -> dict:
    """
    Validasi artikel yang di-generate (sebelum HTML conversion).
    Return: dict dengan keys: valid, issues, word_count, content
    """
    issues    = []
    min_words = task_config.get("min_words", 400)
    word_count = len(content.split())

    if word_count < min_words:
        issues.append(
            f"Too short: {word_count} words (minimum: {min_words})"
        )

    if not re.search(r'^# .+', content, re.MULTILINE):
        issues.append("Missing H1 heading")

    h2_count = len(re.findall(r'^## .+', content, re.MULTILINE))
    if h2_count < 2:
        issues.append(f"Too few H2 headings: {h2_count} (minimum: 2)")

    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', content)
    if placeholders:
        issues.append(f"Unfilled placeholders: {placeholders}")

    keywords  = topic_info.get("keywords", {})
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
    3. Generate nama file .html (bukan .md)

    Return: tuple (html_content, filename)
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    topic    = topic_info.get("topic", "untitled")
    slug     = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:55].rstrip('-')
    filename = f"{date_str}-{slug}.html"

    word_count = len(content.split())

    # Isi placeholder yang mungkin ada di body
    content = content.replace("{{DATE}}", date_str)
    content = content.replace("{{SLUG}}", slug)
    content = content.replace("{{WORD_COUNT}}", str(word_count))

    # Override frontmatter yang mungkin diisi salah oleh AI
    content = re.sub(r'date: "[^"]*"',
                     f'date: "{date_str}"', content)
    content = re.sub(r'word_count: \S+',
                     f'word_count: {word_count}', content)
    content = re.sub(r'slug: "[^"]*"',
                     f'slug: "{slug}"', content)

    # Pisahkan frontmatter dari body
    fm, body_md = _extract_frontmatter(content)

    # Convert body markdown ke HTML
    body_html = _md_to_html(body_md)

    # Bungkus ke full HTML page
    full_html = _build_article_html(fm, body_html, slug, date_str)

    return full_html, filename


# ─────────────────────────────────────────────
# TOOL
# ─────────────────────────────────────────────

def validate_tool(content: str) -> dict:
    """
    Validasi HTML tool yang sudah di-assemble oleh format_tool.
    Dipanggil SETELAH format_tool.
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
    parts    : dict dari generate_tool_parts() di ai_caller.py
    template : isi file templates/calculator.html
    Return   : tuple (assembled_html, filename)
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

    # Nilai dari topic_info (system-controlled)
    content = content.replace("{{TOOL_NAME}}",            tool_name)
    content = content.replace("{{TOOL_SLUG}}",            slug)
    content = content.replace("{{RELATED_ARTICLE_LINK}}", related_url)
    content = content.replace("{{RELATED_ARTICLE_TITLE}}", related_title)

    # Nilai dari AI (parts dict)
    content = content.replace("{{TOOL_SUBTITLE}}",
                               parts.get("tool_subtitle", ""))
    content = content.replace("{{META_DESCRIPTION}}",
                               parts.get("meta_description", ""))
    content = content.replace("{{PRIMARY_UNIT}}",
                               parts.get("primary_unit", ""))
    content = content.replace("{{FORMULA_COMMENT}}",
                               parts.get("formula_comment", ""))
    content = content.replace("{{INPUT_FIELDS}}",
                               parts.get("input_fields_html", ""))
    content = content.replace("{{EXAMPLE_VALUES_INIT}}",
                               parts.get("example_values_init", ""))
    content = content.replace("{{CALCULATOR_JAVASCRIPT}}",
                               parts.get("calculator_javascript", ""))
    content = content.replace("{{FORMULA_BOX}}",
                               parts.get("formula_box_html", ""))
    content = content.replace("{{AFFILIATE_BOX}}",
                               parts.get("affiliate_box_html", ""))

    return content, filename

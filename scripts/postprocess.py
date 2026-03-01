"""
postprocess.py
Validasi dan format output dari AI sebelum dipublish.
"""
import re
from datetime import datetime


# ─────────────────────────────────────────────
# ARTICLE
# ─────────────────────────────────────────────

def validate_article(content: str, task_config: dict,
                     topic_info: dict) -> dict:
    """
    Validasi artikel yang di-generate.
    Return: dict dengan keys: valid, issues, word_count, content
    """
    issues = []
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

    keywords = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict)
        else topic_info.get("target_keyword", "")
    )
    if primary_kw and primary_kw.lower() not in content.lower():
        issues.append(f"Primary keyword not found: '{primary_kw}'")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "word_count": word_count,
        "content": content
    }


def format_article(content: str, topic_info: dict) -> tuple:
    """
    Format artikel dan generate nama file.
    Slug dibatasi 55 chars (bukan 60) dan di-rstrip('-')
    agar tidak berakhir di tengah kata dengan trailing dash.
    Return: tuple (formatted_content, filename)
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    topic = topic_info.get("topic", "untitled")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:55].rstrip('-')
    filename = f"{date_str}-{slug}.md"

    word_count = len(content.split())
    content = content.replace("{{DATE}}", date_str)
    content = content.replace("{{SLUG}}", slug)
    content = content.replace("{{WORD_COUNT}}", str(word_count))

    # Override apapun yang AI isi di frontmatter — paksa nilai yang benar
    content = re.sub(r'date: "[^"]*"', f'date: "{date_str}"', content)
    content = re.sub(r'word_count: \S+', f'word_count: {word_count}', content)

    return content, filename


# ─────────────────────────────────────────────
# TOOL
# ─────────────────────────────────────────────

def validate_tool(content: str) -> dict:
    """
    Validasi HTML tool yang sudah di-assemble oleh format_tool.
    Dipanggil SETELAH format_tool, bukan sebelumnya.
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

    # Cek placeholder yang belum terisi
    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', content)
    if placeholders:
        issues.append(f"Unfilled placeholders: {placeholders}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "content": content
    }


def format_tool(parts: dict, template: str,
                topic_info: dict) -> tuple:
    """
    Inject bagian dinamis dari AI ke dalam HTML template.
    parts: dict dari generate_tool_parts() di ai_caller.py
    template: isi file templates/calculator.html
    Return: tuple (assembled_html, filename)
    """
    slug      = topic_info.get("tool_slug", "untitled-tool")
    tool_name = topic_info.get("tool_name", "Calculator")
    filename  = f"{slug}.html"

    # Ambil related article info dari linking jika ada
    linking = topic_info.get("linking", {}) or {}
    related_article_id = linking.get("link_to_article", "")
    if related_article_id:
        # Gunakan slug artikel sebagai URL relatif
        # Akan diperbaiki oleh sistem rendering situs ke URL penuh
        related_url   = f"/articles/{related_article_id}"
        related_title = f"Related Article"
    else:
        related_url   = "#"
        related_title = "More SaaS Resources"

    content = template

    # Inject nilai dari topic_info (bukan dari AI)
    content = content.replace("{{TOOL_NAME}}", tool_name)
    content = content.replace("{{TOOL_SLUG}}", slug)
    content = content.replace("{{RELATED_ARTICLE_LINK}}", related_url)
    content = content.replace("{{RELATED_ARTICLE_TITLE}}", related_title)

    # Inject nilai dari AI (parts dict)
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

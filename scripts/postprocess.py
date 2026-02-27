"""
postprocess.py
Validasi dan format output dari AI sebelum dipublish.
"""
import re
from datetime import datetime


def validate_article(content: str, task_config: dict,
                     topic_info: dict) -> dict:
    """
    Validasi artikel yang di-generate.
    Return: dict dengan keys: valid, issues, word_count, content
    """
    issues = []
    min_words = task_config.get("min_words", 600)
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
    Return: tuple (formatted_content, filename)
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    topic = topic_info.get("topic", "untitled")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:60]
    filename = f"{date_str}-{slug}.md"

    word_count = len(content.split())
    content = content.replace("{{DATE}}", date_str)
    content = content.replace("{{SLUG}}", slug)
    content = content.replace("{{WORD_COUNT}}", str(word_count))

    return content, filename


def validate_tool(content: str) -> dict:
    """
    Validasi HTML tools yang di-generate.
    Return: dict dengan keys: valid, issues, content
    """
    issues = []

    if "<script" not in content.lower():
        issues.append("No JavaScript found")

    if "<input" not in content.lower():
        issues.append("No input elements found")

    if ('id="result' not in content and
            'id="output' not in content):
        issues.append("No result/output element found")

    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', content)
    if placeholders:
        issues.append(f"Unfilled placeholders: {placeholders}")

    if "function calculate" not in content:
        issues.append("No calculate() function found")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "content": content
    }


def format_tool(content: str, topic_info: dict) -> tuple:
    """
    Format HTML tool dan generate nama file.
    Return: tuple (formatted_content, filename)
    """
    slug = topic_info.get("tool_slug", "untitled-tool")
    filename = f"{slug}.html"
    return content, filename

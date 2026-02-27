"""
ai_caller.py
Panggil Cloudflare Workers AI untuk generate konten.
Model: @cf/meta/llama-3.1-8b-instruct
"""
import os
import json
import urllib.request
import urllib.error

CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_API_TOKEN  = os.environ["CF_API_TOKEN"]
MODEL = "@cf/meta/llama-3.1-8b-instruct"


def call_ai(messages: list, max_tokens: int = 1024) -> str:
    """
    Kirim messages ke Cloudflare Workers AI.
    Return: teks hasil generate sebagai string.
    Raise Exception jika gagal.
    """
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT_ID}/ai/run/{MODEL}"
    )
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f"CF AI HTTP error {e.code}: {body}")

    if not data.get("success"):
        raise Exception(f"CF AI error: {data.get('errors')}")

    result = data.get("result", {}).get("response", "").strip()
    if not result:
        raise Exception("CF AI returned empty response")
    return result


def build_messages(task_config: dict, topic_info: dict,
                   rules: list, knowledge: list,
                   template: str) -> list:
    """
    Bangun daftar messages untuk dikirim ke AI.
    Return: list dict messages dalam format chat.
    """
    rules_text = "\n\n".join(rules)
    # Batasi knowledge agar tidak melebihi context window
    knowledge_text = "\n\n---\n\n".join([k[:2000] for k in knowledge])

    # Ambil directives jika ada
    directives = topic_info.get("content_directives") or \
                 topic_info.get("tool_directives") or {}
    if isinstance(directives, str):
        directives = {}

    keywords = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict)
        else topic_info.get("target_keyword", "")
    )

    system_msg = f"""You are a content writer specializing in SaaS tools and \
resources for bootstrapped founders in the US and Canada.

RULES YOU MUST FOLLOW:
{rules_text}

RELEVANT KNOWLEDGE AND DATA:
{knowledge_text}

CONTENT TEMPLATE TO FOLLOW:
{template}

Output ONLY the final content. Do not include explanations, \
apologies, or any text that is not part of the actual content."""

    user_msg = f"""Create content for this task:

Task type    : {topic_info.get('task_type')}
Topic/Name   : {topic_info.get('topic') or topic_info.get('tool_name')}
Keyword      : {primary_kw}
Angle        : {directives.get('angle', 'standard approach')}
Tone         : {directives.get('tone', 'peer-founder')}
Word target  : {directives.get('word_count_target', 800)}

Follow the template exactly. Replace all {{PLACEHOLDER}} \
values with actual content."""

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]


def generate(task_config: dict, topic_info: dict,
             rules: list, knowledge: list, template: str) -> str:
    """
    Generate konten menggunakan Cloudflare Workers AI.
    Return: konten yang di-generate sebagai string.
    """
    messages = build_messages(
        task_config, topic_info, rules, knowledge, template
    )
    max_tokens = task_config.get("max_tokens", 1024)
    print(f"Calling Cloudflare Workers AI (model: {MODEL})...")
    content = call_ai(messages, max_tokens)
    word_count = len(content.split())
    print(f"AI generated {word_count} words")
    return content

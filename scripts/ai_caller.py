"""
ai_caller.py
Panggil Cloudflare Workers AI untuk generate konten.
Model: @cf/meta/llama-3.1-8b-instruct
"""
import os
import re
import json
import time
import urllib.request
import urllib.error

CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_API_TOKEN  = os.environ["CF_API_TOKEN"]
MODEL = "@cf/meta/llama-3.1-8b-instruct"

MAX_RETRIES  = 3
RETRY_DELAY  = 10   # detik antar retry
RULES_PER_FILE_LIMIT = 1500   # chars per rules file
KNOWLEDGE_PER_FILE_LIMIT = 800  # chars per knowledge file


# ─────────────────────────────────────────────
# CORE: HTTP call ke CF AI dengan retry
# ─────────────────────────────────────────────

def call_ai(messages: list, max_tokens: int = 1024) -> str:
    """
    Kirim messages ke Cloudflare Workers AI.
    Retry otomatis hingga MAX_RETRIES kali jika timeout.
    Return: teks hasil generate sebagai string.
    Raise Exception jika semua retry gagal.
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

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"Retry attempt {attempt}/{MAX_RETRIES} "
                  f"(waiting {RETRY_DELAY}s)...")
            time.sleep(RETRY_DELAY)

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
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())

            if not data.get("success"):
                raise Exception(f"CF AI error: {data.get('errors')}")

            result = data.get("result", {}).get("response", "").strip()
            if not result:
                raise Exception("CF AI returned empty response")

            return result

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            last_error = Exception(f"CF AI HTTP error {e.code}: {body}")
            print(f"Attempt {attempt} failed: HTTP {e.code}")

        except Exception as e:
            last_error = e
            print(f"Attempt {attempt} failed: {e}")

    raise last_error


# ─────────────────────────────────────────────
# ARTICLE: build messages + generate
# ─────────────────────────────────────────────

def build_messages(task_config: dict, topic_info: dict,
                   rules: list, knowledge: list,
                   template: str) -> list:
    """
    Bangun messages untuk generate artikel.
    Setiap rules file dibatasi RULES_PER_FILE_LIMIT secara individual
    agar tidak ada rules file yang terpotong total karena limit gabungan.
    """
    # Truncate per file, bukan gabungan — pastikan setiap file ada representasinya
    rules_text = "\n\n".join([r[:RULES_PER_FILE_LIMIT] for r in rules])
    knowledge_text = "\n\n---\n\n".join(
        [k[:KNOWLEDGE_PER_FILE_LIMIT] for k in knowledge]
    )

    directives = topic_info.get("content_directives") or {}
    if isinstance(directives, str):
        directives = {}

    keywords = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict)
        else topic_info.get("target_keyword", "")
    )

    system_msg = (
        "You are an expert content writer specializing in SaaS tools and "
        "resources for bootstrapped founders in the US and Canada.\n\n"
        "RULES YOU MUST FOLLOW:\n"
        f"{rules_text}\n\n"
        "RELEVANT KNOWLEDGE AND DATA:\n"
        f"{knowledge_text}\n\n"
        "CONTENT TEMPLATE TO FOLLOW:\n"
        f"{template}\n\n"
        "Output ONLY the final content. Do not include explanations, "
        "apologies, or any text that is not part of the actual content."
    )

    user_msg = (
        "Create content for this task:\n\n"
        f"Task type    : {topic_info.get('task_type')}\n"
        f"Topic        : {topic_info.get('topic')}\n"
        f"Keyword      : {primary_kw}\n"
        f"Angle        : {directives.get('angle', 'standard approach')}\n"
        f"Tone         : {directives.get('tone', 'peer-founder')}\n"
        f"Word target  : {directives.get('word_count_target', 800)}\n\n"
        "Follow the template exactly. Replace all {{PLACEHOLDER}} "
        "values with real content."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg}
    ]


def generate(task_config: dict, topic_info: dict,
             rules: list, knowledge: list, template: str) -> str:
    """
    Generate artikel menggunakan Cloudflare Workers AI.
    Return: konten artikel sebagai string.
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


# ─────────────────────────────────────────────
# TOOL: build messages + generate (JSON output)
# ─────────────────────────────────────────────

def build_tool_messages(topic_info: dict, rules_text: str) -> list:
    """
    Bangun messages untuk generate komponen kalkulator.
    AI diminta menghasilkan JSON dengan bagian dinamis saja —
    bukan full HTML. Postprocess.py yang inject ke template.
    """
    formula   = topic_info.get("formula", {})
    directives = topic_info.get("tool_directives", {}) or {}
    affiliate  = topic_info.get("affiliate", {}) or {}
    tool_name  = topic_info.get("tool_name", "Calculator")
    tool_slug  = topic_info.get("tool_slug", "calculator")
    show_cta   = affiliate.get("show_cloudways_cta", False)

    # Ambil input keys dari formula untuk panduan ID elemen
    input_keys = list(formula.get("inputs", {}).keys())
    input_labels = {
        k: v.get("label", k)
        for k, v in formula.get("inputs", {}).items()
    }
    input_placeholders = {
        k: v.get("placeholder", "0")
        for k, v in formula.get("inputs", {}).items()
    }
    computed = formula.get("computed", {})
    output   = formula.get("output", {})
    edge_cases = formula.get("edge_cases", {})
    interpretations = output.get("interpretations", [])

    system_msg = (
        "You are a JavaScript developer and UX writer building "
        "a SaaS calculator tool for bootstrapped founders.\n\n"
        "RULES:\n"
        f"{rules_text}\n\n"
        "OUTPUT FORMAT: Return ONLY valid JSON. "
        "No markdown fences, no explanation before or after. "
        "Just the raw JSON object."
    )

    user_msg = (
        f"Build the dynamic parts of this calculator tool:\n\n"
        f"Tool name  : {tool_name}\n"
        f"Tool slug  : {tool_slug}\n"
        f"Subtitle   : {directives.get('subtitle', '')}\n"
        f"Scenario   : {directives.get('example_scenario', '')}\n"
        f"Show formula: {directives.get('show_formula', True)}\n"
        f"Cloudways CTA: {show_cta}\n\n"
        f"Formula inputs (use these exact IDs in HTML and JS):\n"
        f"{json.dumps(input_labels, indent=2)}\n\n"
        f"Example placeholder values:\n"
        f"{json.dumps(input_placeholders, indent=2)}\n\n"
        f"Computed values:\n"
        f"{json.dumps(computed, indent=2)}\n\n"
        f"Output:\n"
        f"{json.dumps(output, indent=2)}\n\n"
        f"Edge cases to handle in JS:\n"
        f"{json.dumps(edge_cases, indent=2)}\n\n"
        f"Interpretations:\n"
        f"{json.dumps(interpretations, indent=2)}\n\n"
        "Return a JSON object with EXACTLY these keys:\n"
        "- tool_subtitle: string (one sentence, plain text)\n"
        "- meta_description: string (150-160 chars)\n"
        "- primary_unit: string (e.g. 'months', 'customers')\n"
        "- formula_comment: string (one-line formula for JS comment)\n"
        "- input_fields_html: string (HTML using class='input-group' "
        f"and input IDs matching exactly: {input_keys})\n"
        "- example_values_init: string (JS lines setting .value for each "
        f"input ID using the placeholder values above)\n"
        "- calculator_javascript: string (complete function calculate() "
        "that reads input values by ID, computes result, updates "
        "document.getElementById('result-primary').textContent, "
        "document.getElementById('interpretation').textContent, "
        "and handles edge cases)\n"
        "- formula_box_html: string (HTML div with class='formula-box' "
        "showing the formula if show_formula is true, empty string if false)\n"
        "- affiliate_box_html: string (HTML div with class='affiliate-box' "
        "for Cloudways CTA if show_cloudways_cta is true, "
        "empty string if false)\n"
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg}
    ]


def generate_tool_parts(task_config: dict, topic_info: dict,
                        rules: list) -> dict:
    """
    Generate komponen dinamis kalkulator menggunakan CF AI.
    Return: dict dengan bagian-bagian yang akan diinjeksikan ke template HTML.
    Raise Exception jika AI mengembalikan JSON tidak valid.
    """
    # Untuk tools, hanya kirim tools_rules — tidak perlu article_rules
    # Ambil rules file terakhir yang relevan (tools_rules.txt)
    tools_rules = rules[-1][:RULES_PER_FILE_LIMIT] if rules else ""

    messages  = build_tool_messages(topic_info, tools_rules)
    max_tokens = task_config.get("max_tokens", 1024)

    print(f"Calling Cloudflare Workers AI (model: {MODEL})...")
    raw = call_ai(messages, max_tokens)
    word_count = len(raw.split())
    print(f"AI generated {word_count} words")

    # Parse JSON — strip markdown fences jika ada
    clean = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    clean = re.sub(r'\s*```$', '', clean.strip(), flags=re.MULTILINE)
    clean = clean.strip()

    try:
        parts = json.loads(clean)
    except json.JSONDecodeError as e:
        raise Exception(
            f"Tool AI returned invalid JSON: {e}\n"
            f"Raw output (first 300 chars): {raw[:300]}"
        )

    # Validasi keys yang wajib ada
    required_keys = [
        "tool_subtitle", "meta_description", "primary_unit",
        "formula_comment", "input_fields_html", "example_values_init",
        "calculator_javascript", "formula_box_html", "affiliate_box_html"
    ]
    missing = [k for k in required_keys if k not in parts]
    if missing:
        raise Exception(f"Tool AI JSON missing required keys: {missing}")

    return parts

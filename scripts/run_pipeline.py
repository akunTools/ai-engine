"""
run_pipeline.py
Orchestrator utama pipeline generate konten.
Dipanggil oleh GitHub Actions workflow.
Menggabungkan loader, ai_caller, postprocess, publisher.
"""
import os
import sys
import json
import traceback
from datetime import datetime

# Tambahkan folder scripts ke path agar import bisa dilakukan
sys.path.insert(0, os.path.dirname(__file__))

from loader import (
    fetch_file, fetch_json, get_next_pending,
    mark_topic, write_log
)
from ai_caller import generate
from postprocess import (
    validate_article, format_article,
    validate_tool, format_tool
)
from publisher import publish


def run_article_pipeline(topic_info: dict,
                         tasks_config: dict) -> dict:
    """
    Jalankan pipeline lengkap untuk generate artikel.
    Return: dict hasil dengan keys: success, issues, filename
    """
    task_config = tasks_config["article"]
    print(f"\n=== ARTICLE PIPELINE ===")
    print(f"Topic   : {topic_info.get('topic')}")

    keywords = topic_info.get("keywords", {})
    primary_kw = (
        keywords.get("primary", "") if isinstance(keywords, dict)
        else ""
    )
    print(f"Keyword : {primary_kw}")

    # Load rules dari ai-brain
    rules = []
    for rules_file in task_config["rules_files"]:
        rules.append(fetch_file(rules_file))
    print(f"Rules loaded: {len(rules)} files")

    # Load knowledge dari ai-brain
    knowledge = []
    for kn_file in task_config["knowledge_files"]:
        knowledge.append(fetch_file(kn_file))
    print(f"Knowledge loaded: {len(knowledge)} files")

    # Load template
    template = fetch_file(task_config["template"])
    print("Template loaded")

    # Generate dengan AI
    content = generate(task_config, topic_info,
                       rules, knowledge, template)

    # Validasi output
    validation = validate_article(content, task_config, topic_info)
    if not validation["valid"]:
        print(f"Validation FAILED: {validation['issues']}")
        return {"success": False, "issues": validation["issues"]}

    print(f"Validation passed: {validation['word_count']} words")

    # Format untuk publish
    formatted_content, filename = format_article(content, topic_info)

    # Publish ke branch output
    success = publish(filename, formatted_content, "articles")
    if success:
        return {
            "success": True,
            "filename": filename,
            "word_count": validation["word_count"]
        }
    else:
        return {"success": False, "issues": ["Publishing failed"]}


def run_tool_pipeline(topic_info: dict,
                      tasks_config: dict) -> dict:
    """
    Jalankan pipeline lengkap untuk generate tools kalkulator.
    Return: dict hasil dengan keys: success, issues, filename
    """
    task_config = tasks_config["calculator_tool"]
    print(f"\n=== TOOL PIPELINE ===")
    print(f"Tool name : {topic_info.get('tool_name')}")
    print(f"Tool slug : {topic_info.get('tool_slug')}")

    # Load formula dari ai-brain
    formulas = fetch_json(task_config["formulas_file"])
    formula_id = topic_info.get("formula_id")
    if formula_id not in formulas:
        return {
            "success": False,
            "issues": [f"Formula '{formula_id}' not found in formulas file"]
        }
    formula = formulas[formula_id]
    print(f"Formula loaded: {formula_id}")

    # Load rules
    rules = []
    for rules_file in task_config["rules_files"]:
        rules.append(fetch_file(rules_file))

    # Load knowledge
    knowledge = []
    for kn_file in task_config["knowledge_files"]:
        knowledge.append(fetch_file(kn_file))

    # Load template
    template = fetch_file(task_config["template"])

    # Tambahkan formula ke topic_info agar AI bisa gunakan
    topic_info_with_formula = {**topic_info, "formula": formula}

    # Generate dengan AI
    content = generate(task_config, topic_info_with_formula,
                       rules, knowledge, template)

    # Validasi output
    validation = validate_tool(content)
    if not validation["valid"]:
        print(f"Validation FAILED: {validation['issues']}")
        return {"success": False, "issues": validation["issues"]}

    print("Tool validation passed")

    # Format untuk publish
    formatted_content, filename = format_tool(content, topic_info)

    # Publish ke branch output
    success = publish(filename, formatted_content, "tools")
    if success:
        return {"success": True, "filename": filename}
    else:
        return {"success": False, "issues": ["Publishing failed"]}


def main():
    print(f"Pipeline started at {datetime.utcnow().isoformat()}")

    task_type      = os.environ.get("TASK_TYPE", "article")
    topic_id_env   = os.environ.get("TOPIC_ID", "").strip()
    date_str       = datetime.utcnow().strftime("%Y-%m-%d")

    # Load konfigurasi task
    tasks_config = fetch_json("config/tasks.json")

    # Tentukan topik yang akan diproses
    if topic_id_env:
        # Cari topik spesifik berdasarkan ID
        schedule = fetch_json("config/schedule.json")
        topic_info = next(
            (t for t in schedule["topic_queue"]
             if t["id"] == topic_id_env),
            None
        )
        if not topic_info:
            print(f"Topic ID '{topic_id_env}' not found in queue")
            sys.exit(1)
    else:
        # Ambil topik pertama yang pending
        topic_info = get_next_pending(task_type)
        if not topic_info:
            print(f"No pending {task_type} topics in queue. Exiting.")
            # Tandai queue kosong dengan membuat flag file
            with open("/tmp/queue_empty.flag", "w") as f:
                f.write(task_type)
            return

    print(f"Processing: {topic_info['id']}")

    try:
        # Jalankan pipeline sesuai task_type
        if task_type == "article":
            result = run_article_pipeline(topic_info, tasks_config)
        elif task_type == "calculator_tool":
            result = run_tool_pipeline(topic_info, tasks_config)
        else:
            print(f"Unknown task_type: {task_type}")
            sys.exit(1)

        # Update status di queue
        new_status = "done" if result.get("success") else "failed"
        mark_topic(topic_info["id"], new_status)

        # Tulis log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "topic_id": topic_info["id"],
            "task_type": task_type,
            "result": result
        }
        write_log(date_str, log_entry, new_status)

        if result.get("success"):
            print(f"\nPipeline completed successfully")
            print(f"Output: {result.get('filename')}")
        else:
            print(f"\nPipeline failed: {result.get('issues')}")
            sys.exit(1)

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"\nUnexpected error:\n{error_msg}")

        # Catat kegagalan
        mark_topic(topic_info["id"], "failed")
        write_log(date_str, {
            "timestamp": datetime.utcnow().isoformat(),
            "topic_id": topic_info["id"],
            "task_type": task_type,
            "result": {"success": False, "issues": [str(e)]}
        }, "failures")

        # Simpan error untuk artifact upload di workflow
        with open("/tmp/pipeline_error.log", "w") as f:
            f.write(error_msg)

        sys.exit(1)


if __name__ == "__main__":
    main()

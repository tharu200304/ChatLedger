import json
from pathlib import Path
from typing import Dict, Any, List
from backend.config import DATASETS_DIR
from backend.database import get_db

def export_lora_dataset(format_type: str = "alpaca") -> Dict[str, Any]:
    """
    Exports all confirmed and corrected orders as a training dataset
    formatted for LoRA fine-tuning (e.g. Unsloth, PEFT, llama.cpp fine-tune)
    on Qwen3-8B.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, raw_chat_prompt, corrected_json, created_at
        FROM corrections
        ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    dataset_entries: List[Dict[str, Any]] = []

    system_instruction = (
        "You are ChatLedger, extracting structured order details from an English "
        "WhatsApp chat. Output valid JSON adhering to the specified schema."
    )

    for r in rows:
        chat_text = r["raw_chat_prompt"]
        try:
            output_json = json.loads(r["corrected_json"])
            formatted_output = json.dumps(output_json, indent=2, ensure_ascii=False)
        except Exception:
            formatted_output = r["corrected_json"]

        if format_type == "sharegpt":
            entry = {
                "conversations": [
                    {"from": "system", "value": system_instruction},
                    {"from": "human", "value": f"Extract order from this customer thread:\n\n{chat_text}"},
                    {"from": "gpt", "value": formatted_output}
                ]
            }
        else: # Alpaca format
            entry = {
                "instruction": system_instruction,
                "input": f"Extract order from this customer thread:\n\n{chat_text}",
                "output": formatted_output
            }
        dataset_entries.append(entry)

    out_file = DATASETS_DIR / f"chatledger_lora_{format_type}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for entry in dataset_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {
        "total_examples": len(dataset_entries),
        "filepath": str(out_file),
        "filename": out_file.name,
        "format": format_type
    }

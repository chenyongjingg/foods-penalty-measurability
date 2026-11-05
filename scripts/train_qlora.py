#!/usr/bin/env python3
"""Optional self-training step (Plan §5.2: QLoRA on high-confidence silver).

Triggered by the extractor only when E1 misses the floor and >=500 high-tier
documents exist. This script refuses to run silently when the training stack is
absent: it exits with a recorded reason, which is the honest state of the
ladder. It never overwrites the base model; adapters go to data/train/adapter.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("FOODS_ROOT", "/opt/foods"))
DATA = ROOT / "data" / "train" / "selftrain.jsonl"
OUT = ROOT / "data" / "train" / "adapter"


def main() -> int:
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
    except Exception as exc:  # noqa: BLE001
        reason = f"training stack unavailable: {type(exc).__name__}: {exc}"
        (ROOT / "state" / "selftrain_status.json").write_text(
            json.dumps({"status": "blocked", "reason": reason}, ensure_ascii=False), encoding="utf-8")
        print(reason)
        return 2
    if not DATA.exists():
        print("no selftrain.jsonl")
        return 1
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    model_path = os.environ.get("FOODS_MODEL", "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct")
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.bfloat16,
                                                 device_map="auto")
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32,
                                             target_modules=["q_proj", "v_proj"],
                                             task_type="CAUSAL_LM"))

    def fmt(r):
        target = json.dumps({k: r[k] for k in ("entities", "violation_category")},
                            ensure_ascii=False)
        return {"text": f"文书标注任务\n输出：{target}{tok.eos_token}"}

    ds = Dataset.from_list([fmt(r) for r in rows])
    ds = ds.map(lambda x: tok(x["text"], truncation=True, max_length=2048), batched=False)
    Trainer(model=model, args=TrainingArguments(
        output_dir=str(OUT), num_train_epochs=1, per_device_train_batch_size=1,
        gradient_accumulation_steps=8, learning_rate=1e-4, logging_steps=10,
        save_strategy="epoch", bf16=True, report_to="none"),
        train_dataset=ds).train()
    model.save_pretrained(OUT)
    (ROOT / "state" / "selftrain_status.json").write_text(
        json.dumps({"status": "adapter_saved", "path": str(OUT)}, ensure_ascii=False),
        encoding="utf-8")
    print("adapter saved to", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

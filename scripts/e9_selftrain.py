#!/usr/bin/env python3
"""E9 -- QLoRA self-training controlled rerun (Plan v7 E9; appendix-level).

Question: do high-confidence silver pseudo-labels improve *anchor F1* when the
same 7B model is fine-tuned on them? This is deliberately not an E1 change:
E1's 0.6898 stays frozen and is measured under its own protocol; E9 reports
one number of its own (anchor F1 of a greedy, single-channel run) and never
places the post-ladder 0.7457 in the same table.

What this script does, in one run, so the base and the adapter see identical
inputs:

1. load the frozen 7B in 4-bit NF4 (bitsandbytes) -- the *same* weights vLLM
   serves, so the only difference between the two arms is the adapter;
2. score the base model on the anchor evaluation set (greedy, channel alpha
   prompt, one sample). This is the control arm;
3. attach a LoRA adapter (r=16, alpha=32, q_proj/v_proj) and train it on the
   high-confidence silver subset (tier == high): input = the rendered alpha
   prompt, target = the silver record's entities + violation_category, loss on
   the answer tokens only (prompt tokens are masked to -100);
4. score the adapter on the same evaluation set with the same decoding;
5. write data/analysis/e9_selftrain.json with both arms, the delta, the
   truncation counts and the adapter's sha256.

The old scripts/train_qlora.py is left untouched but must not be used: its
training text is `"文书标注任务\n输出：" + target` with **no document**, so it
trains the model to emit labels from nothing. That defect is registered (D-82).

Evaluation set = every silver record that carries a statute-grounded anchor
(`anchor.category` and basis in penalty_statute / cited_statute / statute+fact
/ None), i.e. exactly the documents `anchors.anchor_pairs` admits. Documents
the model fails to parse are counted, never imputed.

Usage (after stopping the inference server -- ~10 GB VRAM is needed):
    /opt/e9venv/bin/python scripts/e9_selftrain.py --build-only   # no GPU
    /opt/e9venv/bin/python scripts/e9_selftrain.py --run          # GPU
Exit 0 = product written; 1 = precondition failed; 2 = training stack absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL_PATH = os.environ.get("FOODS_MODEL", "/model/ModelScope/Qwen/Qwen2.5-7B-Instruct")
SILVER = ROOT / "data" / "silver" / "silver.jsonl"
TRAIN_JSONL = ROOT / "data" / "train" / "selftrain.jsonl"
ADAPTER = ROOT / "data" / "train" / "adapter_e9"
OUT = ROOT / "data" / "analysis" / "e9_selftrain.json"

MAX_LEN = 8192          # tokens; the *document* is shortened to fit, never the template
# Answer budget must match the labelling instrument, not intuition: channel A
# runs with max_tokens=3000 (data/metrics/e1.json protocol.max_tokens). The
# first two E9 launches kept 256 and 49/50 answers were cut mid-JSON; the 1024
# probe showed the two failures were document continuations caused by right-
# truncating the chat wrapper. The budget is now channel A's exactly, so the
# only remaining gap to production is the document window (D-89).
MAX_NEW = 3000          # answer tokens: exactly channel A's budget (e1.json protocol)
MIN_DOC_CHARS = 200     # never shorten a document below this to fit the window
EPOCHS = 3
GRAD_ACCUM = 8
LR = 1e-4


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _texts() -> dict[str, str]:
    from foods_pipeline.manifest import Manifest
    out = {}
    m = Manifest()
    with m.conn() as c:
        for row in c.execute("SELECT doc_id, text_path FROM docs"):
            if row["text_path"]:
                try:
                    out[row["doc_id"]] = Path(row["text_path"]).read_text(encoding="utf-8")
                except OSError:
                    pass
    return out


def _records() -> list[dict]:
    return [json.loads(l) for l in open(SILVER, encoding="utf-8") if l.strip()]


def _render(rec: dict, text: str) -> str:
    from foods_pipeline.label import prompts
    return prompts.render("alpha", rec.get("lang") or "zh", text)


def _chat(tok, prompt: str) -> str:
    """Render the prompt exactly as vLLM does for the labelling path.

    `foods_pipeline.label.llm` posts `{"messages":[{"role":"user",...}]}` to
    /chat/completions, so the server applies the model's ChatML template. The
    first E9 launch (2026-11-05T04:02Z) fed the raw prompt string to the
    instruct model instead; the base arm then emitted unparsable prose in
    49/50 documents (D-89), which would have made any adaptor delta a format
    artefact rather than a labelling gain. Both arms now go through the
    template, so the only difference between them is the adaptor.
    """
    try:
        return tok.apply_chat_template([{"role": "user", "content": prompt}],
                                       tokenize=False, add_generation_prompt=True)
    except Exception:  # noqa: BLE001 - keep a fallback but record which path ran
        return prompt


def build(recs: list[dict], texts: dict[str, str]) -> tuple[list[dict], list[dict], dict]:
    """Training rows and the anchor evaluation set, with truncation counts."""
    train = [r for r in recs if r.get("tier") == "high" and r["doc_id"] in texts]
    evalset = []
    from foods_pipeline.label.anchors import anchor_pairs
    for r in recs:
        if r["doc_id"] not in texts:
            continue
        a = r.get("anchor") or {}
        if not a.get("category"):
            continue
        if a.get("basis") in ("penalty_statute", "cited_statute", "statute+fact", None):
            evalset.append(r)
    # `anchor_pairs` is the single definition of who counts; assert we agree.
    assert len(anchor_pairs(evalset)[0]) == len(evalset), "eval set disagrees with anchor_pairs"

    rows, n_trunc = [], 0
    for r in train:
        text = texts[r["doc_id"]]
        prompt = _render(r, text)
        target = json.dumps({"entities": r.get("entities") or [],
                             "violation_category": r.get("violation_category")},
                            ensure_ascii=False)
        n_trunc += int(len(text) > 20000)
        rows.append({"doc_id": r["doc_id"], "lang": r.get("lang"),
                     "prompt": prompt, "target": target, "text": text})
    stats = {
        "n_train": len(rows),
        "n_train_zh": sum(1 for r in rows if r.get("lang") == "zh"),
        "n_train_truncated_at_20k_chars": n_trunc,
        "n_eval_anchor": len(evalset),
        "n_eval_zh": sum(1 for r in evalset if r.get("lang") == "zh"),
        "n_eval_en": sum(1 for r in evalset if r.get("lang") == "en"),
        "eval_basis": {b: sum(1 for r in evalset if (r.get("anchor") or {}).get("basis") == b)
                       for b in ("penalty_statute", "cited_statute", "statute+fact", None)},
    }
    return rows, evalset, stats


def _imports():
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    return torch, LoraConfig, get_peft_model, prepare_model_for_kbit_training, \
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def _load(torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig):
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, quantization_config=bnb,
                                                 device_map={"": 0}, torch_dtype=torch.bfloat16)
    return tok, model


def _fit_ids(tok, rec: dict, text: str, budget: int) -> tuple[list[int], int, bool]:
    """Tokenise the chat prompt, shortening the *document* until it fits.

    Truncating the assembled token sequence from the right (the first two E9
    launches did that) cuts `<|im_start|>assistant`, so the instruct model
    continues the document instead of answering -- observed directly in the
    probe: the unparsable answers were verbatim document continuations (D-89).
    The wrapper has to survive; the document is what gives way.

    Returns (token ids, characters of the document kept, whether it was cut).
    """
    def ids_for(chars: int) -> list[int]:
        return tok(_chat(tok, _render(rec, text[:chars])),
                   add_special_tokens=False)["input_ids"]

    full = ids_for(len(text))
    if len(full) <= budget:
        return full, len(text), False
    lo, hi = MIN_DOC_CHARS, len(text)
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        if len(ids_for(mid)) <= budget:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ids_for(best), best, True


def _predict(torch, model, tok, recs, texts, tag: str) -> tuple[list[dict], dict]:
    """Greedy single-sample answers; unparsable answers are counted, not filled.

    `n_ctx_truncated` measures the one instrument gap that remains after the
    ChatML fix: MAX_LEN tokens is a much shorter document than the labelling
    path's 20,000 characters, so long documents are seen in part here. Both
    arms see the same shortened input, so the delta is unaffected; the count is
    reported so the absolute F1 is not read as the labelling instrument's F1.
    """
    from foods_pipeline.label.llm import parse_json
    model.eval()
    preds, n_err, n_ctx_trunc, t0 = [], 0, 0, time.time()
    budget = MAX_LEN - MAX_NEW
    with torch.inference_mode():
        for i, r in enumerate(recs):
            ids, kept_chars, truncated = _fit_ids(tok, r, texts[r["doc_id"]], budget)
            n_ctx_trunc += int(truncated)
            x = torch.tensor([ids], device=model.device)
            out = model.generate(input_ids=x, max_new_tokens=MAX_NEW, do_sample=False,
                                 num_beams=1, pad_token_id=tok.eos_token_id)
            ans = tok.decode(out[0][x.shape[1]:], skip_special_tokens=True)
            j = parse_json(ans) or {}
            cat = (j.get("violation_category") or "").strip().upper() or None
            n_err += int(cat is None)
            preds.append({"doc_id": r["doc_id"], "lang": r.get("lang"),
                          "pred": cat, "ctx_truncated": truncated,
                          "doc_chars_kept": kept_chars,
                          "n_new_tokens": int(out.shape[1] - x.shape[1]),
                          "raw_head": ans[:400]})
            if (i + 1) % 50 == 0:
                print(f"[{tag}] {i + 1}/{len(recs)}  {time.time() - t0:.0f}s  err={n_err} "
                      f"ctx_trunc={n_ctx_trunc}", flush=True)
    return preds, {"n": len(recs), "n_unparsed": n_err, "n_ctx_truncated": n_ctx_trunc,
                   "seconds": round(time.time() - t0, 1)}


UNPARSED = "__UNPARSED__"   # sentinel: never a real category, never imputed away


def _score(evalset: list[dict], preds: list[dict], only_untruncated: bool = False,
           only_ids: set[str] | None = None) -> dict:
    from foods_pipeline.label.anchors import anchor_f1, anchor_pairs, anchor_support
    drop = {p["doc_id"] for p in preds if only_untruncated and p.get("ctx_truncated")}
    if only_ids is not None:
        drop |= {p["doc_id"] for p in preds if p["doc_id"] not in only_ids}
    by = {p["doc_id"]: p["pred"] for p in preds if p["doc_id"] not in drop}
    n_unparsed = 0
    recs = []
    for r in evalset:
        if r["doc_id"] in drop:
            continue
        rr = dict(r)
        cat = by.get(r["doc_id"])
        if not cat:
            # A failed parse is a wrong answer, not a missing one. Passing None
            # into anchor_pairs used to crash anchor_f1's sorted() (2026-11-05
            # 07:08Z, after 2.3 h of base-arm inference) and, had it been
            # dropped instead, would have inflated the score by removing the
            # failures (D-103).
            n_unparsed += 1
            cat = UNPARSED
        rr["violation_category"] = cat
        recs.append(rr)
    pairs, fact_only = anchor_pairs(recs)
    f1 = anchor_f1(pairs)
    return {"anchor_f1": f1, "n_docs": len(recs), "n_pairs": len(pairs),
            "n_unparsed": n_unparsed,
            "fact_only_excluded": fact_only, "support": anchor_support(pairs)}


def _checkpoint(name: str, preds: list[dict], stat: dict) -> None:
    """Persist one arm's per-document predictions before scoring.

    An arm costs hours of GPU; the 2026-11-05 run lost 2.3 h of base-arm
    output when the *scoring* step raised after inference had finished
    (D-103). Write-only: nothing reads this file back, so a stale checkpoint
    can never enter a verdict.
    """
    p = ROOT / "data" / "train" / f"e9_{name}_preds.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"decode": stat, "predictions": preds},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-only", action="store_true", help="dump the train file, no GPU")
    ap.add_argument("--run", action="store_true", help="train + evaluate on the GPU")
    ap.add_argument("--probe", type=int, default=0,
                    help="print the full answer for the first N eval docs (instrument check)")
    args = ap.parse_args()
    if not (args.build_only or args.run or args.probe):
        print("pass --build-only, --probe N, or --run", file=sys.stderr)
        return 1

    recs, texts = _records(), _texts()
    rows, evalset, stats = build(recs, texts)
    print(json.dumps({"build": stats, "silver_sha256": _sha(SILVER)}, ensure_ascii=False))

    TRAIN_JSONL.parent.mkdir(parents=True, exist_ok=True)
    TRAIN_JSONL.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                           encoding="utf-8")
    if args.build_only:
        return 0

    try:
        (torch, LoraConfig, get_peft_model, prepare_model_for_kbit_training,
         AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig) = _imports()
    except Exception as exc:  # noqa: BLE001
        print(f"training stack unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    started = time.time()
    tok, model = _load(torch, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig)
    from foods_pipeline.label.prompts import doc_chars as _doc_chars
    doc_cut = _doc_chars()

    if args.probe:
        # Instrument check: show what the base model actually answers, so an
        # unparsable arm is diagnosed from its output and not guessed at (D-89).
        preds, st = _predict(torch, model, tok, evalset[:args.probe], texts, "probe")
        for p in preds:
            print("PROBE " + json.dumps({"doc_id": p["doc_id"], "pred": p["pred"],
                                         "n_new_tokens": p["n_new_tokens"],
                                         "ctx_truncated": p["ctx_truncated"],
                                         "answer": p["raw_head"]}, ensure_ascii=False),
                  flush=True)
        print("PROBE_STATS " + json.dumps(st, ensure_ascii=False), flush=True)
        return 0
    base_preds, base_stat = _predict(torch, model, tok, evalset, texts, "base")
    _checkpoint("base", base_preds, base_stat)
    base_score = _score(evalset, base_preds)
    base_score_nc = _score(evalset, base_preds, only_untruncated=True)
    torch.cuda.empty_cache()

    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32,
                                             target_modules=["q_proj", "v_proj"],
                                             task_type="CAUSAL_LM"))
    model.train()

    # tokenise: prompt masked, answer scored; same ChatML template as inference
    data = []
    for r in rows:
        p_ids, _, _ = _fit_ids(tok, r, r["text"], MAX_LEN - MAX_NEW)
        t_ids = tok(r["target"] + tok.eos_token, truncation=True, max_length=MAX_NEW)["input_ids"]
        ids = (p_ids + t_ids)[:MAX_LEN]
        labels = [-100] * min(len(p_ids), len(ids)) + ids[min(len(p_ids), len(ids)):]
        data.append((ids, labels))

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
    step, t0, losses = 0, time.time(), []
    for ep in range(EPOCHS):
        for i, (ids, labels) in enumerate(data):
            x = torch.tensor([ids], device=model.device)
            y = torch.tensor([labels], device=model.device)
            loss = model(input_ids=x, labels=y).loss / GRAD_ACCUM
            loss.backward()
            losses.append(float(loss) * GRAD_ACCUM)
            if (i + 1) % GRAD_ACCUM == 0 or i + 1 == len(data):
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
            if (i + 1) % 40 == 0:
                print(f"[train] ep{ep + 1} {i + 1}/{len(data)} loss={losses[-1]:.4f} "
                      f"{time.time() - t0:.0f}s", flush=True)
    ADAPTER.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ADAPTER)

    model.eval()
    ft_preds, ft_stat = _predict(torch, model, tok, evalset, texts, "adapter")
    _checkpoint("adapter", ft_preds, ft_stat)
    ft_score = _score(evalset, ft_preds)
    ft_score_nc = _score(evalset, ft_preds, only_untruncated=True)

    base_ok = {p["doc_id"] for p in base_preds if p["pred"]}
    base_score_ok = _score(evalset, base_preds, only_ids=base_ok)
    ft_score_ok = _score(evalset, ft_preds, only_ids=base_ok)

    def macro(s):
        v = (s["anchor_f1"] or {}).get("macro_f1")
        return v if v is not None else (s["anchor_f1"] or {}).get("macro")

    delta = None
    if macro(base_score) is not None and macro(ft_score) is not None:
        delta = round(macro(ft_score) - macro(base_score), 4)
    delta_nc = None
    if macro(base_score_nc) is not None and macro(ft_score_nc) is not None:
        delta_nc = round(macro(ft_score_nc) - macro(base_score_nc), 4)
    delta_ok = None
    if macro(base_score_ok) is not None and macro(ft_score_ok) is not None:
        delta_ok = round(macro(ft_score_ok) - macro(base_score_ok), 4)
    # An adaptor gain that only exists because the base arm could not produce a
    # parsable answer is a format effect, not a labelling gain (D-89). Require
    # the base arm to be informative before any verdict other than zero.
    base_parseable = float(base_stat["n"] - base_stat["n_unparsed"]) / max(1, base_stat["n"])
    verdict = ("not_estimable" if delta is None else
               "invalid_base_arm" if base_parseable < 0.5 else
               "positive" if delta >= 0.03 else "no_material_gain")

    out = {
        "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol": {
            "model": MODEL_PATH, "quantisation": "4-bit NF4 + double quant",
            "lora": {"r": 16, "alpha": 32, "target_modules": ["q_proj", "v_proj"]},
            "epochs": EPOCHS, "lr": LR, "grad_accum": GRAD_ACCUM,
            "max_len": MAX_LEN, "max_new_tokens": MAX_NEW, "decoding": "greedy",
            "train_source": "silver tier==high (pseudo-labels), alpha prompt",
            "eval_set": "silver records with a statute-grounded anchor",
        },
        "data": stats,
        "instrument": {
            "prompt_format": "chatml (apply_chat_template, add_generation_prompt) -- the same "
                             "rendering vLLM applies to /chat/completions; see D-89",
            "max_len_tokens": MAX_LEN,
            "answer_budget_tokens": MAX_NEW,
            "doc_cut_chars": doc_cut,
            "fitting": "document shortened (binary search) to keep the chat wrapper; "
                       "the token sequence is never truncated from the right (D-89)",
            "n_eval_ctx_truncated": base_stat["n_ctx_truncated"],
            "base_parseable_share": round(base_parseable, 4),
        },
        "sensitivity_untruncated": {
            "n_docs": base_score_nc["n_docs"],
            "base": base_score_nc["anchor_f1"],
            "adapter": ft_score_nc["anchor_f1"],
            "delta_macro_f1": delta_nc,
        },
        "sensitivity_base_parseable": {
            "n_docs": base_score_ok["n_docs"],
            "note": "both arms scored only on documents the BASE arm could parse; this "
                    "separates category learning from format learning (D-89)",
            "base": base_score_ok["anchor_f1"],
            "adapter": ft_score_ok["anchor_f1"],
            "delta_macro_f1": delta_ok,
        },
        "silver_sha256": _sha(SILVER),
        "base": {"score": base_score, "decode": base_stat},
        "adapter": {"score": ft_score, "decode": ft_stat,
                    "sha256_weights": _sha(ADAPTER / "adapter_model.safetensors")
                    if (ADAPTER / "adapter_model.safetensors").exists() else None},
        "delta_macro_f1": delta, "verdict": verdict,
        "decision_rule": "Plan v7 E9: delta >= +3 points -> positive result in appendix; "
                         "otherwise one sentence of zero result.",
        "seconds_total": round(time.time() - started, 1),
        "train_loss_tail": [round(x, 4) for x in losses[-10:]],
        "predictions": {"base": base_preds, "adapter": ft_preds},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    print(json.dumps({"e9": "ok", "base": base_score["anchor_f1"],
                      "adapter": ft_score["anchor_f1"], "delta": delta,
                      "verdict": verdict}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

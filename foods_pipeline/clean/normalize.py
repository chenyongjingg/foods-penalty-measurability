"""L2 cleaning: text extraction, normalization, PII masking, dedupe, intake rule.

The intake rule is the D1' inclusion criterion from Plan §4.1:
fraud term AND document-type term (within a 20-character window) AND a food
context term anywhere in the document. Documents that fail are kept as
`filtered_out` for audit; they never enter the silver corpus.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import (cfg, get_logger, normalize_space, path_of, sha256_text,
                      utc_iso)
from ..manifest import Manifest

CJK = re.compile(r"[一-鿿]")
IDCARD = re.compile(r"\b\d{17}[\dXx]\b")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BANK = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
NAME_MARKER = r"(经营者|法定代表人|负责人|直接责任人|被处罚人|当事人|姓名|联系人)"
# Colon is optional: real documents also write "经营者叶青陆经现场辨认".
# The lookahead pins the name to a clause boundary so that "经营者应当……"
# does not swallow the following verb.
PERSON = re.compile(NAME_MARKER + r"[：:]?\s*([一-鿿]{2,4}?)"
                    r"(?=经|系|称|到|来|在|未|已|的|等|，|。|、|；|：|（|\(|\s|$)")
# Tokens that start with these characters are verbs/adverbs, not names.
FUNCTION_CHARS = set("应须不的在为是有未与和将可对及等其从向把被所该各每本我你他她它经要能会已正均也都又再更很最")
ADDRESS = re.compile(r"(经营场所|住所|联系地址|地址)[：:]\s*([^\n，,。；;]{1,80})")


def extract_text(raw_path: str, meta: dict) -> tuple[str, str]:
    """Return (text, kind). kind in {pdf, html, json, empty}."""
    p = Path(raw_path)
    if not p.exists():
        return "", "empty"
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            with fitz.open(p) as doc:
                parts = [page.get_text("text") for page in doc]
            return "\n".join(parts), "pdf"
        except Exception:
            return "", "empty"
    if suffix in (".html", ".htm"):
        try:
            from lxml import html as lhtml
            tree = lhtml.fromstring(p.read_bytes())
            for bad in tree.xpath("//script|//style|//noscript"):
                bad.getparent().remove(bad)
            return tree.text_content(), "html"
        except Exception:
            return "", "empty"
    if suffix == ".json":
        try:
            obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "", "empty"
        if "row" in obj:  # cfws metadata-only record
            row = obj["row"]
            return " ".join(str(row.get(k, "")) for k in ("2", "7", "14", "30", "36")), "json"
        # openFDA record
        keys = ("product_description", "reason_for_recall", "recalling_firm",
                "initial_firm_notification", "distribution_pattern", "city",
                "state", "country", "report_date", "classification")
        return "\n".join(f"{k}: {obj.get(k, '')}" for k in keys if obj.get(k)), "json"
    return "", "empty"


def mask_pii(text: str) -> str:
    text = IDCARD.sub("[ID]", text)
    text = BANK.sub("[ACCT]", text)
    text = PHONE.sub("[PHONE]", text)
    text = EMAIL.sub("[EMAIL]", text)

    def _person(m: re.Match) -> str:
        name = m.group(2)
        if len(name) == 1 or name[0] in FUNCTION_CHARS:
            return m.group(0)
        return f"{m.group(1)}：{name[0]}{'*' * (len(name) - 1)}"

    def _addr(m: re.Match) -> str:
        # Keep province/city granularity (used for jurisdiction checks), drop
        # street-level detail.
        val = m.group(2)
        return f"{m.group(1)}：{val[:6]}{'*' * max(0, len(val) - 6)}"

    text = PERSON.sub(_person, text)
    return ADDRESS.sub(_addr, text)


def lang_of(text: str) -> str:
    if not text:
        return "und"
    cjk = len(CJK.findall(text))
    return "zh" if cjk / max(1, len(text)) > 0.15 else "en"


def normalize(text: str) -> str:
    text = text.replace("　", " ").replace("\xa0", " ")
    text = re.sub(r"-\s*\n\s*", "", text)          # de-hyphenate PDF line breaks
    text = re.sub(r"(?<=[一-鿿])\n(?=[一-鿿])", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return normalize_space(text) if len(text) < 200 else text.strip()


def _term_near(text: str, a_terms: list[str], b_terms: list[str], window: int) -> bool:
    a_pos = [m.start() for t in a_terms for m in re.finditer(re.escape(t), text)]
    b_pos = [m.start() for t in b_terms for m in re.finditer(re.escape(t), text)]
    for i in a_pos:
        for j in b_pos:
            if abs(i - j) <= window:
                return True
    return False


def intake_decision(text: str, lang: str = "zh",
                    source: str | None = None) -> tuple[bool, dict]:
    """D1' lexical inclusion rule.

    openFDA records (D3a) are included by their API query (recall reason =
    adulterated / misbranded / labeling fraud / counterfeit), which is the
    plan's D3a criterion; applying the Chinese D1' rule to them would empty
    the comparison corpus. English text otherwise uses the same shape with
    English term lists.
    """
    if source == "openfda":
        return True, {"rule": "openfda_query_selection"}
    if lang == "en":
        fraud = cfg("intake.en_fraud_terms", [])
        has_fraud = any(t.lower() in text.lower() for t in fraud)
        has_food = any(t.lower() in text.lower()
                       for t in cfg("intake.en_food_terms", []))
        return bool(has_fraud and has_food), {"fraud": has_fraud, "food": has_food,
                                              "lang": "en"}
    fraud = cfg("intake.fraud_terms", [])
    doc = cfg("intake.document_terms", [])
    food = cfg("intake.food_terms", [])
    window = int(cfg("intake.window_chars", 20))
    has_fraud = any(t in text for t in fraud)
    has_doc = any(t in text for t in doc)
    has_food = any(t in text for t in food)
    # The plan's D1' rule is conjunctive keyword presence (fraud term AND
    # document term, in a food-safety decision). A proximity requirement was
    # added during the pilot and then measured: it rejected 115 of 399 filtered
    # documents that contain all three term families (e.g. the fraud is in the
    # facts section and the document type in the legal-basis section). Since
    # the labelling stage is the designated precision filter, proximity is off
    # by default; `intake.require_proximity: true` restores the pilot rule
    # (DEVIATIONS.md D-19).
    near = _term_near(text, fraud, doc, window)
    required = bool(cfg("intake.require_proximity", False))
    ok = bool(has_fraud and has_doc and has_food and (near or not required))
    return ok, {"fraud": has_fraud, "document": has_doc, "food": has_food,
                "near": near, "proximity_required": required}


class Cleaner:
    def __init__(self, manifest: Manifest | None = None):
        self.m = manifest or Manifest()
        self.log = get_logger("clean")
        self.outdir = path_of("data") / "clean" / "docs"
        self.outdir.mkdir(parents=True, exist_ok=True)
        # Documents that fail D1' keep their (PII-masked) text on disk. The
        # keyword sensitivity (analyze/keywords.py, Plan P115) asks what the
        # corpus would look like under another term list, and that question
        # cannot be answered from the admitted corpus alone: the documents a
        # variant would *add* are exactly the ones the current rule drops.
        self.filtered_dir = path_of("data") / "clean" / "filtered"
        self.filtered_dir.mkdir(parents=True, exist_ok=True)

    def run(self, limit: int | None = None) -> dict:
        stats = {"seen": 0, "clean": 0, "filtered_out": 0, "duplicate": 0,
                 "empty_text": 0, "awaiting_pdf": 0, "errors": 0}
        for doc in self.m.iter_stage("raw", limit=limit):
            stats["seen"] += 1
            try:
                meta = json.loads(doc.get("meta") or "{}")
                text, kind = extract_text(doc["raw_path"] or "", meta)
                if doc.get("source") == "cfws" and kind != "pdf":
                    # D1' analysis text must be the published decision itself,
                    # not the portal's list-view snippet. The PDF is fetched by
                    # the collector's backfill on a later run.
                    self.m.set_stage(doc["doc_id"], "failed", error="awaiting_pdf",
                                     note="needs_pdf")
                    stats["awaiting_pdf"] += 1
                    continue
                if len(text.strip()) < 40:
                    # Metadata-only records (no PDF) are retained as candidate
                    # rows but cannot enter text analysis.
                    self.m.set_stage(doc["doc_id"], "failed",
                                     error=f"empty_text:{kind}", note="extract")
                    stats["empty_text"] += 1
                    continue
                text = normalize(mask_pii(text))
                lang = lang_of(text)
                ok, why = intake_decision(text, lang, doc.get("source"))
                if not ok:
                    # Keep the masked text for the keyword sensitivity; it is
                    # never read by labelling and never enters the corpus.
                    (self.filtered_dir /
                     f"{doc['doc_id'].replace(':', '_')}.txt").write_text(text, encoding="utf-8")
                    self.m.set_stage(doc["doc_id"], "filtered_out",
                                     error=json.dumps(why, ensure_ascii=False), note="intake_rule")
                    stats["filtered_out"] += 1
                    continue
                case_no = (meta.get("case_no") or "").strip()
                dedupe_key = sha256_text((case_no + "|" + (doc.get("title") or "")).lower())[:32]
                if not self.m.dedupe_claim(dedupe_key, doc["doc_id"]):
                    self.m.set_stage(doc["doc_id"], "duplicate", note="dedupe")
                    stats["duplicate"] += 1
                    continue
                text_sha = sha256_text(text)
                out = self.outdir / f"{doc['doc_id'].replace(':', '_')}.txt"
                out.write_text(text, encoding="utf-8")
                self.m.set_stage(doc["doc_id"], "clean", text_path=str(out),
                                 text_sha=text_sha, n_chars=len(text), lang=lang,
                                 note="clean")
                stats["clean"] += 1
            except Exception as exc:  # noqa: BLE001
                self.log.exception("clean failed %s", doc["doc_id"])
                self.m.bump_attempt(doc["doc_id"], f"{type(exc).__name__}: {exc}")
                stats["errors"] += 1
        stats["at_utc"] = utc_iso()
        self.m.kv_set("stage_status:clean", stats)
        return stats

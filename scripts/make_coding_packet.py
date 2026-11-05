#!/usr/bin/env python
"""Draw the human-coding sample and build a self-contained HTML coding packet.

Sampling rule is fixed in PREREG_20261105_rescue.md:
  S1 = random.Random(20261105).sample(sorted(zh doc_ids), 60)
  S2 = first 20 of the disagreement pool ordered by sha256(doc_id)

The packet shows the full clean document text and the six codebook labels.
It shows no instrument output, no model output, and does not mark which
stratum a document came from.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
from pathlib import Path

ROOT = Path("/opt/foods")
SILVER = ROOT / "data/silver/silver.jsonl"
CLEAN = ROOT / "data/clean/docs"
OUT_SAMPLE = ROOT / "data/analysis/human_sample.json"
OUT_HTML = ROOT / "data/analysis/coding_packet.html"

SEED = 20261105
N_SRS = 60
N_DIS = 20

LABELS = [
    ("FORGED_INSPECTION_REPORT", "伪造/变造检验检测报告",
     "文书事实中出现伪造、变造、买卖检验/检测报告、检验结论、检测数据或检疫证明。"),
    ("TAMPERED_TRACEABILITY", "篡改溯源数据",
     "篡改、伪造或删除溯源码、追溯码、溯源/追溯信息。"),
    ("FAKE_CERTIFICATION", "虚假认证",
     "伪造、变造、冒用、买卖认证证书、认证标志或认证材料。"),
    ("FALSE_LABELING", "标签虚假标注",
     "标签/说明书虚假标注，篡改或虚假标注生产日期，冒用厂名厂址产地等（不含报告、认证类）。"),
    ("UNLICENSED_OPERATION", "无证或超范围经营",
     "未取得许可、无证或超出许可范围从事食品生产经营。"),
    ("OTHER", "其他违规",
     "文书确有食品安全违法行为，但不属于以上五类（如商标侵权、超范围使用添加剂、未履行进货查验等）。"),
    ("UNRESOLVED", "无法判定",
     "文书残缺、事实不足以判断，或同一文书同时构成多种类型且无法确定主类型。"),
]


def main() -> None:
    recs = [json.loads(l) for l in SILVER.open(encoding="utf-8")]
    zh = [r for r in recs if r.get("lang") == "zh"]
    by_id = {r["doc_id"]: r for r in zh}
    ids = sorted(by_id)

    rng = random.Random(SEED)
    srs = sorted(rng.sample(ids, N_SRS))

    pool = [d for d in ids
            if (by_id[d]["channels"] or {}).get("cat_a")
            and by_id[d]["channels"]["cat_a"] != by_id[d]["violation_category"]
            and d not in set(srs)]
    pool.sort(key=lambda d: hashlib.sha256(d.encode()).hexdigest())
    dis = pool[:N_DIS]

    items = [(d, "srs") for d in srs] + [(d, "disagreement") for d in dis]
    rng.shuffle(items)  # order is randomised; stratum is not shown

    cards, sample_rows = [], []
    for k, (d, stratum) in enumerate(items, 1):
        safe = d.replace(":", "_")
        p = CLEAN / f"{safe}.txt"
        text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        cards.append({"k": k, "doc_id": d, "text": text})
        sample_rows.append({"k": k, "doc_id": d, "stratum": stratum,
                            "text_sha256": hashlib.sha256(text.encode()).hexdigest()})

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # The sample itself is a pure function of (seed, frame, disagreement rule).
    # Digest that deterministic core so it is a stable anchor even though the
    # file-level sha necessarily moves when at_utc does.
    digest = hashlib.sha256(json.dumps(
        sorted([d, s] for d, s in items), ensure_ascii=False).encode()).hexdigest()
    if OUT_SAMPLE.exists():
        try:
            prev = json.loads(OUT_SAMPLE.read_text(encoding="utf-8"))
            if prev.get("digest") == digest and prev.get("at_utc"):
                now = prev["at_utc"]
        except Exception:
            pass
    sample = {
        "at_utc": now, "digest": digest,
        "seed": SEED, "n_srs": len(srs), "n_disagreement": len(dis),
        "n_total": len(items), "frame_n": len(ids),
        "silver_sha256": hashlib.sha256(SILVER.read_bytes()).hexdigest(),
        "disagreement_pool_n": len(pool),
        "rule": "S1 = Random(20261105).sample(sorted(ids), 60); S2 = first 20 of pool by sha256(doc_id)",
        "items": sample_rows,
    }
    tmp = OUT_SAMPLE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT_SAMPLE)

    btns = "\n".join(
        f'<button class="lb" data-v="{v}"><b>{v}</b><span>{name}</span></button>'
        for v, name, _ in LABELS)
    legend = "\n".join(f"<li><b>{v}</b> — {name}：{d}</li>" for v, name, d in LABELS)
    payload = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!doctype html>
<meta charset="utf-8">
<title>食品处罚文书编码表</title>
<style>
 body{{font:15px/1.6 -apple-system,"Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#1a1d21}}
 header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #d9dde3;padding:10px 18px;z-index:5}}
 h1{{font-size:16px;margin:0 0 4px}}
 .bar{{height:6px;background:#e6e9ee;border-radius:3px;overflow:hidden;margin-top:6px}}
 .bar>i{{display:block;height:100%;background:#2f6fed;width:0}}
 main{{max-width:900px;margin:0 auto;padding:18px}}
 .doc{{background:#fff;border:1px solid #d9dde3;border-radius:8px;padding:14px;white-space:pre-wrap;
      max-height:44vh;overflow:auto;font-size:14px}}
 .meta{{color:#666;font-size:12px;margin:0 0 6px}}
 button.lb{{display:block;width:100%;text-align:left;margin:6px 0;padding:9px 12px;border:1px solid #cfd5dd;
      background:#fff;border-radius:7px;cursor:pointer;font:inherit}}
 button.lb:hover{{border-color:#2f6fed;background:#f2f6ff}}
 button.lb b{{display:inline-block;min-width:210px;color:#2f6fed;font-size:12px}}
 button.lb.sel{{border-color:#1f9d55;background:#ecfbf2}}
 details{{background:#fff;border:1px solid #d9dde3;border-radius:8px;padding:10px 14px;margin:0 0 14px}}
 summary{{cursor:pointer;color:#2f6fed}}
 .foot{{margin-top:14px;display:flex;gap:10px}}
 #done{{display:none;background:#fff;border:1px solid #d9dde3;border-radius:8px;padding:16px}}
 textarea{{width:100%;height:120px;font:12px monospace}}
</style>
<header>
 <h1>食品安全行政处罚文书 — 违规类型人工编码</h1>
 <div class="meta">共 {len(items)} 篇 · 已编码 <b id="n">0</b>/{len(items)} · 每篇只选一项，不确定请选“无法判定”</div>
 <div class="bar"><i id="p"></i></div>
</header>
<main>
 <details><summary>类别定义（点开）</summary><ul>{legend}</ul></details>
 <details><summary>判断顺序 · 四步（必读）</summary>
  <ol>
   <li><b>找事实</b>：定位「经查明 / 经调查 / 现查明 / 经查」之后的段落。</li>
   <li><b>找依据</b>：找「违反了《…》第…条」与「依据《…》第…条…决定」这两句。</li>
   <li><b>定主行为</b>：以<b>处罚依据所罚的那个行为</b>为准；只在事实里提过、没被作为处罚依据的行为不算。</li>
   <li><b>按序匹配，命中即停</b>：检验报告 → 溯源 → 认证 → 标签虚假 → 无证 → 其他 → 无法判定。</li>
  </ol>
  <p><b>五个易错点：</b></p>
  <ul>
   <li>「标签不符合规定」但<b>内容不虚假</b>（未标配料表、格式错误）⇒ 选<b>其他</b>，不是标签虚假标注。</li>
   <li>商标侵权 ⇒ 选<b>其他</b>，不是虚假认证。</li>
   <li>处罚依据是无证经营条款 ⇒ 选<b>无证</b>，即使事实里提到标签问题。</li>
   <li>销售食用农产品<b>不需要</b>食品经营许可。</li>
   <li>「涉嫌…」是立案表述，<b>不作判据</b>；以「经查明」的事实为准。</li>
  </ul>
  <p>每篇 30–60 秒。不确定就选「无法判定」——硬猜会毁掉整个结果。</p>
 </details>
 <div class="meta">第 <b id="k">1</b> 篇 · 文书编号 <code id="did"></code></div>
 <div class="doc" id="doc"></div>
 <div id="btns" style="margin-top:12px">{btns}</div>
 <div class="foot"><button id="exp" style="padding:8px 16px;border-radius:7px;border:1px solid #2f6fed;background:#2f6fed;color:#fff;cursor:pointer">导出编码结果</button>
 <button id="undo" style="padding:8px 16px;border-radius:7px;border:1px solid #cfd5dd;background:#fff;cursor:pointer">上一题</button></div>
 <div id="done"><h3>已全部完成</h3><p>把下面这段 JSON 整段复制发回即可。</p><textarea id="ta"></textarea></div>
</main>
<script>
const CARDS = {payload};
const KEY = "foods_coding_v1";
let ans = JSON.parse(localStorage.getItem(KEY) || "{{}}");
let idx = Number(localStorage.getItem(KEY+"_i") || 0);
function save(){{ localStorage.setItem(KEY, JSON.stringify(ans)); localStorage.setItem(KEY+"_i", idx); }}
function render(){{
  const c = CARDS[idx]; if(!c) return finish();
  document.getElementById("k").textContent = idx+1;
  document.getElementById("did").textContent = c.doc_id;
  document.getElementById("doc").textContent = c.text || "(文本缺失)";
  document.querySelectorAll(".lb").forEach(b=>b.classList.toggle("sel", ans[c.doc_id]===b.dataset.v));
  const n = Object.keys(ans).length;
  document.getElementById("n").textContent = n;
  document.getElementById("p").style.width = (100*n/CARDS.length)+"%";
}}
document.querySelectorAll(".lb").forEach(b=>b.onclick=()=>{{
  ans[CARDS[idx].doc_id] = b.dataset.v; save(); idx++; save(); render();
}});
document.getElementById("undo").onclick=()=>{{ if(idx>0){{idx--; save(); render();}} }};
document.getElementById("exp").onclick=()=>finish();
function finish(){{
  const out = CARDS.map(c=>({{doc_id:c.doc_id, label: ans[c.doc_id] || null}}));
  const miss = out.filter(o=>!o.label).length;
  document.getElementById("done").style.display="block";
  document.getElementById("done").querySelector("h3").textContent =
      "已导出（未编码 "+miss+" 篇）";
  document.getElementById("ta").value = JSON.stringify(out);
  document.getElementById("ta").select();
}}
render();
</script>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(json.dumps({"at_utc": now, "n_srs": len(srs), "n_dis": len(dis),
                      "pool": len(pool), "html_bytes": OUT_HTML.stat().st_size,
                      "sample_sha": hashlib.sha256(OUT_SAMPLE.read_bytes()).hexdigest()},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

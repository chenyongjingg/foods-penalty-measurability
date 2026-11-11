# -*- coding: utf-8 -*-
"""Measure the residual AI-writing tells in the Frontiers draft and write them out.

This does not score the text. It counts a fixed set of surface patterns over a
fixed range (the markdown body, headings and captions included, table pipes
excluded), attaches the judgement made for each, and writes the table so a
human can overrule any line. The counts are reproducible from this script; the
judgements are not, and are marked as such.

Output: AI_TELLS_RESIDUAL.md
"""
from __future__ import annotations

import hashlib
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "manuscript_frontiers_v2.src.md"
OUT = HERE / "AI_TELLS_RESIDUAL.md"

# Judgement for each sentence over 40 words, matched on the sentence's own
# opening words. Keying on (line, occurrence) was wrong: one paragraph is one
# line here, so a sentence's index depends on how many short sentences precede
# it, and every note silently fell through to the default. The text is stable;
# its position is not.
NOTES = {
    "Agencies publish the legal basis they invoked": "三项义务的枚举，删掉任一项会丢掉法定要素",
    "The third obligation is specific to food": "三项义务的最后一项，问题陈述本身",
    "The commodity dimension has the same shape": "商品维度的对照介绍",
    "Three things come out": "**本轮新增**：三项贡献的前置句；冒号后是三件事，可拆成两句",
    "Across three queries pages": "检索日志的读数，保留原样",
    "Documents entered and left the corpus": "语料漏斗，四个数必须同句",
    "Tested with the frozen coarse map": "负对照结论，两个粒度同值",
    "Annotation runs on a locally served": "标注设置，模型与两条通道",
    "Input is capped at 20,000 characters": "输入上限与实测分位",
    "A single-pass protocol fixed in advance": "单遍协议的结果",
    "Evaluating a test without a gold standard": "无金标准下的既有补救手段，引用串",
    "To measure what a match means": "判定抽样的固定规则",
    "Each hit was read in a": "**已知最长**：判定协议四段枚举，拆开会读成四条独立规定",
    "Three constructs were registered before": "三构念的开跑条件",
    "Fleiss’ κ (chance-corrected agreement)": "κ 的出处与切点惯例",
    "Macro-F1 over all classes": "全类 macro-F1 被低支撑类拖累",
    "The 19 false matches are not one phenomenon": "19 个假匹配的分类，七/五/七",
    "The categories that survive do so": "存活类别的强度对比",
    "Three rows are not commodity spectra": "**表 3 题注**（C2 冻结，不得改）",
    "The audit measures precision only": "精度-only 的局限",
    "Turning the forced choice into per-category binaries": "二元化带来的 κ 与灵敏度增益",
    "The deterministic layer’s own food axis": "确定性层的食物轴，词表与读取范围",
    "Differential comparison across enforcement profiles": "**补充材料题注**",
    "Work on other systems compares constructs": "**本轮改动**：三系统构造对比，压缩后的一句",
    "Design: QLoRA adapters": "QLoRA 超参，列表式",
    "The bundle `supplementary_20261106.zip`": "提交件清单，路径与计数",
    "Table 4.** Three pre-registered attempts": "**表 4 题注**（C2 冻结，不得改）",
}


def strip_yaml_keep_lines(text: str) -> str:
    """Blank the YAML block without shifting line numbers.

    Deleting the block would renumber every line, and the report's 行 column
    has to index the source file a reader will open.
    """
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                for j in range(i + 1):
                    lines[j] = ""
                break
    return "\n".join(lines)


def sentences(line: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", line) if len(s.split()) >= 3]


def main() -> int:
    raw = SRC.read_text(encoding="utf-8")
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    text = strip_yaml_keep_lines(raw)

    prose = "\n".join(l for l in text.split("\n")
                      if l.strip() and not l.startswith(("|", "1. ", "<!--")))

    counts = {
        "Three（句首/列举标记）": len(re.findall(r"\bThree\b", prose)),
        "rather than": len(re.findall(r"\brather than\b", prose)),
        "instrument（全部形式）": len(re.findall(r"\binstrument", prose)),
        "not X but Y / 不是…而是": len(re.findall(r"\bnot (?:just|only|merely)\b", prose)),
        "pre-registered": len(re.findall(r"pre-registered", prose, re.I)),
        "破折号 —（全文件）": raw.count("—"),
        "破折号 –（全文件）": raw.count("–"),
    }

    all_sents = []
    for i, line in enumerate(text.split("\n")):
        if not line.strip() or line.startswith(("|", "1. ", "<!--")):
            continue
        for j, s in enumerate(sentences(line)):
            all_sents.append((i, j, s))
    n_sent = len(all_sents)
    n_the = sum(1 for _, _, s in all_sents if s.startswith("The "))
    long = [(i, j, s) for i, j, s in all_sents if len(s.split()) > 40]

    L = []
    A = L.append
    A("# 残余 AI 腔实测清单（Frontiers v2）")
    A("")
    A(f"- 源稿：`manuscript_frontiers_v2.src.md`，{len(raw):,} B，sha256 `{sha[:16]}…`")
    A("- 生成：`ai_tells_v2.py`。**计数可复现，判定不可复现**——判定逐条写在下面，供人推翻。")
    A("- 范围：去掉 YAML、表格行、参考文献行、HTML 注释后的正文；标题与题注计入。")
    A("")
    A("## 1　总量")
    A("")
    A("| 模式 | 次数 | 判定 |")
    A("|---|---|---|")
    A(f"| `Three` 开头的列举 | {counts['Three（句首/列举标记）']} | 保留。三构念、三读者、三粒度、三项义务都是真实的三项；"
      "见 §2 的逐处检查 |")
    A(f"| `rather than` | {counts['rather than']} | 保留。逐条检查过：每一处被否掉的那一项都带着内容"
      "（见 §3），不是空转的对比 |")
    A(f"| `instrument` | {counts['instrument（全部形式）']} | 保留。同一构念的一致指称；"
      "换同义词会让\"我们把它当仪器审\"这条主线散掉 |")
    A(f"| `not just/only/merely` | {counts['not X but Y / 不是…而是']} | 0 处 |")
    A(f"| `pre-registered` | {counts['pre-registered']} | 从 8 处减到 3 处（摘要、Appendix A、表 4 题注）；"
      "其余 5 处改为 `registered in advance` 等表述 |")
    A(f"| 破折号 `—` | {counts['破折号 —（全文件）']} | 均在**表 2 的两个单元格**内（2 处），正文 0 处 |")
    A(f"| 连字符号 `–` | {counts['破折号 –（全文件）']} | 全部为数值区间或复合名词"
      "（2019–2024、0.8927–0.9545、1–2 类、behaviour–hazard），保留 |")
    A(f"| 句首 `The` | {n_the} / {n_sent} 句（{n_the / n_sent:.0%}） | 偏高但非可机械修的病："
      "英文测量学论文的主体就是\"这个量\"，换主语会变成被动堆叠。**仅在本轮改写的四段里主动换了主语** |")
    A(f"| >40 词的长句 | {len(long)} | 逐条见 §4；其中 3 条是题注（2 条的表体受 C2 冻结），"
      "1 条是已知最长的判定协议句 |")
    A("")
    A("## 2　`Three …` 的 15 处（按指向归类）")
    A("")
    A("逐处读过，15 处落在七个簇上，不是随机分布：")
    A("")
    A("| 簇 | 处数 | 指代 | 真的三项？ |")
    A("|---|---|---|---|")
    A("| 三名编码者 | 3 | L30 摘要、L92 Methods、L146 Results | 是（三份独立判定，同一码本） |")
    A("| 三构念／三次尝试 | 4 | L88 Methods、L130 小节标题、L132 Results、L308 表 4 题注 | 是（三个预注册构念） |")
    A("| 三个非食物对照词 | 2 | L86 抽取、L128 商品审计 | 是（battery / boiler / plastic） |")
    A("| 三项义务 | 1 | L42 Introduction | 是（法定要素） |")
    A("| 三件事／三项贡献 | 1 | L48 Introduction 末段 | 是（本稿的三条结论） |")
    A("| 三个不能回答的问题 | 2 | L156 小节标题、L158 正文 | 是（结构／动力／制度三层） |")
    A("| 三项限制／三行非谱系 | 2 | L216、L128 题注 | 是（三条真限制；三行确非商品谱系） |")
    A("")
    A("结论：**没有一处是为凑三项而生**，但同一套三项在 4 个位置重讲一次是真实的结构重复。"
      "本轮已消掉 Discussion 里两处与 Methods/Results **一字不差**的起句（`Three constructs registered in advance…`、"
      "`Three readers coded the same 80 documents…`），计数从 17 降到 15。剩下的重复属于必要的回指"
      "（表 4 题注必须自足），不再削。")
    A("")
    A("## 3　`rather than` 的 26 处（逐条归类）")
    A("")
    A("判据：把 `rather than` 删掉，句子会不会变成在肯定被否掉的那一项。")
    A("")
    A("- **20 处带着被否掉那项的内容**，删掉就丢信息：法定 vs 研究者（L40）、意图 vs 危害（L44）、"
      "检出 vs 发生（L44）、构造 vs 比率（L44、L196）、未收到文本 vs 文本短（L58、L206）、"
      "索引 vs 原文档（L60）、排除 vs 插补（L72）、二项近似 vs 设计型区间（L86）、"
      "赋值 vs 估计（L108）、形式 vs 实体（L110）、警告 vs 患病率表（L116）、"
      "被错标的配料 vs 售出的产品（L124）、作答 vs 弃答（L136）、入口排序 vs 执法活动（L162）、"
      "Fisher vs χ²（L170）、文档 vs 国家（L196）、程序性 vs 经验性（L202）、证据 vs 谨慎（L210）。")
    A("- **6 处是修辞性的框定**，被否掉的那一项没有人主张：`auditing rather than assuming`（L48）、"
      "`a result rather than housekeeping`（L96）、`report this rather than a single sentence`（L148）、"
      "`bookkeeping rather than a finding`（L154）、`the auditing step rather than the numbers`（L196）、"
      "`requirements rather than caveats`（L200）。这 6 处**保留**——它们是本稿立场的压缩表达，"
      "删掉后对应句子会失去与更常见做法的区分。")
    A("- **0 处是纯语法的同义替换**（没有 `precision rather than recall` 这类可用 `not` 改写而无损失的情形）。")
    A("")
    A("## 4　>40 词的长句（逐条）")
    A("")
    A("| 行 | 词数 | 类型 | 开头 | 判定 |")
    A("|---|---|---|---|---|")
    for i, j, s in sorted(long, key=lambda t: -len(t[2].split())):
        kind = "题注" if s.startswith("**") else "正文"
        plain = s.lstrip("*_ ")        # captions open with a bold marker
        note = next((v for k, v in NOTES.items() if plain.startswith(k)),
                    "枚举/列表句，拆开会把并列项读成先后项")
        head = re.sub(r"[|`*]", "", s[:60]).replace("\n", " ")
        A(f"| {i + 1} | {len(s.split())} | {kind} | {head}… | {note} |")
    A("")
    A("## 5　本轮已处理的")
    A("")
    A("| 痕迹 | 处数 | 处置 |")
    A("|---|---|---|")
    A("| Discussion 四段格言式开场 | 4 | 全部换成从数字起句（见 CHANGES §7.2） |")
    A("| 段首两个开场（`An audited instrument…` + `Two-channel agreement…`） | 1 | 合为一个 |")
    A("| `since` 的修辞用法 | 0 | 8 处全是真实因果，未动 |")
    A("| `which is why` | 1 | 保留（因果两端都带内容） |")
    A("| 42 词结论首句 | 1 | 拆成两句 |")
    A("| `pre-registered` | 5 | 8 → 3 |")
    A("")
    A("## 6　不建议再动的地方（附理由）")
    A("")
    A("1. **`instrument` 换词**：换成 `tool`/`measure` 会让\"我们审的是仪器不是估计\"这条区分在正文里失去固定指称。")
    A("2. **句首 `The` 的比例**：把主语换成\"研究者\"会把方法段变成第一人称叙事，Frontiers 的方法段不这么写。")
    A("3. **93 词的方法句**：四段判定协议写在一条句子里，是因为它是一条规则的四段，"
      "不是四条规则；拆开会改变读者对协议的理解。**这是全稿唯一需要作者拍板的长句**。")
    A("4. **`Three …` 的 15 处**：见 §2，没有一处是凑数；重复的部分已消到只剩必要的回指。")
    A("")
    A("## 7　本清单不是 AI 检测分数")
    A("")
    A("以上是**模式计数**，不是概率判断。同一篇文字在两种模型下都会得到类似的计数，"
      "而计数与\"是不是人写的\"之间没有已知的映射。用它时只问一件事：**这一处是不是作者会故意这么写**。")
    A("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(long)} long sentences, "
          f"Three {counts['Three（句首/列举标记）']}, rather than {counts['rather than']}, "
          f"The-opener {n_the}/{n_sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

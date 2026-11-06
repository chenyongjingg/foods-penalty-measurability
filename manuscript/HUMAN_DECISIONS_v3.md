# HUMAN_DECISIONS_v3 — 需作者裁定的事项

**读法** 每项给「问题 / 我的推荐 / 若不同意则改哪里」。推荐不是裁决，全部可推翻；未勾选前，稿件按「推荐」这一列的状态保存。
**当前状态** `manuscript_submission_v3.docx` 已按下列推荐值构建完毕。

---

## 第 1 项（任务书必列）移入 Supplementary 的内容确认

压缩过程中有一批材料从正文移出。**必须由作者确认**，因为移出即意味着读者要打开补充包才能复核。

| # | 原文位置 | 移出内容 | 现在的落点 | 正文留下的指针 |
|---|---|---|---|---|
| 1 | §2.1 | 门户机制的逐页举证：三个查询各 4 页各 50 行、第 5–6 页为空 | `data/reports/portal_mechanics.json`（2026-11-05T04:54:41Z） | `both properties are recorded as a product (...)`，三个日期仍留在正文 |
| 2 | §2.5 | `osmanthus` + `production` 生成 `peanut` 的跨词边界完整推演 | 补充裁决文件 `data/analysis/e12_commodity_precision.json` 所依据的裁决表 | `worked examples are in the supplementary adjudication file` |
| 3 | §3.3 | 19 个假匹配的四类**完整枚举** | 同上补充裁决文件 | 保留四类判语 + 两类代表（地名/公司名、跨词边界） |
| 4 | §3.10 | 「逐级清单」（每一级问题 + 其状态的一段罗列） | Figure 1 + Table 1 + `numbers.csv` | `every number it prints is licensed by a row of Table 1 or of the supplementary numbers file` |

**推荐** 确认全部四项。
**理由** 四项都是**举证**而非**论断**：被移走的每个数字在别处（表格、产品文件）仍可查，论断句与其限定语全部留在正文。第 1 项的三个日期因属冻结项而保留在正文，故其实只移走了「四次翻页」的过程描述。
**若不同意** 第 3 项最容易回填（四类各一句，约 60 词），但会把总词数推过 7,200，须从 Discussion 再删等量。

**另需注意**：§2.7 关于 DEVIATIONS 编号冲突的两句（`two consecutive new entries first written under numbering already in use`）是**删去**而非移入补充材料——它描述的是装置自身的记账史，不支撑任何论断。若作者认为它是对审稿人展示严谨性的证据，应回填并注明。

---

## 第 2 项（任务书必列）新文献的最终取舍

从 12 条扩到 29 条，新增 17 条，**全部经 Crossref DOI 记录核验**（明细见 `EDIT_LOG_v3.md` 任务 D 表）。

| 编号 | 文献 | 挂载命题类型 |
|---:|---|---|
| 1 | Robson et al. 2021, *Food Control* | 定义（食品欺诈术语分歧） |
| 2 | Jacobs & Wallach 2021, ACM FAccT | 方法学前提（信度≠效度） |
| 6 | Soon 2020, *Food Control* | 数据来源（中国执法数据的建模用法） |
| 10 | Kang 2019, *Food Control* | 制度背景 |
| 15 | Gentzkow et al. 2019, *JEL* | 方法学前提（文本即数据） |
| 16 | Grimmer & Stewart 2013, *Political Analysis* | 方法学前提 |
| 19 | Chen et al. 2026, *PLOS One* | 数据来源（openFDA） |
| 20 | Luscombe et al. 2022, *Quality & Quantity* | 合规采集 |
| 21 | Ziems et al. 2024, *Computational Linguistics* | 方法学前提（LLM 作标注者） |
| 22 | Rutjes et al. 2007, *HTA* | 方法学前提（无金标准） |
| 23 | Collins & Huynh 2014, *Statistics in Medicine* | 同上（潜类方法支） |
| 24 | Umemneku Chikere et al. 2019, *PLOS ONE* | 同上（系统综述支） |
| 25 | Fleiss 1971, *Psychological Bulletin* | 统计量出处 |
| 26 | Landis & Koch 1977, *Biometrics* | 判读门槛 |
| 27 | Byrt et al. 1993, *J. Clin. Epidemiol.* | κ 的性质 |
| 28 | Nosek et al. 2018, *PNAS* | 预登记 |
| 29 | Chambers 2013, *Cortex* | 预登记（Registered Reports 支） |

**推荐** 全部保留。
**理由** 每条都挂在**既有命题**上（不新增论断），且**没有一条**支撑本研究的实测数字（任务 D3 逐条核对通过）。
**两处需作者点头的著录细节**
- **Luscombe（#20）**：DOI 记录的 `issued` 是 2021-05-24（online first），`published-print` 是 2022-06，卷 56、期 3、页 1023–1044。现按 **2022** 著录。若 Foods 要求以 online-first 年著录，改成 2021，卷页不变。
- **Rutjes（#22）**：HTA 专著以**期号代文章号**（Crossref：卷 11、期 50、page 为空），现著录为 `2007, 11, 50`。

**若不同意** 删任意一条只需删除对应 `{key}`，编号由 `_tools/v3_resolve_refs.py` 自动重排，不会留下空号。

**另外两条旧文献仍待定**（v2 遗留，本轮未动）
- **[5] Gao (2020) SSRN preprint**：任务书明确「现有 SSRN 条目保留」，故保留。若 Foods 不接受预印本，需换成正式发表版或删除。
- **[13] 刘文静（2022）中文期刊**：非英文文献，若能补英文译名与 DOI 更好。

---

## 第 3 项（任务书必列）是否向 Foods 编辑部发 presubmission 询问

**推荐** 发。
**理由** 本稿有两点是编辑很可能要问、且提前问能省一轮的：
1. **文章类型**：现按 **Article** 构建（此前讨论过 Brief Report / Communication，已定 Article）。Foods 对 Article 无硬性页数上限但期望完整论证；本稿 7,200 词＋4 表 1 图，属标准 Article 体量。
2. **数据可得性**：稿件把相当一部分证据放在补充包（25 件产品文件 + `MANIFEST.md`），并向期刊承诺「每个统计量可解析到文件、字段、时间戳、哈希」。这类承诺最好在投稿前与编辑部确认格式要求（是否随稿上传、是否需 Zenodo/ScienceDB 托管）。

**建议的问法（三句）**
> We are preparing an Article for Foods on auditing Chinese administrative penalty decisions as a measurement instrument for food-safety violations. Before submission we would like to confirm two points: (i) whether a supplementary bundle of 25 data and script files, with a manifest and hashes, is acceptable as the sole data-availability route, or whether deposition in a repository is expected; (ii) whether the journal has a preferred handling for manuscripts whose central result is a negative or boundary result rather than a positive performance claim.

**若不同意** 不发也不影响投稿；上述两点会在审稿意见里被问到，届时回复即可。

---

## 第 4 项 `CONFLICT_REVIEW_v3.md` 的 4 项疑似不一致

这四项本轮**一律未改**，需作者裁定（详见该文件）：

| 编号 | 一句话 | 我的建议 |
|---|---|---|
| CR-1 | `top-tier` 文档在 §3.7/§3.9 是 128，在 Appendix A 是 228 | 查 E9 与 §3.7 的产品文件；若 228 含英文，正文加 `(228 across both genres)` |
| CR-2 | 分词删失 38 项只分解了 20 项 | 改为「包括…」的举例句式，或补齐剩余 18 项归属 |
| CR-3 | 摘要中 `0.7460 agreement` 与 `micro-F1 0.7825` 相邻，易被读成同一量的两个版本 | 维持现状（文中已有两处限定语）；若编辑提出，再用 `and separately, against the statute anchor` |
| CR-4 | E16 的 `818 of 1,128` 与「已拒答 232 篇」的分母关系未言明 | 明确分母；并说明拒答篇是否计入 category 0 |

**优先级** CR-4 > CR-1 > CR-2 > CR-3。前两项影响对结果的解释，后两项只影响表述。

---

## 第 5 项 Results 首句的「问句形式」

任务 C2 要求「问句＋一句结论」。现稿十个子节**全部是结论先行**，但只有三个子节标题本身是问句形式。

**推荐** 维持结论先行。
**理由** 逐节加问句约需 +60 词，在 7,200 词硬顶下只能靠再删论证句换；且十连问句是模板化语域。若审稿人另有偏好，改动集中在十句之首，不影响正文其余部分。
**若不同意** 告知要哪几节改（建议只改 3.1 / 3.2 / 3.6，这三节的首句最接近「裸测量值」）。

---

## 第 6 项 作者信息与声明（v2 遗留，未变）

- **ORCID**：CRediT 表中五位作者均未填 ORCID。Foods 投稿系统要求通讯作者 ORCID。
- **CRediT 分工**：现表为**代拟**，需五位作者逐项确认（尤其 Y.C. 与 C.Y. 的 Data curation / Formal analysis 双挂）。
- **基金**：`25CSH113` 已在正文与 Statements 在位。
- **仓库与 MANIFEST**：本轮的 v3 改动**尚未**推送仓库，`supplementary/MANIFEST.md` 也未 bump。若补充包要随稿上传，须在定稿后重跑 `verify_numbers` 并更新 25/25 校验块。**这一步我没有替你做**，因为它会把 v3 的数写进一份此前对 v2 校验通过的清单里。

---

## 一页速览

| # | 事项 | 推荐 | 阻塞投稿？ |
|---|---|---|---|
| 1 | 四项移入 Supplementary | 确认 | 否（可回填） |
| 2 | 17 条新文献 | 全留；确认 Luscombe 年份 | 否 |
| 3 | 给编辑部 presubmission 邮件 | 发 | 否 |
| 4 | CR-1…CR-4 | 先裁 CR-4、CR-1 | **是**（CR-4 影响解释） |
| 5 | Results 问句形式 | 维持结论先行 | 否 |
| 6 | ORCID / CRediT / MANIFEST | 需本人填 | **是** |

<!-- v3.1 adjudication 2026-11-06 -->

---

## 裁决回执（2026-11-06）

**已裁** 第 4 项（CR-1…CR-4）已按 `CONFLICT_REVIEW_v3.md` 新增的「裁决记录」执行：CR-1 补 `(128 Chinese, 100 English)`、CR-2 补齐 13 mentions + 5 statute citations、CR-4 改为 586/896 并单列 232 篇拒答、CR-3 不动。

**仍未裁（阻塞投稿）**
- 第 6 项的 ORCID 与 CRediT 五人确认：仍是代拟，须作者本人逐条确认。
- **补充包与正文已不同步**：正文现为 **29 条参考文献**，而 `supplementary/refs_crossref.json` 仍是 **12 条**（6,311 B），`supplementary/MANIFEST.md` 仍是 v2 的 25/25 校验块。本轮按作者指示**未动补充包**；投稿前必须同步，否则正文引用的 17 条新文献在补充包里没有登记记录。
- 第 2 项的 Luscombe 年份（2021 online-first / 2022 print）与第 1、3、5 项（移出确认、presubmission 邮件、Results 问句形式）维持原推荐，等作者一句话即可。

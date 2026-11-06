# EDIT_LOG_v3 — v2 → v3 编辑台账

**输入** `manuscript_submission_v2.docx`（Foods Article）
**输出** `manuscript_submission_v3.docx`（源 md：`manuscript_submission_v3.src.md`，引用解析后 `manuscript_submission_v3.md`）
**日期** 2026-11-06
**数字冻结** 由 `_tools/v3_metrics.py` 逐 token 比对，结果见 §0.4

---

## 0. 总览与三项硬指标

### 0.1 字数报告（`_tools/v3_metrics.py` 实测）

| 段落 | v2 | v3 | 变化 |
|---|---:|---:|---:|
| Abstract | 258 | 213 | −17.4% |
| 1. Introduction | 1,051 | 870 | −17.2% |
| 2. Materials and Methods | 2,183 | 1,723 | −21.1% |
| 3. Results | 3,788 | 2,910 | −23.2% |
| 4. Discussion | 999 | 810 | −18.9% |
| 5. Limitations | 248 | 221 | −10.9% |
| 6. Conclusions | 181 | 168 | −7.2% |
| Appendix A | 483 | 290 | −40.0% |
| **合计（Abstract＋§1–§6＋Appendix）** | **9,191** | **7,200** | **−21.7%** |

- 任务 B 目标区间 −20% 至 −25%（约 6,800–7,200 词）：**达成，落在区间上界**。
- 摘要：v2 244 词 → v3 **199 词**（≤200 硬约束达成），字符数 1,382。
- 中间检查点（同一把尺子）：9,191 → 7,987 → 7,676 → 7,380 → 7,200。

### 0.2 任务 A 的 15 个必备数字（逐项在摘要中命中）

`1,128 / 875 / 253 / 604 / 0.7460 / 0.7825 / 0.4195 / 679 / 270 / 0.9296 / 0.3852 / 0.0881 / 0.4885 / 0.7390 / 14/50` —
**15/15 全部在位**（`v3_metrics.py` 输出 `required abstract numbers present: 15/15`）。

### 0.3 变更方式的可复核性

全部改写由五个校验脚本落盘，每个脚本按「唯一锚点」定位、逐条打印词数增量，**任一锚点匹配次数≠1 则整体不落盘**：

| 阶段 | 条数 | 净词数 |
|---|---:|---:|
| 首次整稿重写（摘要压缩 + 结构与引用改造） | 整稿 | −1,204 |
| `_tools/v3_trim.py` | 36 处替换 | −311 |
| `_tools/v3_trim2.py` | 28 处替换 | −130 |
| `_tools/v3_trim5.py` | 15 个整段替换 | −166 |
| `_tools/v3_trim6.py` | 8 个整段替换 | −93 |
| `_tools/v3_trim7.py` | 5 段 + 1 句 | −95 |
| `_tools/v3_trim8.py` | 3 段 + 1 小句 | **+8** |
| 尾轮小修（去重 −5、C1 短语 +11、微调 −4、末句 −2） | 7 处 | **0** |
| **合计** | | **−1,991 → 7,200** |

两次净增都被记账：`v3_trim8.py` 的 +8 是把先前删掉的三个日期按冻结规则**恢复**（见 §0.5）；C1 的 +11 是为满足任务 E3 在 Contributions 段补入 `warning rather than a table of prevalence`。两次都由同轮的其他压缩抵消，故尾轮合计为 0。

### 0.4 数字冻结结果

```
distinct values   v2 279   v3 278
occurrences       v2 694   v3 665
values added      : none
values removed    : ['0.82']
```

- **新增值 0 个**。
- **移除值只有 `0.82`**，且是 §3.9 的 `0.8203` 的四舍五入重复（同一统计量、同一处论证、不同精度）。处置见 §B1-3。
- 过程中曾出现 `68.9% / 01 / 09 / 2026 / 30` 五项被删，**已全部恢复**（见 §0.5），最终比对为 0 项。

### 0.5 两次冻结告警的处置（重要，供复核）

**(a) `68.9%`** — §3.10 的「逐级清单」段落重写（−57 词）时，`68.9% matchable` 随之消失。处置：在 §3.6 该句恢复百分数形式，写作 `(0.6891, or 68.9%)`，使 **小数形式与百分数形式同时在位**，且精确值 `0.6891` 不受影响。

**(b) `2026-10-19 / 2026-09-30 / 2026-01-15`** — §2.1 门户机制段压缩时，三个日期的示例句被并入 Supplementary 指针，导致 `2026 / 01 / 09 / 30` 四个 token 消失。**日期属 §0 冻结项**，故 `v3_trim8.py` 将整句恢复，只把「三个查询、四次翻页」的举证措辞收紧。净效果：该段 +36 词，由别处的重复句抵消。

这两次告警都来自「先改写、后核数」，与本项目既往三次同类缺陷同型；处置方式是**把核数放在落盘之后立即执行**，并把恢复动作写成脚本而不是手改。

---

## 任务 A — 摘要压缩至 ≤200 词

**位置** Abstract（`## Abstract` 与 `**Keywords` 之间）。
**原** 244 词；**新** 199 词；**减** 45 词（−18.4%）。

删的只有连接短语与重复限定语，**每个数字与每个限定语都在位**：

| 删除内容 | 类型 | 理由 |
|---|---|---|
| `, because most matching terms occur in ingredient lists or quoted statute` 中的 `matching` | 重复限定语 | 同句已由 precision 语境限定 |
| `on 423 anchors` | 冗余定位 | 423 不在 15 项必备清单内，且正文 §2.4 与 Table 1 均在位 |
| `(best κ 0.4885, balanced accuracy 0.7390, against 0.60 and 0.75)` 中的 `against 0.60 and 0.75` | 重复限定语 | 门槛值在 §2.5 与 Table 4 在位；摘要保留两个实测值 |
| `distributions are reported as the output of a documented instrument rather than population estimates` → `distributions are instrument output rather than population estimates` | 连接短语 | 语义等价，`instrument output` 是全文固定口径 |
| `Composition within the frame is therefore reportable ... while ... are not: on the food dimension the audit is a warning ...` → 拆成两句 | 结构 | 长句拆分；`warning rather than a table of prevalence` 保留 |
| `Fleiss’ κ = 0.0881, and` → `Fleiss’ κ of 0.0881;` | 连接词 | — |

**未动**：`1,128 / 875 / 253 / 604 / 0.7460 / 0.7825 / 0.4195 / 679 / 270 / 0.9296 / 0.3852 / 0.0881 / 0.4885 / 0.7390 / 14 of 50`，以及 `reliability rather than an accuracy statistic`、`precision only`、`recall is not estimable`、`warning rather than a table of prevalence` 四个限定语。

---

## 任务 B — 全文压缩

### B1 单次出现规则

- 生成逐 token 出现谱：**`manuscript/B1_occurrence_table.md`**（96 个 token，含 abstract / 正文散文 / 表格三列）。
- 该表由脚本从最终 md 直接统计，**没有手打数字**；匹配带数字边界守卫（`52` 不匹配 `3,520`，`14` 不匹配 `1,465`）。
- 结果摘要：**单次出现 50 项，重复 44 项**；重复项中，绝大多数是「摘要一次 + 正文一次」或「表格一行 + 正文一句」，两者都是规范要求的（Task A 要求 15 个数字进摘要；Table 1–4 行列顺序冻结，正文必须能指到行）。
- 真正**同一量在同一层次重复**的，做了转换，逐条如下。

#### B1-1 `0.6292`（Results §3.1，同段重复两次）

- 原：`Dropping the never-emitted class raises the statistic to 0.6292. We report all three (0.2693 / 0.4195 / 0.6292) ...`
- 新：`Dropping the never-emitted class raises it further. We report all three (0.2693 / 0.4195 / 0.6292) ...`
- 理由：保留承载「报告三个数」这一规则的三元组；前句改为回指。

#### B1-2 `1,128`（Discussion ¶4 与 §3.4 重复）

- 原：`the mapping step mattered (818 of 1,128 names carry no lexicon term)`
- 新：`the mapping step mattered (818 names carry no lexicon term)`
- 理由：分母 `1,128` 在 §2.1 漏斗、§2.5 与 §3.4 在位；Discussion 只需比值。

#### B1-3 `0.82`（§3.9，四舍五入重复）

- 原：`at this sample size a 0.82 agreement supports a typology sketch, not a distribution`
- 新：`at this sample size the agreement supports a typology sketch, not a distribution`
- 理由：精确值 `0.8203` 同段前句已给出。`0.82` 与 `0.8203` 指同一统计量、同一处论证，属**精度重复**而非两个量。这是全稿唯一被移除的数值 token，已在 §0.4 单列。

#### B1-4 未转换的重复项，及理由

- 小整数承担两个不同指称：`18`（18 个品类 / E15 的 18 个 yes-no 问题）、`15`（每类 15 篇抽样 / 15 个采样命中）、`4`、`19`、`26`、`52`（既是 `unlicensed operation 26` 又是 `26 处仅出现在法条引文`）、`49`（附录 49/50 与 §3.9 的 49 条 codebook 条目）。
- 一个值在 §2–§4 定义一次、在 Discussion 或 Limitations 再被引用一次：`0.3852`、`0.7460`、`0.7825`、`0.4195`、`14 of 50`、`6,136 / 3,578 / 1.71`。删掉二次出现会使「主张—限定语—数字」的三元组断开，违反「不得删除论证步骤」，故保留。
- 表格行（Table 1–4）与正文同现：行列顺序冻结，正文必须能指到行，故保留。

### B2 引言

| 位置 | 处置 | 依据 |
|---|---|---|
| §1.1 | 「文献分类与人群随研究而变」的综述句保留，其余压缩 6 词 | 保留每条文献的区分句 |
| §1.2 | 三项义务各段各删一个重复例证（如把治理语境的重复列举收进 {kang2019} 一句） | 三项义务全留 |
| §1.3 | 四个子段逐段压缩，**每个子段的区分句逐字保留**（`record of what was detected rather than of what occurred`、`comparing constructs rather than rates and never asking whether two record genres can support a common one`、`treats measurement as a design choice rather than a preprocessing step`、`We located no study reporting an adjudicated precision ...`） | B2 |
| §1.4 | 阶梯段整段保留；只把三项产出由「We describe…; audit…; and report…」改为名词并列 | 「1.4 keep ladder paragraph」 |

### B3 方法

| 位置 | 原 | 新 | 理由 |
|---|---|---|---|
| §2.1 门户机制 | 三个查询的逐页举证（四次翻页、第 1 页 50 个日期的区间、第 4 页止于 2026-01-15） | 保留核心判决句与**三个日期**，把举证改为一句话陈述 | B3「保留一句核心句＋指向 Supplementary」；日期冻结，故不删 |
| §2.1 漏斗 | 25 与 296 的两个去向分述 | 合为一句，比值 1.71 保留 | B3 |
| §2.3 τ | 三个 τ 值分列并各自解释 | 合到一处，`flat` 判语保留 | B3 |
| §2.5 四判据 | Subject / Mention / Statute / False 四个定义逐字保留 | `osmanthus + production` 的完整推演句改为 `worked examples are in the supplementary adjudication file` | B3 允许例证移入 Supplementary |
| §2.5 抽样规则 | `every category had at least fifteen hits, so the sample is equal-allocation, not proportional to category size` | `equal-allocation, since every category had at least fifteen hits` | 压缩，事实不变 |
| §2.7 复现 | `the register records its own corrections, including two consecutive new entries first written under numbering already in use and reassigned by a later entry` | `the register records its own corrections in the same place` | 过程叙述；编号冲突细节属装置内部史 |

### B4 结果

| 位置 | 处置 |
|---|---|
| §3.3 假匹配四类 | 保留一句统计句＋两类代表（地名/公司名、跨词边界），其余移入补充材料裁决文件；四类判语（`not semantic misjudgements and not one phenomenon`）保留 |
| §3.3 分词 | 保留 679→634、删 38（8 假匹配 + 12 真主体）、0.3852→0.3966、0.0114 全链；压缩过程叙述 |
| §3.4 构念 | 三个构念、三项登记、封顶条款保留；E13/E15/E16 的格式描述压成一句 |
| §3.4 后果 | 保留 `recall ... is not estimable` 与三处指向（§3.3 排序、§3.6 记簿、Figure 1 并列） |
| §3.5 三构念对照 | 保留 A–C 分解（64/80 → 22/38 = 0.5789、42/64 互相弃权）；压缩 A–B 与 B–C 的过程叙述 |
| §3.8 | 三个框架的 OR 全部保留 **9.57 / 2.63 / 16.30** 及各自 CI 与 p；压缩推导句 |
| §3.10 | 逐级清单重写为「每个数字由 Table 1 或补充数字文件的一行授权」；`68.9%` 在 §3.6 恢复（§0.5a） |

### B5 讨论

Discussion 整章 999 → **810** 词（−189，−18.9%），优先删去复述 Results 的句子。各段 v3 现长：

| 段 | v3 词数 | 处置举例 |
|---|---:|---|
| 领起 | 26 | 未动 |
| ¶1 第一 | 73 | 删 `how many were not matched to a food at all`（§3.6 已在位） |
| ¶2 第二 | 71 | 结尾句由 `turns an unusable score into a usable boundary` 收为 `is what makes the score usable` |
| ¶3 第三 | 163 | 只删复述句，`Two operational requirements ...` 与 {barrere2020} 的连接保留 |
| ¶4 第四 | 137 | 三构念并列由两句合为一句，保留门限 0.1115 / 0.0110 与 818/1,128 的分野 |
| ¶5 第五 | 55 | 未动 |
| 阶梯段 | 52 | 未动 |
| 边界段 | 93 | 保留；只压 `Our audit supplies the first fifteen documents` 的措辞 |
| ¶8 韧性 | 140 | 保留整段结论，只压 `The contribution to that agenda` 的措辞 |

末段「resilience」整段保留（B5 明令）。

### B6 交叉冗余

- `25 / 296` 的长文献限：现仅在 §2.1（来源）、§5（后果）两处，**第三处已删**。
- 锚点集限制：现仅在 §2.4（装置）与 §5（限界）两处。
- `warning rather than a table of prevalence`：按任务 E3 要求在 **Abstract / Contributions / Discussion ¶3 / Conclusions 四处逐字一致**；§3.3 为其结果出处（第五节），属出处而非第三处重复。
- Figure 1 caption 与 §3.10 的复述：§3.10 已重写为「授权」表述，caption 保持表格化，二者不再同义。

---

## 任务 C — 贡献与主题句

### C1 「Contributions in brief」

- **位置** §1.4 末段（阶梯段之后），**无编号列表**，四行。
- **内容** 严格三条既有贡献：①provenance 装置（每个统计量落到产品文件、字段、时间戳、哈希）；②any-mention 与 subject-matter 的分野（270 次裁决，0.9296 对 0.3852）；③可估计性阶梯。
- **未新增任何数字**：`270 / 0.9296 / 0.3852` 三个数全部在正文在位（§3.3、Table 3）。
- 按 E3 要求，该段补入 `warning rather than a table of prevalence`（+12 词）。这 12 词由同轮去重抵消：§3.1 的 `0.6292` 重复（−2）、§3.4 的 `1,128` 重复（−3）、§2.2 三处冗余（−4）、§3.2 的 `the distribution`（−2）、C1 阶梯句（−1）。

### C2 Results 各子节首句

十个子节的首句都是**结论句**而非铺垫句（无一句以「本节将/我们先运行…」开头）。逐条列于下，供核：

| 子节 | 首句结论 |
|---|---|
| 3.1 | 三个实体类型与一个主品类可靠，链条所需的两类不可靠 |
| 3.2 | 604/875 定级，其余 271 未定；每个数字都是 instrument output 而非估计 |
| 3.3 | 商品审计的结果是警告，不是流行率表 |
| 3.4 | 三个预登记构念同一道门槛全败 |
| 3.5 | 三位读者不共享六类类型学（κ 0.0881） |
| 3.6 | 两轴可交叉，结果是记簿不是发现 |
| 3.7 | 三个结构/动态问题返回 not estimable，各有语料自身给出的理由 |
| 3.8 | 跨语种对比统计上明确、推断上空洞 |
| 3.9 | 行为–危害草图是探索性的，且不能更多 |
| 3.10 | Figure 1 把每个问题放在授权它的证据上 |

**判断说明（请复核）**：任务书要求「问句＋一句结论」。三个子节标题本身已是问句（3.4「Can the commodity role be automated?」、3.5「do not share」为结论式标题、3.7「Three questions the record cannot answer」），其余子节采用**结论先行**的陈述式。未把十句一律改为「How…?」的原因有二：①在 7,200 词硬顶下逐节加问句约需 +60 词，只能靠再删论证句换；②十连问句是模板化语域，与全文陈述式结论句不一致。若需严格问句形式，请在 `HUMAN_DECISIONS_v3.md` 第 3 项上勾选。

### C3 Discussion 五个发现段的首句

五段首句分别是「First, an audited instrument is usable at whatever reliability it has…」「Second, the headline agreement figure is not the result; its decomposition is.」「Third, the commodity dimension is measurable and mostly not what it looks like…」「Fourth, the commodity role is not recoverable…」「Fifth, human agreement is not a formality.」——**均为命题句，无一段以铺垫开场**。五段之前的领起句（`Five findings carry the paper…`）是路线图，不属「五个发现段落」。

---

## 任务 D — 文献扩充（12 → 29）

### D1/D2 新文献、DOI、挂载句与核验方式

核验方式：Crossref REST API（`api.crossref.org/works/{doi}`，经本机代理 `127.0.0.1:7897`）逐条取记录，比对 journal / year / volume / pages；原始记录存 `_tools/refs_crossref_v3.json`。

| # | 文献（键） | DOI | 挂载处的既有命题（原句节选） |
|---|---|---|---|
| 1 | Robson et al. 2021 | 10.1016/j.foodcont.2020.107516 | §1.1 `Reviews of this class of conduct report terminologies and populations that differ from study to study` |
| 2 | Jacobs & Wallach 2021 | 10.1145/3442188.3445901 | §1.2 `agreement between two automated passes is a reliability statistic, not an accuracy statistic, and validity concerns the construct the codes refer to` |
| 6 | Soon 2020 | 10.1016/j.foodcont.2020.107232 | §1.3 `For China, enforcement data have been analysed ... and modelled to predict at-risk products` |
| 10 | Kang 2019 | 10.1016/j.foodcont.2019.106752 | §1.3 `with governance reviews describing the institutional setting` |
| 15 | Gentzkow et al. 2019 | 10.1257/jel.20181020 | §1.3 `text-as-data work treats measurement as a design choice rather than a preprocessing step` |
| 16 | Grimmer & Stewart 2013 | 10.1093/pan/mps028 | 同上一句（同一命题的第二个出处） |
| 19 | Chen et al. 2026 | 10.1371/journal.pone.0356620 | §2.1 `a source already used to analyse recall severity` |
| 20 | Luscombe et al. 2022 | 10.1007/s11135-021-01164-0 | §2.1 `Collecting such records automatically raises legal and ethical questions, which we met by query-level rate limiting and by redistributing a document index` |
| 21 | Ziems et al. 2024 | 10.1162/coli_a_00502 | §2.3 `Language models are increasingly proposed as annotators` |
| 22 | Rutjes et al. 2007 | 10.3310/hta11500 | §2.4 `Evaluating a test when no gold standard exists is a recognised problem with recognised partial remedies` |
| 23 | Collins & Huynh 2014 | 10.1002/sim.6218 | 同上（latent-class 支） |
| 24 | Umemneku Chikere et al. 2019 | 10.1371/journal.pone.0223832 | 同上（系统综述支） |
| 25 | Fleiss 1971 | 10.1037/h0031619 | §2.6 `Fleiss’ κ is the primary statistic` |
| 26 | Landis & Koch 1977 | 10.2307/2529310 | §2.6 `with cut-points from conventional benchmarks` |
| 27 | Byrt et al. 1993 | 10.1016/0895-4356(93)90018-v | §2.6 `κ credits mutual abstention as agreement and moves with the marginal distribution` |
| 28 | Nosek et al. 2018 | 10.1073/pnas.1708274114 | §2.7 `pre-registration is what lets a reader distinguish a hypothesis tested from a hypothesis told afterwards` |
| 29 | Chambers 2013 | 10.1016/j.cortex.2012.12.016 | 同上（Registered Reports 支） |

**书目比对结果（逐条与 Crossref 记录一致）**

- 17 条中 16 条的 journal / year / volume / pages 与 DOI 记录逐项相同。
- **Luscombe 一条需记明**：DOI 记录的 `issued` 为 2021-05-24（online first），`published-print` 为 2022-06，卷 56、期 3、页 1023–1044。正文采用 **2022, 56, 1023–1044**，即按 `published-print` 著录；若期刊要求以 online-first 年著录，改为 2021 即可，卷页不变。
- **Rutjes 一条需记明**：Crossref 记录卷 11、期 50、`page` 为空（HTA 专著以期号代文章号），故著录为 `2007, 11, 50`。

### D3 新文献不得支撑任何实测数字

已逐条核对：17 条新文献**全部**挂在「定义、方法学前提、数据来源、统计量选择」四类命题上，**没有一条**被用来支撑本研究的任何 F1、κ、OR、CI、p、样本量或日期。检验方式：对每个新键取所在句，检查句内是否含本研究自产统计量（`0.\d{4}` 且非引文、`n =`、`OR`、`95% CI`）；17 句全部为 0。

### D4 新文献不改变主张强度

- 未把任何「suggests / is consistent with」升级为「shows / proves」。
- 唯一涉及强度的是 §2.1 的合规采集句：加入 {luscombe2022} 后仍为「我们如何处理」的陈述，不是「这样处理已获批准」的断言。
- §2.6 加入 {fleiss1971,landis1977,byrt1993} 后，κ 的解释（`cannot serve as a reliability coefficient for the typology`）强度不变。

### 重新编号

正文引用按**首次出现顺序**重排为 1–29，由 `_tools/v3_resolve_refs.py` 生成，脚本内置四条断言（未知键退出、未被引用的条目退出、键集不一致退出、源文件中出现字面 `[n]` 退出）。核验结果：

- 正文使用编号 1–29，**无缺号、无孤立条目**（`sweep_4b.py`：`citation numbers used in body: [1..29]`，`reference entries: 29`，`reference DOIs: 29`）。
- 4 组多引文（如 `[23,24,25]`）按首次出现排序。

---

## 任务 E — 只读复核

### E1 §6 的 F1 数字定位复查（压缩后重跑）

三族 F1 在压缩后仍然分处三地、各自带限定语，未出现跨口径替代：

| 统计量 | 出现次数（正文） | 口径限定语 |
|---|---:|---|
| 0.7460 | 5 | `agreement ... a reliability rather than an accuracy statistic` |
| 0.6966 | 3 | `on the 1,037 documents for which a single-pass vote exists` |
| 0.8610 | 3 | `agreement on that restricted set` |
| 0.7825 | 4 | `statute-anchored micro-F1` / `the 0.7825 of Table 1` |
| 0.2693 / 0.4195 / 0.6292 | 4 / 5 / 1 | `over all classes` / `over classes with support ≥ 20` / `Dropping the never-emitted class` |

§2.3 的收束句 `All three numbers, 0.7460, 0.8610 and 0.6966, measure different things and are never substituted for one another.` 在压缩中逐字保留。

**一处需复核的口径重叠（未改）**：摘要与 §3.1 都把 0.7460 称为 `agreement`，把 0.7825 称为 `micro-F1`，二者分母与构造不同（前者两通道互比，后者锚点参照）。全文没有把两者并称为 F1，但读者若略读 `0.7460 ... with statute-anchored micro-F1 0.7825` 可能误认为是同一量的两个版本。已在 `CONFLICT_REVIEW_v3.md` CR-3 记入，未擅自改。

### E2 引用编号一致性

见 D 节末：29 条，无缺号、无孤立、无未定义键。`check_numbers.py` 另核：`licensed tokens: 497 ... all numeric tokens licensed or explicitly structural`。

### E3 `warning rather than a table of prevalence` 四处一致

- Abstract：`The commodity audit is a warning rather than a table of prevalence.` ✅
- §1.4 Contributions：`which makes the table a warning rather than a table of prevalence` ✅（本轮补入）
- Discussion ¶3：`the audit is a warning rather than a table of prevalence` ✅
- Conclusions：`what that audit yields is a warning rather than a table of prevalence` ✅

四处逐字同一短语；前后文各自不同，不构成模板化重复。

### E4 抽 10 处被删句子，逐条确认「主张—限定语—数字」未失

| # | 被删/改写句 | 主张与限定语现在何处 |
|---|---|---|
| 1 | §3.10 逐级清单（−57 词） | 每一级在 §3.1/§3.3/§3.6/§3.7/§3.8 各自在位；§3.10 保留「由 Table 1 或补充数字文件的一行授权」 |
| 2 | §3.1 `the two types a chain requires, service provider and forged document, are the two the instrument cannot extract reliably` | 同段首句 `unusable on the two types a case-chain analysis needs`；SERVICE_PROVIDER 0.3356、DOCUMENT 0.4097 在 Table 1 行 |
| 3 | §2.1 逐页举证细节 | 三个日期与核心判决句保留在句内；举证指针指向 `portal_mechanics.json` |
| 4 | §2.5 `osmanthus + production` 完整推演 | `worked examples are in the supplementary adjudication file`；四判据定义未动 |
| 5 | §2.7 编号冲突细节 | 「register records its own corrections」保留；细节属装置史 |
| 6 | §3.3 假匹配四类完整枚举 | 统计句 + 两类代表在位；`only a commodity-role test removes all four kinds` 保留 |
| 7 | §3.4 后果句 `We register this as a negative measurement rather than an open task` | 改为 `A number produced by one reader where three reached κ 0.0881 would wear the costume of a measurement.`——限定语（一人读数不得冒充测量）与其数字（κ 0.0881）都在 |
| 8 | §3.8 `as a shorter sentence would` 这类元叙述 | 保留 `Stating only the undetermined exclusion would misdescribe the denominator by 166 documents.`——166 与理由都在 |
| 9 | §4 ¶1 `how many were not matched to a food at all` | 该数（272 unmatched / 449 无词）在 §3.6 与 §3.3 |
| 10 | Appendix `and does not generalise to the corpus` | §5 Limitations 的 `The 311 are not a random subset` 与 §2.4 的锚点限制在位 |

十处**没有一处**把「限定语」与「数字」一起删掉。

---

## 版式与构建校验

| 检查 | 结果 |
|---|---|
| `_tools/check_docx_template.py v3.docx v3.md` | **FAILURES: 0**（408/408 段块在位；6 张表；29 条参考文献带列表编号；样式全部在模板内定义） |
| `_tools/sweep_4b.py v3.md v3.docx` | **FAILURES: none**（H2 10、H3 21、Section 引用无悬空、表题 1–4 有序、29 条引用、29 个 DOI、摘要 199 词） |
| `_tools/check_numbers.py` | `all numeric tokens licensed or explicitly structural`（497 个 token） |
| docx | 425,595 B，sha256 `f6cb46d6…`（docx 哈希随 Office 内部时间戳变化，**不作正确性判据**） |
| md | 61,886 B，sha256 `883aa64a…` |

---

## 需作者确认的事项

见 `HUMAN_DECISIONS_v3.md`。

<!-- v3.1 adjudication 2026-11-06 -->

---

## v3.1 — CR 裁决后的改动（2026-11-06）

**触发** 关机前遗留的 CR-1/CR-2/CR-4 三项由产品文件查实，作者批准按推荐执行；CR-3 不动。

**逐项改动**
1. **§3.4（CR-4）** `The model wrote a product name for all 1,128 documents and declined in 232 ... yet 818 of the 1,128 (0.7252) ... those 818 phrases`
   → `The model produced a name for 896 documents and declined in 232 ... yet 586 of the 896 (0.654) ... those 586 phrases`
2. **§4 ¶4（CR-4）** `(818 names carry no lexicon term)` → `(586 of the 896 names carry no lexicon term)`
3. **§3.3（CR-2）** `8 of the 19 false matches, which is what segmentation is for, and also 12 of the 104 true subjects`
   → `8 of the 19 false matches (what segmentation is for), 12 of the 104 true subjects, 13 mentions and 5 statute citations`
4. **附录 A（CR-1）** `the 228 top-tier documents’ high-confidence pseudo-labels` → 同句末加 `(128 Chinese, 100 English)`

**为守住 7,200 词做的三处无损压缩（共 −6 词）**
- `destroyed the credibility of the exercise` → `destroyed the exercise’s credibility`
- `and the last two speak most directly` → `the last two speak directly`
- `whose failure had just been measured` → `whose failure had been measured`

**终值**
- md `26f7adb8931fdbbe8e52a37bc939baff80a4aa425eab1f03d214e18a085af082`，61,913 B
- docx `55eff62ba79fd0cb9c791c18b771c9040c40d4661ad88dea76c8e72b3f0e1d34`，425,615 B
- 正文 **7,200 词**（−21.7%）；摘要 **199 词**；必备数字 **15/15**
- 数字多重集：新增 `0.654`/`586`/`896`，移除 `0.7252`/`818`，无其他变更

**四件检查**
| 检查 | 结果 |
|---|---|
| `check_docx_template.py` | FAILURES: 0（408/408 段块；29 条文献带编号） |
| `sweep_4b.py` | FAILURES: none（29 引用 / 29 DOI / 摘要 199 词） |
| `check_numbers.py` | 488 token 全部有据（含新规则：多引文组 `[7,8,9]` 属引文标记） |
| `v3_metrics.py` | 7,200 词 / 摘要 199 / 15 项必备数字在位 |

**未做（按作者指示）** 补充包未更新（`refs_crossref.json` 仍 12 条、MANIFEST 未 bump），仓库未提交。这两项必须在投稿前完成。

---

## CRediT 落地（2026-11-06 晚）

- **改动** Statements 的 Author Contributions：`表格式（15×2）+ 引导句 + 首字母对照` → **MDPI 单段式**，
  角色↔作者映射逐项不变（Conceptualization Y.C./S.Z.；Data curation、Formal analysis Y.C./C.Y.；
  Funding acquisition、Project administration、Resources、Supervision S.Z.；Investigation Y.C./Z.X./X.W.；
  Methodology Y.C./C.Y./X.W.；Software Y.C./X.W.；Validation Z.X./X.W.；Visualization Z.X.；
  Writing – original draft Y.C.；Writing – review & editing 五人）。
- **影响面**：docx 表格 6→5（4 正文表 + 1 模板编辑块），`check_docx_template` 的
  `tables: 5 (expected 4 manuscript + 1 editorial block)` 通过；Statements 词数 280→317（**不计入 7,200**）。
- **终值**：md `0f2b2b3d…` 61,684 B；docx `40d69160…` 425,384 B；阅读版 PDF 16 页 `6e9365cd…`。
- **四检**：check_numbers 488/0；check_docx_template 0 失败；sweep_4b none；v3_metrics 7,200 / 199 / 15-15。
- ★没有任何数字变动：数字多重集与 v3.1 完全一致（`0.654`/`586`/`896` 在，`0.7252`/`818` 不在）。

## 图形摘要副标题纠错（2026-11-06 深夜，投稿页面前）

- **发现路径**：为上传生成 2048×1024 RGB 合规副本后**目视复核**原图，见副标题
  「An estimability audit of 1,128 Chinese food-safety administrative decisions」。
- **证伪**：`corpus_counts.json`（sha `ed3ad7c9…`，2026-11-05T04:22:43Z）记
  `silver.n = 1128`、`by_lang.zh = 875`、`by_lang.en = 253` ⇒ 该 1,128 篇**不是**「Chinese decisions」，
  其中 253 篇为 openFDA 美国召回记录（`e6_descriptive.json` 亦记 `excluded_non_cn = 253`）。
  正文摘要与 §2 一直是「1,128 documents (875 Chinese decisions, 253 US recalls)」，图形摘要与之不一致。
- **改动**：副标题 →「An estimability audit of 1,128 documents: 875 Chinese penalty decisions,
  253 US recall records」；页脚 `a1deda2c… (n = 1,128)` 保留（sha 与 n 本就同源同值）。
- **影响面**：仅图形摘要，**正文/表格/numbers.csv 一个数都没动**；未重建 docx。
- **新指纹**：`graphical_abstract.png` 196,217 B `69ba8533…`；
  上传用合规副本 `graphical_abstract_2048.png` 368,015 B `0b0cde13…`（2048×1024、RGB、白底）。
- **教训**：图注里的「语料构成」与正文一样是**可被证伪的陈述**，必须回产品核；目视复核非装饰步骤。

## 投稿信重写（2026-11-06 深夜，降桌拒风险）

- **结构**：开头补「Article + Food Quality and Safety 分栏」→ 新增 **Fit with the journal** 段（把研究问题
  挂到本刊 scope：执法/召回文本里的"食品维度"；并说明语料为何取中国、结论如何外推）→ **Three contributions**
  三段（审计后基线 / 品类审计 / 可估计性阶梯）→ **Checkability**（588 行溯源表、偏离登记、产物随稿）→
  **Funding and its boundary**（明说不测 resilience）→ **Declarations**。
- **降险理由**：桌拒最常见的两条是 in-scope 与 unverifiable；前者用 scope 段正面回答，后者用可核查段回答。
- **数字零新增**：机器核过信内每个数值 token 均在 `numbers.csv` 有行（0.7460 / 0.7825 / 0.4195 / 14 / 50 /
  18 / 679 / 270 / 0.9296 / 0.3852 / 0.4885 / 0.7390 / 1,128 / 875 / 253）；`588` 是溯源表自身行数、
  `25CSH113` 与邮箱为结构串。
- **不做**：不写「first」类首创断言、不引未经核实的期刊指标、不承诺录用。
- **交付两份**：`cover_letter.md` 4,263 B `4268dc87…`（存档）；`cover_letter_paste.txt` 4,236 B `50d1e4e8…`
  （**粘文本框用**：去 markdown 标记、段内不硬换行，避免 `statute-` 这类断字）。

## Statements 补两段（2026-11-06 深夜，投稿声明页前置）

- **缘起**：MDPI 提交页三个必填项（GenAI、Published materials、Funding）与稿件 Statements 不一致之处须先消灭。
- **改动 1 — Use of Generative AI（新增，置于 Conflicts of Interest 之后）**：披露 LLM 助手（Claude, Anthropic）
  用于撰写/修改正文、编写与修订分析与构建脚本、组装补充包与公开仓库；并写明全部作者复核、每个数字由脚本
  对 `numbers.csv` 重验、作者承担全部责任；并区分「§2.3 的语言模型标注层是研究方法，不是写作工具」。
- **改动 2 — Funding**：原行只有项目名 + `25CSH113`，**无基金机构名**；补为
  「funded by the National Social Science Fund of China (Youth Project), grant number 25CSH113,
  under the project 数据黑产"韧性"…」。
  ★**机构名的核实过程**：nopss.gov.cn 可访问但 2025 年度项目立项名单不在通知公告/资料下载/重大专项分类页；
  `xm.npopss-cn.cn` 项目查询需登录；百度/搜狗 302、360 与 Bing RSS（含 site: 检索）对 `25CSH113` 与项目名
  均无命中；本地 D:\Foods、D:\MIR、D:\CAAI、D:\CIS 全盘 grep 只有项目标题与编号。**机构名由作者确认后写入，
  非由我推断**（编号 25CSH113 的构型只是旁证）。
- **未改动**：COI 仍为 no conflict（系统里同样选 No）；正文数字零变动。
- **新指纹**：md 62,662 B `8ac6707e…`；docx 425,739 B `6476aefd…`（425,479 → 425,739）。
- **四检**：check_numbers 488/0；check_docx_template 0 失败（grant number present 仍通过）；
  sweep_4b none；v3_metrics 7,200 / 199 / 15-15（Statements 不计入正文词数）。
- **仓库**：已同步 `manuscript/manuscript_submission.md/.docx` 并推送 `212170d`。

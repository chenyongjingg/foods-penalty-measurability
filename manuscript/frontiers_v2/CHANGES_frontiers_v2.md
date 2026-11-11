# manuscript_frontiers_v1 → v2　变更清单

生成日期：2026-11-11　　基线：`manuscript_frontiers_v1.docx`（376,221 B `6f12f0acf27691ff`）

---

## 0　交付物

| 文件 | 大小 | sha256 前 16 位 | 说明 |
|---|---:|---|---|
| `manuscript_frontiers_v2.src.md` | 53,414 B | `2526a885c4cbfd8e` | 工作源件（`{key}` 引用标记未解析） |
| `manuscript_frontiers_v2.md` | 59,015 B | `51016aace39693d5` | 投递用 markdown（引用已按首现解析为 [1]–[29]） |
| `manuscript_frontiers_v2.docx` | 841,923 B | `488110968c01dcb9` | **投稿件**：Frontiers 官方 Word 模板（Letter、单倍行距、表 1–4 置于文末） |
| `manuscript_frontiers_v2.pdf` | 630,821 B | `c8cb69f975ef8722` | 由投稿件导出，仅供校对；不作为投稿附件 |
| `figure1_estimability.png` | 361,819 B | `cc57ff6aa6a9123d` | 图 1 独立高分辨率文件（2280×1950 px；模板版内按 6.60 in 宽嵌入 = 345 dpi） |
| `COVER_LETTER.md` | 874 B | `26d46f44fd05b440` | 投稿信，129 词（正文 119 词，限 150） |

（表中 sha256 前 16 位以本文件生成时刻为准，逐字全值见 `sha256sum` 记录或仓库 `manuscript/frontiers_v2/SHA256SUMS`。）

闸门脚本：`check_v2.py`（C1–C11，内容层）、`check_docx_v2.py`（D1–D10，排版层）。两者当前均全绿，原始输出见 §6。

**A4 备用件**：`build_docx_v2.py` 仍保留，可生成 `manuscript_frontiers_v2_plain.docx`（A4、1.5 倍行距）。本次未生成；投稿件一律指上表的模板版 `manuscript_frontiers_v2.docx`。

---

## 1　阶段一：作者与单位

### 1.1 作者行（`src.md` 第 10 行）

```
v1 ：Yongjin Chen^1^, Chenrui Yang^1^, Ziying Xue^1^, Xiyuan Wang^1^ and Songze Zhu^1^,*
中间：Ziying Xue^1^, Chenrui Yang^2^, Yongjin Chen^3^, Xiyuan Wang^2^ and Songze Zhu^3^,*
定稿：Ziying Xue^1^, Yongjin Chen^2^ and Songze Zhu^2^,*
```

先做第一 ↔ 第三作者对调，随后按指示删除第二（Chenrui Yang）与第四（Xiyuan Wang）作者。通讯作者始终为 Songze Zhu（`20196846@ppsuc.edu.cn`），星号未变。删除后仅剩两位作者所属的单位，上标重新连续编号为 ^1^ ^2^，不保留空号。

### 1.2 单位（在 2026-11-11 的第二轮指示后写入）

| 作者 | 学院（中文） | 英文著录 |
|---|---|---|
| Z.X.（第一作者） | 侦查学院 | ^1^ School of Criminal Investigation |
| Y.C.（第二作者） | 公安管理学院 | ^2^ School of Police Administration |
| S.Z.（通讯作者） | 公安管理学院 | ^2^ School of Police Administration |

原第二、第四作者所在的**信息网络安全学院**随作者删除一同移出，不保留空单位。三个学院的英文名是对中文名的直译，若贵校有官方英文名请替换，其余字串未动。

### 1.3 邮箱随人走 + 删除

| 作者 | 邮箱 |
|---|---|
| Z.X. | 原属 Y.C. 的 `202420610006@stu.ppsuc.edu.cn` → **`15620821066@163.com`** |
| Y.C. | 原属 Z.X. 的 `15620821066@163.com` → **`202420610006@stu.ppsuc.edu.cn`** |
| C.Y. / X.W. | **随作者删除**（`2024111033@stu.ppsuc.edu.cn`、`202321440020@stu.ppsuc.edu.cn`） |

C8 现在同时断言"作者行逐字正确"＋"三人上标与学院一一对应"＋"两个保留邮箱在位"＋"`(C.Y.)`/`(X.W.)`/Chenrui/Xiyuan 一处不剩"。

> **C1 的一处例外（已显式打印，不是静默放行）**：删掉两位作者后，其邮箱号段 `2024111033`、`202321440020` 从正文消失，C1 报 "2 lost"。闸门已改为**有依据的豁免**：只有当某数值 token 在 v1 中恰好出现一次、且那一处正好是 `@stu.ppsuc.edu.cn` 的本地部分时，才允许它消失，并逐条打印豁免名单；其他任何数值丢失仍然 fail。

### 1.4 CRediT 角色（删除后）

| 角色 | 归属 |
|---|---|
| Conceptualization | Z.X. + S.Z. |
| Methodology | **Z.X. + S.Z.**（2026-11-11 由你授权分配） |
| Data curation / Formal analysis / Software / Writing – original draft | Z.X. |
| Validation / Visualization / Investigation | Y.C. |
| Funding acquisition / Supervision / Resources / Administration | S.Z. |

定稿原文：`"Z.X. and S.Z. conceived the study (conceptualization) and designed its method (methodology), and S.Z. acquired its funding, administered and supervised the project and provided the resources. Z.X. curated the data, performed the formal analysis, wrote the software and prepared the original draft; Y.C. carried out validation and visualization and joined the investigation. All three authors took part in reviewing and editing the manuscript and have read and agreed to its published version."`

**Methodology 的归属理由**（2026-11-11 你授权由我分配）：该角色在 v1 属 C.Y. 与 X.W.，两人删除后不能凭空消失，也不宜全压给 Z.X.（他已有 4 个角色，贡献声明会读成"一个人做了全部"）。Methodology 是**设计**角色，与 S.Z. 已有的 conceptualization / supervision 同属研究设计层，故与 Z.X. 共同署名。Y.C. 未加挂 Methodology，避免与其 validation / visualization / investigation 的实际分工不符。

### 1.5 位置性指代清查

全文检索 `first author`、`the first author`、`corresponding author`、`by Y.C.`、`by the third author` 等位置性表述：**0 处**。作者仅以缩写在 CRediT 段出现，无位置序数引用。

### 1.6 Funding

未改动：National Social Science Fund of China (Youth Project)，grant number **25CSH113**（以稿件为准，未采用其他来源的编号）。

---

## 2　阶段二：压缩

### 2.1 实测结果（同一分词器 v1↔v2，脚本 `measure_sections.py`）

| 章节 | v1 词 | v2 词 | 增减 | % |
|---|---:|---:|---:|---:|
| Abstract | 263 | **237** | −26 | −9.9%（250 词上限之下的真实长度） |
| Introduction | 863 | 761 | −102 | −11.8% |
| Materials and Methods | 1,646 | 1,537 | −109 | −6.6% |
| Results | 2,671 | 2,234 | −437 | −16.4%（见表注） |
| Discussion | 1,016 | 845 | **−171** | **−16.8%** |
| Limitations | 206 | 184 | −22 | −10.7% |
| Conclusions | 168 | 140 | −28 | −16.7% |
| Appendix A | 273 | 273 | 0 | 0%（见 §2.4） |
| Statements（七个声明合计） | 471 | 411 | −60 | −12.7% |
| Tables（四个题注，移到文末后单列） | 0 | 164 | +164 | 位置变化，非新增 |
| **正文合计（不含参考文献）** | **7,577** | **6,786** | **−791** | **−10.4%** |

**Results 那一行的读法**：四个表题注（164 词）按模板要求移到文末，单独成 `Tables` 一节。原地散文 2,234 + 移走的题注 164 = **2,398**，与上一版记录的 2,398 逐数吻合，即 Results 的真实删减仍为 **−273（−10.2%）**。合计行两侧都含题注，因此可比。

闸门 C5 用整文件分词（含 YAML、表行、声明块）：7,984 → 7,220 词，−9.6%。
Word 自身计数（含 29 条参考文献与表格单元）：**9,453 → 8,740 词（−7.5%）**。

**页数不作减法**：v1 原件 30 页（Word 默认 Letter + 1.5 倍行距），v2 模板版 19 页（Letter + 单倍行距 + 0.89/0.82 in 边距）。两版版式不同，页数差里混着版式变化，故只用与版式无关的**词数**判断长度。

### 2.2 未达 15% 的原因（可复算，不是估计）

按"这句话里有没有数字"把正文切开再统计：

| | v1 | v2 | 变化 |
|---|---:|---:|---:|
| 含数值句子的词数 | 3,830 | 3,768 | **−62**（−1.6%） |
| 不含任何数值的句子 | 3,753 | 3,037 | **−716（−19.1%）** |

（口径：正文去掉标题行与表格行后按 `.!?` 切句；句子总数 328 → 293。分词器与 §2.1 略有出入，故合计为 7,583 → 6,805 而非 7,577 → 6,786，差额来自小数点被当句号切开，两套读数各自内部自洽。）

也就是说：**凡是可以自由改写的散文，已经压掉了 19.1%**；剩下动不了的是"每个数值都必须原样落地"约束下的句子。C1 逐 token 证明了 v1 的 260 个数值 token（其中 2 个是已删作者的邮箱号段，见 §1.3）在 v2 中一个不少——这些 token 所在的句子只删了 62 词。**要在不丢数值的前提下再压约 350 词（补到 15%），只能开始删除测量内容本身**，与用户的绝对约束冲突，故停在 −10.4%，此处如实报告而非凑数。

### 2.3 逐项实测：哪些真是改动，哪些是空操作

这张表是本节唯一的事实来源，每一项都是"数出来"的，不是回忆：

| 检查项 | v1 | v2 | 结论 |
|---|---:|---:|---|
| `"Two properties matter"` | 1 | **0** | **已删**（Discussion 首段） |
| `"Three things bear on anyone building…"` | 1 | **0** | **已删**（Introduction 段首） |
| `notably / crucially / importantly / it is worth noting / in fact / indeed` | **0** | **0** | ⚠ v1 本来就是 0，本轮**没有删除动作**；列在此处是为了不让"已清理"被读成"清理过" |
| `may potentially / could arguably` 叠用 | **0** | **0** | ⚠ 同上，无合并动作 |
| `"which is why"` | **6** | **1** | 删去 5 处（其中一处是承接句的重复）；剩 1 处（阈值 ≤3） |
| 含 >40 词的句子 | 29 | **23** | 拆分 6 处；最长句 96 → 93 词，而这 93 词的一句是四种判据的定义列举（subject/mention/statute/false），拆开会让判据更难对照，故保留 |
| `were sorted by the sha256`（被动） | 1 | **0** | 改主动：`"we sorted documents by the sha256 of their identifier and took the first fifteen"` |
| `and are excluded, with the exclusion recorded…`（被动） | 1 | **0** | 改主动：`"we exclude them and record the exclusion in the evaluation product"` |
| `is computed`（被动） | 2 | 2 | **保留**：两句主语都是统计量本身（"the marginal distribution it is computed over"），改 `we` 会误置施动者 |
| 0.7460 / 0.7825 / 0.9296 / 0.3852 在正文的出现次数 | 4 / 4 / 6 / 8 | 4 / 4 / 6 / 8 | ⚠ **没有做跨节去重**：这些数在 Results 与 Discussion 各出现一次是论文的复述需要，删掉会切断讨论 |

**778 词到底从哪里减掉的**：见 §2.2 的切分——716 词（92%）来自"不含任何数值的句子"（整段改写、合并、删口号），62 词来自含数值句子的语法性虚词。没有一次删除落在数值、表格、声明或附录上。

**保留的克制语气**（按要求不得丢失，实测三句均在）：`"We did not expect the gap to be this wide"`、`"would wear the costume of a measurement"`、`"the run is an abort"`。

### 2.4 Appendix A 未压缩的理由

Appendix A 的 273 词几乎全部是"哪一个 run 为什么作废"的判定记录（E9 的三次尝试、49 of 50 不可解析、27 个无法解析为类别、`None` 使比较步抛错）。删任何一句都会删掉一个判定，故整节不动。

---

## 3　阶段三：Frontiers 对齐

| 项 | 处置 | 位置 |
|---|---|---|
| 标题页 | 标题 + 作者带上标 + 单位 + 通讯邮箱，四件齐全；删掉了可见的 `**Article type:** Original Research` 行（信息改由 YAML 与投稿系统承载） | `src.md` 第 3–15 行 |
| 摘要 | 无引文；**237 词**（限 250）；四个子标题 Background/Methods/Results/Conclusions | `## Abstract` |
| 结构与标题 | IMRaD + `Materials and Methods`（原 `Materials and methods`）、`Conclusion`（原 `Conclusions`）按 Frontiers 标题大小写 | `## ` 级 |
| 声明顺序 | 七个声明各成**独立二级标题**：Ethics → Data Availability → Conflict of Interest → Funding → Author Contributions → Acknowledgments → Supplementary Material；C11 断言标题出现位置单调递增 | 七个 `## ` 标题 |
| 生成式 AI 声明 | **合并进 Acknowledgments**，压到 3 句，并保留"标注层是方法不是写作工具"这一关键限定 | `**Acknowledgments:**` |
| 表 1 列宽 | `1128` 换行、`0.7460` 断字：定宽列，数值列右对齐，表头行跨页重复（最终列宽见 §3b） | `build_docx_template_v2.py: COLUMN_WIDTHS[0]` |
| 表 2–4 | 同法定宽，数值列右对齐 | 同上 |
| 表 3 置信区间列 | 末行 `(0.8927–0.9545)` / `(0.3291–0.4445)` 为不可分的 15 字符 token，列宽须容下（C9 实测拦截的正是这两处） | 同上 |
| 图 1 | 嵌入 docx，题注完整；同时单独交付 `figure1_estimability.png`（模板要求图件单独提交） | `Caption` 样式 |
| 参考文献 | 29 条 Vancouver；`[n]` 按首现顺序生成，编号与列表不可能分叉；[13] 中文名规范为 `Liu WJ`（生成器内 `AUTHOR_OVERRIDE`，重生成不会回退） | `refs_v4.py`、`resolve_refs_v2.py` |
| 行距/字体/标题 | 改为模板样式（单倍行距、Times New Roman 12 pt、Title 16 pt），见 §3b | D2/D3/D8 |
| 页面 | 改为模板页面（Letter 8.5×11 in），见 §3b | D1 |

### 3b　换上出版社的专属模板（2026-11-11 追加）

**模板来源**：`https://www.frontiersin.org/Design/zip/Frontiers_Word_Templates.zip` → `Frontiers_Template.docx`（695,612 B），经 `127.0.0.1:7897` 代理下载，存于 `D:\Foods\_frontiers_template\`。

**做法**：直接沿用模板的样式与节属性，而不是照样子重画一遍。`clean_reference()` 清空模板的教学正文、只留 `w:sectPr` 与样式表，交给 pandoc 作 `--reference-doc`；随后把 pandoc 自带的 `Body Text / First Paragraph / Compact` 归并到模板的 `Normal`，把 markdown 的 `##/###` 映射到 `Heading 1/2`，标题→`Title`，作者行/关键词/Abstract 标签→`Author List`（模板给该样式设了别名 `Keywords,Abstract`，正是这个用途），图表题注→`Caption`。

| 模板带来的变化 | v2 原 A4 版 | 模板版 |
|---|---|---|
| 页面 | A4 210×297 mm，四边 1 in | **Letter 8.5×11 in**，边距左 0.89 / 右 0.82 / 上 0.79 in（出版方原值，`pgMar` 逐 twip 抄自模板，可用宽 **6.79 in**） |
| 行距 | 1.5 倍 | **单倍**（模板 `Normal` 为 `line=240 auto`，段前 6 pt / 段后 12 pt） |
| 标题 | Heading 1/2/3 12/12/12 pt 手设 | 模板样式：`Title` 16 pt 加粗居中，`Heading 1` 加粗，**自动编号**（1、2、2.1 …） |
| 首屏 | 无 | 模板首页页眉带 Frontiers 徽标（`header3`，`titlePg` 控制） |
| 行号 | 无 | Word 左侧连续行号（模板 `lnNumType`，评审所需） |
| 表格 | 就地放在各节中 | **移到文末** `## Tables` 一节（模板原文："Tables should be inserted at the end of the manuscript."） |
| 表格宽度 | 6.27 in（A4 正文宽） | **6.79 in 满宽**，多出的 0.52 in 给最宽的文字列，数值列宽度不变：表 1 `[1.30, 0.72, 1.05, 1.42, 2.30]`、表 2 `[1.55, 0.80, 0.90, 3.54]`、表 3 `[1.42, 1.10, 0.72, 0.72, 1.16, 1.67]`、表 4 `[0.85, 2.37, 0.72, 0.95, 0.95, 0.95]` |
| 表格分页 | — | 表头行跨页重复、行不跨页（`cantSplit`）、题注不断行（`keep_together`） |
| 图 1 | 5.83 in 宽 / 391 dpi | **6.60 in 宽 / 345 dpi**（仍在 6.79 in 之内，留 0.19 in 余量） |
| 模板残留 | — | 删除模板的**偶数页页脚**（内容为 "This is a provisional file, not the final typeset article"）：先从 `sectPr` 移除 `footerReference type=even`，再把 `word/footer1.xml` 里的该句一并抹掉，两道都做，防止日后误复活 |

**为什么表格要移到文末**：模板第 23 段原文即此句。正文里"Table 1 collects every statistic…" 等引用句全部保留在原位，`[1]`–`[29]` 引用编号不受影响；四个表体逐字节未动（C2 仍报 1,634 / 678 / 1,285 / 419 字符全等）。

**为什么图 1 仍嵌在正文**：模板第 19 段说"figures to be submitted individually … will then be automatically embedded"，指的是**投稿件单独交图**。我们两件事都做：正文内嵌一份便于审读，同时单独交付 `figure1_estimability.png`。

**两处与先前要求不一致，须由作者裁定**（不擅自改模板）：
1. **行距**：你此前要求 1.5 倍行距，模板 `Normal` 是单倍。此处以模板为准（出版方要求优先）。若要回到 1.5 倍，把 `build_docx_template_v2.py` 里 `Normal` 的 `line` 改成 `360` 即可，一处改动。
2. **标题自动编号**：模板 `Heading 1/2` 自带编号，渲染为 "1 Introduction"、"2.1 Sources and sampling frame"。这是模板的默认行为，未改；若期刊最终排版去编号，按模板走即可。

---

## 4　阶段四：终检

### 4.1 关键数值三处对照（摘要 / 表 1 / 正文）

| 数值 | 摘要 | 表内（表 1–4） | 其余正文 | 合计 |
|---|---:|---:|---:|---:|
| 0.7460 | 1 | 1（表 1） | 2 | 4 |
| 0.7825 | 1 | 1（表 1） | 2 | 4 |
| 0.4195 | 1 | 1（表 1） | 2 | 4 |
| 0.9296 | 1 | 2（表 1、表 3） | 3 | 6 |
| 0.3852 | 1 | 2（表 1、表 3） | 5 | 8 |
| 0.0881 | 1 | 1（表 1） | 3 | 5 |
| 0.4885 | 1 | 1（表 4） | 1 | 3 |
| 0.7390 | 1 | 1（表 4） | 1 | 3 |
| 14 of 50 | 1 | 0 | 2 | 3 |
| 604 | 1 | 1（表 2） | 1 | 3 |
| 679 | 1 | 1（表 3） | 2 | 4 |

口径：`src.md` 中按"摘要 / 表体 / 其余正文"三块分别计数，合计即全文出现次数。**摘要与表体各至少一次，且摘要值都能在表或正文里找到同值**，这是这张表要证明的事；出现次数多寡不是一致性判据（同一统计量在 Results 与 Discussion 各引一次是论文的复述需要，见 §2.3）。

正文散文中 `1128` 统一写为 `1,128`（表 1 单元内保持裸写 `1128`，因表体须逐字节不变）。

### 4.2 作者一致性

标题页 3 人 ↔ CRediT 段 3 人（Z.X./Y.C./S.Z.）↔ 邮箱 2 组 ↔ `All three authors`：全部匹配。`C.Y.`、`X.W.`、`Chenrui`、`Xiyuan` 全文 **0 处**（C8 断言，防止删除后残留）。Funding 段不点名作者，无冲突。

### 4.3 缩写首次出现

| 缩写 | 首次出现时是否展开 | 位置 |
|---|---|---|
| F1 | ✅ `F1 is the harmonic mean of precision and recall` | Results 首段 |
| CI | ✅ `95% confidence interval [CI]` | Results §"What a commodity term denotes" |
| OR | ✅ `odds ratio (OR) 9.57` | Discussion §"A behaviour–hazard sketch" |
| TPR / TNR | ✅ 写入表 4 题注 `TPR, true positive rate; TNR, true negative rate` | 表 4 题注 |
| κ | ✅ `Fleiss' κ (chance-corrected agreement)` | Results §"Human readers…" |

### 4.4 残留 AI 腔句清单（**只列不改，留人工裁决**）

按用户要求，以下不擅自重写：

1. **"rather than" 对比句式全文 26 处**（正文）。多数承载真实对立（detected vs occurred、construct vs rate、estimate vs assignment），但下列 8 处两半信息量不匹配，属可选删减：
   - `"We answer it by auditing rather than assuming."`（Introduction 末段）
   - `"comparing constructs rather than rates and never asking whether…"`（Introduction 第 4 段）
   - `"the result is bookkeeping rather than a finding."`（Results §"Crossing the two axes" 首句）
   - `"The transferable lesson is the auditing step rather than the numbers."`（Discussion 第 6 段）
   - `"we state them as requirements rather than as caveats."`（Discussion 末段）
   - `"the link here is procedural rather than empirical"`（Discussion 第 9 段）
   - `"are missing rather than short"`（Limitations）
   - `"the result is a warning rather than a table of prevalence"`（Results §"What a commodity term denotes"）
2. **规则三段式框架**（不是数据驱动的计数，是修辞排比）：`"Three obligations follow"`（Introduction 第 3 段）、`"Three things come out:"`（Introduction 末段）。另有三处是真实计数，可保留：`Three readers`、`Three attempts`、`Three questions the record cannot answer`。
3. **判断句收尾**（每段末一句短判断）：`"The three figures measure different things."`（Results 首段末）、`"Each system produces the document its law requires, and each document licenses a different question."`（Discussion 第 6 段）。前者可删，后者承载了论文的核心论点。
4. **表格内的 `reliability, not accuracy`**（表 1 第 1 行"what it measures"列）——属同一条对比习惯，但该列本就是判据说明，可保留。

**未发现**：破折号（正文 0 处，仅表格空值占位用 `—`）、`"the real question is / at its core / in reality"` 类箴言（0）、`delve / pivotal / robust / landscape / testament` 类词（0）、Hedging 叠用（0）。

---

## 5　需人工确认的事项

1. **参考文献 [13] 的 `Liu WJ` 是拼音转写**：出版方记录（Hans，DOI `10.12677/ds.2022.83056`）只给出 `刘文静`，全库无罗马化形式。已按拼音转写并在 `build_refs_v4.py` 的 `AUTHOR_OVERRIDE` 中单列说明——这是 29 条中唯一一条不是从记录里抄下来的作者串。
2. **三个学院的英文名是直译**（`School of Criminal Investigation`、`School of Police Administration`）：若学校有官方英文译名，请替换，其余字串不动（见 §1.2）。
3. **行距与标题编号**：模板 `Normal` 是单倍行距、`Heading` 自带编号，与你先前"1.5 倍行距"的要求不一致；已按出版方模板执行，改动方式见 §3b 末尾。

（原"单位缺院系"一项已于 2026-11-11 你给出学院信息后解决，见 §1.2。）

## 6　闸门原始输出

### 6.1 内容层 `check_v2.py`

```
C1 number freeze : v1 260 distinct tokens, v2 258
   exempt (removed authors' e-mail local parts): 202321440020 | 2024111033
   PASS - no numeric token from v1 is absent from v2
C2 Table 1       : PASS byte-identical (1634 vs 1634 chars)
C2 Table 2       : PASS byte-identical (678 vs 678 chars)
C2 Table 3       : PASS byte-identical (1285 vs 1285 chars)
C2 Table 4       : PASS byte-identical (419 vs 419 chars)
C3 anchors       : PASS (11/11)
C4 abstract      : 237 words (limit 250), 4/4 sub-headings, 15/15 mandated numbers
C5 length        : v1 7984 -> v2 7220 words (9.6% below), limit 12,000 -> PASS
   15% trim target: NOT MET (9.6%)
C6 cross-refs    : PASS none
C7 citations     : 29 distinct, first-appearance ordered PASS, list entries 29 PASS
C8 authorship    : order PASS, departments PASS, emails PASS, CRediT draft to Z.X. PASS
C9 column fit    : PASS
C10 prose        : meta-discourse PASS 0, 'which is why' 1 (<=3), 'instrument output' 0 (<=1)
C11 statements   : PASS Frontiers order

RESULT: ALL CHECKS PASS
```

### 6.2 排版层 `check_docx_v2.py`

```
D1 page          : 8.50 x 11.00 in PASS Letter, margins L0.89 R0.82 T0.79 in PASS template, usable 6.79 in
D2 spacing       : body single PASS; cells 1.0 PASS
D3 styles        : Title 1 PASS 16 pt bold centred, Heading 1 16 PASS, Heading 2 17, fonts ['Times New Roman'] PASS
D4 tables        : widths [6.79, 6.79, 6.79, 6.79] (usable 6.79) PASS
D5 column fit    : PASS
D6 cells         : 9 pt PASS; numeric right-aligned PASS
D7 figure        : 1 image(s) in body, 2280x1950 px at 6.60 in wide -> 345 dpi, Caption style PASS PASS
D8 rules         : 0 paragraph borders PASS
D9 text          : markdown body 257 numeric tokens, docx 355, missing 0 PASS
D10 package      : 'provisional file' in 0 part(s) PASS, even footer ref PASS absent

RESULT: ALL CHECKS PASS
```

D9 中 docx 侧 token 数多于 markdown 正文（355 vs 257）是预期的：docx 侧同时统计了表格单元、图题与参考文献条目，而 markdown 侧只比对正文；检查的方向是"markdown 正文里的数值在 docx 里一个不缺"，缺失数为 0。

D7 只数 **`document.xml` 里被引用的图**：模板首页页眉的徽标 `image1.jpeg` 也在包里，但它不在正文流中，把它算进来会让"正文只有一张图"这句话变成假的。

D10 是针对模板残留的检查：模板偶数页页脚写着 "This is a provisional file, not the final typeset article"，若原样保留会在每个偶数页印出一句假话；现已从 `sectPr` 移除该页脚引用并抹掉文字，闸门同时断言"全文任何部件里没有这句话"与"`sectPr` 里没有 even 页脚引用"。

### 6.3 送 Word 实测（`ComputeStatistics`）

```
manuscript_frontiers_v1.docx  pages 30  words 9453  chars 51793
manuscript_frontiers_v2.docx  pages 19  words 8740  chars 48087
```

两版版式不同（v1 为 Word 默认 Letter + 1.5 倍行距，v2 为模板 Letter + 单倍行距），**页数差不可当压缩量**；版式无关的读数只有词数：−7.5%。

---

## 7　投稿前最后精修（2026-11-11 第三轮：去 AI 腔 · 公卫口径 · 文献重合 · 格式终检）

本节记录本轮改动。§1–§6 是同一份稿子上一轮（模板改造）的记录，其闸门输出反映的是那一轮的构建；本轮输出见 §7.7。

### 7.1 四条指令与实测不符之处（三条按原文执行会伤到结果）

| 请求条目 | 实测 | 实际处置 |
|---|---|---|
| 删 `"instrument output rather than an estimate"` | 正文 **0 次**。最近的实体是 Limitations 的 `records what that layer produced and not a validated estimate`（1 次）；另一处在**图 1 位图内部**的烤死文字，不是正文 | 不删不存在的短语。真正的重复是 `instrument` 一词（现 10 次）；逐处判定均为同一构念的一致指称，保留 |
| 删 `"reliability is not accuracy"` | 正文 **1 次**（Introduction 第 3 段，全文唯一的定义处）；另 1 次在表 1 冻结单元格 | 保留。删掉它，`reliability` 与 `accuracy` 的分野在正文里就没有落点 |
| 删第 3 次及以后的 `"pre-registered"` | 正文 8 处 | 保留 3 处（摘要 L28 的做法声明、Appendix A L218 的判据句、表 4 题注 L308，后者受 C2 冻结），其余 5 处改为 `registered in advance` / `fixed in advance` / `the registered comparison` / `the quantity the criterion fixed`——**事实全部保留，只去掉标签** |
| 删第 3 个 `"14 of 50"` | 3 次：摘要、Methods、Results。**Results 那一处是负对照的结果陈述本身** | 删 Methods 那一处，改写为「0.28 在两个粒度上同值；条件于规则已判定的部分为 14 of 32（0.4375），18 件弃判全是分歧」。14 / 32 / 0.4375 / 18 / 50 全部在位，C1 不受影响 |

另两条前提也不成立：**图 1 不是截图**（仓库里已有矢量 PDF，见 §7.5）；**表 1 的 `jso n` 是 Word 断行**，源文本一直是完整的 `data/analysis/e12_commodity_precision.json`。

### 7.2 阶段一：Discussion / Limitations 去 AI 腔

四处格言式开场均已换成从数字起句。四句受保护的"人味"原句一字未动。

| 位置 | 原开场 | 新开场 | 新增可见的数字（均取自稿内已有值） |
|---|---|---|---|
| Discussion 第 2 段 | `An audited instrument is usable at whatever reliability it has…` | `Two-channel agreement is 0.7460 over the 1,128 documents…` | 0.7460 / 1,128 / 423 / 0.7825 / 0.2693 / 0.4195 |
| Discussion 第 3 段 | `The commodity dimension is measurable and mostly not what it looks like.` | `A lexicon any research group could write in an afternoon matches 679 of the 1,128 documents.`（保护句逐字保留，改为段首） | 679 / 1,128 / 0.9296 / 0.3852 / 0.0667 |
| Discussion 第 4 段 | `The commodity role is not recoverable by asking a general model nicely.` | `All three constructs failed the same gate; the best missed κ = 0.60 by 0.1115…` | 0.60 / 0.1115 / 0.75 / 0.0110（原值） |
| Discussion 第 5 段 | `Human agreement is not a formality.` | `The three readers produced Fleiss' κ 0.0881 over the same 80 documents…` | 80 / 0.0881 / 0.8000 |

- **逐字重复**：改写稿最初让这两段以 `Three constructs registered in advance…` / `Three readers coded the same 80 documents…` 起句，与 Methods 的 L92、Results 的 L132 **一字不差**——这是全稿最硬的两处重复。最终改为 `All three constructs…` / `The three readers…`，两句都不再与别处同形。

- **合段**：`An audited instrument…` 与 `Two-channel agreement on its own…` 实测**已在同一段**，无需并段；该段的问题是"两个开场"，改写后只剩一个。
- **`since` 逐处**：8 处全部为真实因果（无一处误用为时间义），仅把 Discussion 第 4 段的两处改写成直接陈述（`Format mattered: sensitivity rose 0.1923…` / `The mapping step mattered too: 586 of the 896 names…`）。
- **`which is why`**：1 处（Discussion 末段），因与果都带内容，保留。
- **长句**：Discussion 与 Limitations 现无 >40 词句（实测最长 40 词）；本轮另拆了 Conclusion 首句与新增句（42 → 两段）。Methods 仍有一句 93 词（`Each hit was read in a ±120-character window…`），是判定协议的四段枚举，**未动，列入 §7.8**。

### 7.3 阶段二：public-health 口径（三句）

1. Introduction 末段首句前加：`Public-health surveillance that draws on these records inherits their limits, so what the text can measure is settled before a number enters a trend table or a policy brief.`
2. Discussion 比较段末加：`Any jurisdiction building a food-category table from enforcement or recall text should run the same audit before the table is used, because a table of mentions and a table of subject matter support different conclusions.`
3. Conclusion 末加：`The protocol behind this audit can be reused as it stands. The gate is fixed before the first call, agreement is reported with its negative control beside it, and commodity precision is reported separately for what a document is about and what it merely mentions.`

`public health` 一词在正文的出现次数：0 → 3（含关键词行）。全稿未使用 `novel contribution` 一类兜售语。

### 7.4 阶段三：文献重合与核源

- **Discussion 比较段压缩**：{barrere2020} / {menard2024} / {macheka2026} 三处逐一描写的复述，压成一句构造对比；完整评述留在 Introduction 第 4 段。三处引用编号（[18] / [12] / [11]）位置未变，`0 of 253` 保留。
- **核源结果**（逐条对摘要，不是对题名）：

| 引文 | 稿件原句 | 核源结论 | 处置 |
|---|---|---|---|
| {joshi2025} | `782 Indian food-violation judgments from 2022–2024` | ACL Anthology `2025.justnlp-main.6` 摘要逐字为 "782 Indian food safety violation cases filed between 2022-2024" | 保留 |
| {robson2021} | `terminologies and populations that differ from study to study` | 摘要只支持"定义/术语因研究者和监管机构而异"，未提 population | 改为 `its terminologies differ between studies and regulators` |
| {barrere2020} | `European food-fraud vulnerability assessment…` | 摘要无"欧洲"这一限定 | 压缩时删去 `European` |
| {everstine2024} | `a four-decade curated database` | 题名 "Summary of Data from 1980 to 2022"；摘要 "covering 1980-present" | 保留 |
| {chen2026} | `a source already used to analyse recall severity` | 摘要以 Class I 召回为高风险的严重度结局（2012–2024） | 保留 |
| {macheka2026}、{menard2024} | 全国图景 / 中观制度跨国比较 | Semantic Scholar 无摘要，只能核到题名 | 保留，**列入"仅题名可核"** |

- **关键词**：`estimability` → `public health surveillance`（仍 6 个）。不另加 `measurement validity`——`construct validity` 已在列，两者在本稿里指同一件事。

### 7.5 阶段四：格式与技术终检

1. **图 1 独立矢量件**：`figure1_estimability.pdf`（34,091 B，`%PDF-1.4`，**0 个位图对象 / 4 个字体对象**，MediaBox 547.2×468 pt）已放入本目录；正文保留 Caption 样式的图题。docx 内的位图仍是 2280×1950 px、印制宽 6.60 in ⇒ 345 dpi。
2. **表 1 路径断行**：成因实测——该串 9 pt Times 下宽 **2.20 in**，单元格左右默认内边距各 0.08 in，列宽 2.30 in 只剩 2.14 in 可用 ⇒ Word 在 `jso` 与 `n` 之间断开。列宽 2.30 → **2.50**（0.20 从相邻说明列让出，总宽仍 6.79）。Word 实测：11 个产品路径单元格现在**全部 1 行**。
3. **表 3 的加粗**：加粗的四格是 0.1333（Condiments）、0.0667（Health food）、0.9333（Soy）、0.0667（FSDU）——正文点名讨论的四类；Tea 的 0.8667 未加粗是对的。原稿没有给加粗的图例，正文明明写着"Three rows are not commodity spectra and are bold"却有**四行**加粗，两处互相矛盾。**作者拍板后已改**：题注加一句 `Bold marks the total row and the four subject-matter precisions the text quotes.`，正文那句删去 `and are bold` 并去掉三个类别序号 `(15) (16) (18)`（它们是 `e12_commodity_precision.json` 的键，不是样本量，紧挨着 `15 sampled` 会被读成计数）。**C2 只比对表体**（`table_block()` 取的是 `|` 行），题注改动不影响表 1–4 的逐字节断言。
4. **缩写**：CI 首现（Results §commodity）展开、OR 首现（Results §cross-genre）展开、TPR/TNR 在表 4 题注定义；κ 的展开与出处写在 Results §"Human readers"（比"无需定义"更强）。四项**已合规，未改**。
5. **行号**：Word 实测 `LineNumbering.Active = -1`、`RestartMode = 0`（continuous），全篇连续；新增 **D11** 断言该属性与"带编号的 Heading 1 恰为 1–6"。
6. **词数**：Word `ComputeStatistics(0)` = **8,847**（上限 12,000）；正文口径（C5）7,328。
7. **节编号**：模板 Heading 1 引用 `numId 17`，而 pandoc 写出的 `numbering.xml` 里 num 17 **存在但样式级引用缺 `ilvl`**，Word 对这种引用不渲染——直接改样式无效。修法是把 `ilvl/numId` 钉在**段落**上：六个实质章节 → `numId 17`，其余十个（Appendix A、七条声明、References、Tables）→ `numId 0`。PDF 实测：`1 Introduction` … `6 Conclusion` 在，`7 Appendix` / `8 Ethics` / `16 Tables` 不在。

### 7.6 数字与长度（改前 → 改后）

| 量 | 改前 | 改后 | 说明 |
|---|---|---|---|
| Word 词数 | 8,740 | **8,847** | +107，来自 §7.3 的三句、§7.2 的两处去重、表 3 题注的加粗图例 |
| Word 页数 | 19 | **19** | 不变 |
| C5 正文词数 | 7,220 | **7,328** | +108；对 v1 的降幅由 9.6% 变为 8.2% |
| 摘要词数 | 237 | **237** | 未动 |
| C1 数值 token | 258 | **258** | 新增的每个数字都取自稿内已有值，token 集合未扩张 |
| 表 1–4 | 1,634 / 678 / 1,285 / 419 字符 | 同左，逐字节相同 | C2 全绿 |

### 7.7 本轮闸门输出

`python check_v2.py`（源稿闸门，逐字）：

```
C1 number freeze : v1 260 distinct tokens, v2 258
   exempt (removed authors' e-mail local parts): 202321440020 | 2024111033
   PASS - no numeric token from v1 is absent from v2
C2 Table 1       : PASS byte-identical (1634 vs 1634 chars)
C2 Table 2       : PASS byte-identical (678 vs 678 chars)
C2 Table 3       : PASS byte-identical (1285 vs 1285 chars)
C2 Table 4       : PASS byte-identical (419 vs 419 chars)
C3 anchors       : PASS (11/11)
C4 abstract      : 237 words (limit 250), 4/4 sub-headings, 15/15 mandated numbers
C5 length        : v1 7984 -> v2 7328 words (8.2% below), limit 12,000 -> PASS
   15% trim target: NOT MET (8.2%)
C6 cross-refs    : PASS none
C7 citations     : 29 distinct, first-appearance ordered PASS, list entries 29 PASS
C8 authorship    : order PASS, departments PASS, emails PASS, CRediT draft to Z.X. PASS
C9 column fit    : PASS
C10 prose        : meta-discourse PASS 0, 'which is why' 1 (<=3), 'instrument output' 0 (<=1)
C11 statements   : PASS Frontiers order

RESULT: ALL CHECKS PASS
```

`python check_docx_v2.py`（成品 docx 闸门，逐字）：

```
D1 page          : 8.50 x 11.00 in PASS Letter, margins L0.89 R0.82 T0.79 in PASS template, usable 6.79 in
D2 spacing       : body single PASS; cells 1.0 PASS
D3 styles        : Title 1 PASS 16 pt bold centred, Heading 1 16 PASS, Heading 2 17, fonts ['Times New Roman'] PASS
D4 tables        : widths [6.79, 6.79, 6.79, 6.79] (usable 6.79) PASS
D5 column fit    : PASS
D6 cells         : 9 pt PASS; numeric right-aligned PASS
D7 figure        : 1 image(s) in body, 2280x1950 px at 6.60 in wide -> 345 dpi, Caption style PASS PASS
D8 rules         : 0 paragraph borders PASS
D9 text          : markdown body 257 numeric tokens, docx 355, missing 0 PASS
D10 package      : 'provisional file' in 0 part(s) PASS, even footer ref PASS absent
D11 numbering    : line numbers continuous, numbered sections 6 of 16 PASS 1-6

RESULT: ALL CHECKS PASS
```

Word 导出：`pages 19  words 8847  chars 48601`。PDF 文本断言：含 `1 Introduction` / `3.1 Agreement` / `6 Conclusion`，不含 `7 Appendix` / `8 Ethics` / `16 Tables`。

### 7.8 作者拍板的三项（2026-11-11，均由作者授权决定）

1. **表 3 的加粗**：**改题注，不动表体**。题注加 `Bold marks the total row and the four subject-matter precisions the text quotes.`；同时删去正文里与之矛盾的 `and are bold` 和三个类别序号 `(15) (16) (18)`。理由是原文一句话同时声称"三行加粗"而实际四行加粗，且三个序号是 JSON 的键、紧挨 `15 sampled` 会被读成样本量。C2 只比对 `|` 行，题注改动不影响表 1–4 的逐字节断言（改后实测 C2 四项仍 PASS）。
2. **Methods 那句 93 词的判定协议**：**保留**。它是一条规则的四段，拆开会读成四条独立规定。若审稿人点名，这是全稿唯一需要动的地方。
3. **`Three …` 15 处 / `rather than` 26 处**：**不削减**。`AI_TELLS_RESIDUAL.md` 逐条给了判据：15 处落在七个真实的三项设计上，26 处中 20 处带着被否掉那一项的内容、6 处是立场压缩；机械削减会让句子失去与通行做法的区分。

### 7.8.1 投稿版块：Frontiers in Public Health — **Public Health Policy**

选定 **Public Health Policy**。依据：本稿的对象是**行政执法文书与召回记录**（制定法映射、处罚条款、执法机构），不是营养学结局；三条结论的出口是监测表与政策简报（§7.3 新增的三句正是这样写的）。未选 `Public Health and Nutrition`：该版块要求膳食或营养结局，而本稿不测任何健康结局；未选 `Digital Public Health`：LLM 在这里只是工具，抽掉它审计结论不变，把它当卖点会误导审稿人。若编辑建议转投 `Public Health and Nutrition`（食物安全在该版块同样在范围内），迁移成本为零——稿件没有按版块定制的格式要求。

### 7.9 本轮新增/改动的文件

| 文件 | 变化 |
|---|---|
| `manuscript_frontiers_v2.src.md` | 工作源稿（本轮全部文字改动的落点） |
| `manuscript_frontiers_v2.docx` | 重建：19 页 / 8,847 词（表 3 题注定稿后） |
| `manuscript_frontiers_v2.pdf` | 重建（Word 导出） |
| `manuscript_frontiers_v2.lines.md` | **新增**，带 `<!-- L n-m -->` 行号标记（150 块映射，8 块无标记：封面 5 行 + 图行 + 表行） |
| `figure1_estimability.pdf` | **新增**，矢量图件，34,091 B `f671dc68…` |
| `line_map_v2.py` | **新增**，行号映射（五点锚定校准，偏移不唯一即中止） |
| `build_docx_template_v2.py` | 表 1 列宽 2.30→2.50；节编号钉到段落级 `numPr` |
| `check_docx_v2.py` | 新增 D11（行号连续 + 1–6 编号） |
| `COVER_LETTER.md` | 重写，正文 206 词（含落款 227 词），写明投 `Public Health Policy` 版块；第二段删去 `1,128`（`875 + 253` 已隐含），第三段末补一句把每条统计量系到产物文件与 sha256 |
| `COVER_LETTER.docx` | **新增**，投稿用 Word 版（Times New Roman 12 pt，Letter 页面，1 in 边距，1 页；由 `build_cover_letter_docx.py` 从 `.md` 生成，措辞不在两处各写一遍；落款三行是一个段落内的换行，不是三个段落，避免出现段落间距） |
| `AI_TELLS_RESIDUAL.md` | **新增**，残余 AI 痕迹实测清单（由 `ai_tells_v2.py` 生成） |

### 7.10 作者邮箱变更（2026-11-11，按作者指示）

| 作者 | 原邮箱 | 新邮箱 | 位置 |
|---|---|---|---|
| 第二作者 Yongjin Chen | `202420610006@stu.ppsuc.edu.cn` | **`3337851329@qq.com`** | `E-mail addresses:` 行 |
| 第三/通讯作者 Songze Zhu | `20196846@ppsuc.edu.cn` | **`18513826980@163.com`** | `\* Correspondence:` 行 |

第一作者 Ziying Xue 的 `15620821066@163.com` 未动。

**两处闸门随之修改**（都只为这件事放宽，且都点名可查）：

1. **C1 的豁免从"正则"改成"具名表"**。旧规则是"9–12 位数字 + 恰好出现一次 + 后接 `@stu.ppsuc.edu.cn`"，通讯作者的 `20196846` 是 8 位、且域名是 `@ppsuc.edu.cn`，旧规则既挡不住也漏不掉，会直接把这次授权变更判成"丢失数值"。新规则是一张具名的四行表（两位被删除作者 + 两位改址作者），每条仍要求"v1 里恰好出现一次且确实是某个邮箱的本地部分"，并逐条打印**谁、为什么**。
2. **C8 的邮箱断言**改为新地址，并把 `202420610006` / `20196846` 加进"不得再出现"的反向断言。

实测：C1 v1 260 → v2 258，四条豁免全部命中并打印；新增 token `18513826980`、`3337851329` 被列为"new tokens (review)"（这是邮箱本身，不是新数据）。C8 emails PASS；表 1–4 仍逐字节相同。Word：19 页 / 8,847 词。PDF 文本实测：`3337851329@qq.com` 与 `18513826980@163.com` 在，`202420610006` 与 `20196846` 不在。

**未改的两处历史文件**：`manuscript_frontiers_v1.src.md`（闸门基线，动它就没有对照了）与 `repo/manuscript/manuscript_submission.md`（上一版 MDPI 投稿件）。仓库 `README.md` 的 Contact 地址已随通讯作者更新。

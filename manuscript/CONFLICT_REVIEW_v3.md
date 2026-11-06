# CONFLICT_REVIEW_v3 — 疑似数值不一致清单（未裁决）

**性质** 本文件按 v3 任务书 §0 第 4 条设置：发现疑似数值不一致时**只登记、不裁决**，由作者裁定。
**范围** 压缩（任务 B）与文献扩充（任务 D）之后对全稿做的数值自洽复查。
**结论** 发现 **4 项**疑似不一致（CR-1 至 CR-4），另有 **1 项**在压缩中被识别但已按「精度重复」处置、不算冲突（CR-0）。
**处置** 五项**均未改动任何数值、未改写相关句子**。凡压缩涉及这些句子的，原样保留。

---

## CR-0（已处置，非冲突）`0.82` 与 `0.8203`

- **位置** §3.9。
- **现象** 同段先给 `0.8203`，后又出现 `a 0.82 agreement supports a typology sketch`。
- **判定依据** 两个字符串指同一统计量、同一处论证，差别只在精度；`0.82` 不是独立测量。
- **处置** 删去末句中的 `0.82`，改为 `the agreement`；`0.8203` 逐字保留。这是全稿唯一被移除的数值 token（`v3_metrics.py`：`values removed: ['0.82']`）。
- **为何不算冲突** 冲突的定义是两个值互相矛盾；此处是一个值的两种写法，且删除后不损失任何信息。
- **仍需作者确认** 若期刊要求摘要/正文不得出现四位小数以外的舍入写法，此处置方向正确；若作者本意是给出一个「约 0.82」的量级判断，则应在 §3.9 补一句明确它是 `0.8203` 的舍入，而不是当作另一个数。

---

## CR-1 「top-tier」文档数：128 与 228

- **位置**
  - §3.7：`The main corpus contains **128** Chinese documents in the top confidence tier`
  - §3.9：`On the **128** top-tier Chinese documents, dual-channel agreement for the behaviour–hazard codebook is 0.8203`
  - Appendix A：`trained on the **228** top-tier documents' high-confidence pseudo-labels`
- **现象** 同一措辞 `top-tier` 指向两个不同规模：128（中文）与 228。
- **可能的解释（未采信，仅列出）**
  1. 228 = 全部顶层文档（含英文召回），128 = 其中中文子集；
  2. 228 是另一个 tier 定义（如 confidence 阈值不同）；
  3. 其中一处数字在 v1/v2 之间改过而另一处未跟改。
- **为何不裁决** 三种解释都要求回读 E9 与 §3.7 的产品文件（`data/analysis/` 下各自的 tier 判定），本轮任务禁止新增实验与重算，也无法从正文自身判定。
- **作者须做** 指定二者关系：若 228 含英文，建议正文改为 `the 128 Chinese documents in the top confidence tier (228 across both genres)`；若为两套阈值，则须在 Appendix 指明阈值。**在裁定前，两处数字均保持原样。**

---

## CR-2 分词删失的 38 项只分解了 20 项

- **位置** §3.3。
- **原文** `On the 270 adjudicated hits it drops 38: 8 of the 19 false matches, which is what segmentation is for, and also 12 of the 104 true subjects.`
- **现象** 删失总数 38，句内只交代了 8（假匹配）+ 12（真主体）= **20**，其余 **18** 未归因。
- **一致性检验（仅作记录，不作结论）**
  - `270 − 38 = 232`，与后文 `92 of 232` 的分母吻合；
  - `104 − 12 = 92`，与 `0.3966 = 92/232` 吻合；
  - 因此 38 与 232、92 三者自洽，缺的是**归因**，不是算术。
- **为何不裁决** 剩余 18 项应落在 mention（121）与 statute（26）两类里，但正文未给出这两类的删失数；补齐需要回读分词敏感性产品文件，属新增分析。
- **作者须做** 二选一：①补一句 `the remaining 18 fall in the mention and statute classes`（若产品文件支持）；②把句子改为 `drops 38, including 8 of the 19 false matches and 12 of the 104 true subjects`，明确这是举例而非穷举。**本轮未改一字。**

---

## CR-3 摘要中 `0.7460 agreement` 与 `micro-F1 0.7825` 相邻

- **位置** Abstract；同一并置见于 §3.1 与 §2.4 的交叉处。
- **原文** `a two-channel language-model layer reaches 0.7460 agreement, a reliability rather than an accuracy statistic, with statute-anchored micro-F1 0.7825 and macro-F1 0.4195 over classes with support ≥ 20`
- **现象** 两个数分属不同构造：0.7460 是**两通道互比**的 agreement（无外部参照），0.7825 是**以锚点集为参照**的 micro-F1。二者并列且都以四位小数呈现，略读时易被当作同一量的两个版本。
- **文本是否已作区分** 是：`a reliability rather than an accuracy statistic` 紧接 0.7460，`statute-anchored` 紧接 0.7825，§2.3 另有 `All three numbers ... measure different things and are never substituted`。
- **为何不裁决** 这是**表述密度**问题而非数值矛盾：去掉任一数会违反任务 A 的 15 项必备清单；改写句式会改变摘要的论断结构。
- **作者须做** 若认为风险实在，可在摘要中把 `with` 改为 `and separately, against the statute anchor,`（约 +5 词，需在别处再删 5 词以守住 200 词上限）。**本轮维持原样。**

---

## CR-4 E16 的 818／1,128 分母与「已拒答 232 篇」的关系

- **位置** §3.4。
- **原文** `The model wrote a product name for all 1,128 documents and declined in 232.` 紧接 `yet 818 of the 1,128 (0.7252) contain no lexicon term at all, so the mapping assigns them category 0`
- **现象** 若 232 篇被拒答（无名称），则实际写出的名称只有 896 个；818 的分母究竟是 1,128（含拒答）还是 896（仅写出者），正文未言明。`818/1,128 = 0.7252` 说明分母取的是 1,128。
- **由此产生的第二个问题** 拒答的 232 篇在映射时是否也被赋为 category 0？若是，则「名称里没有词表项」与「根本没有名称」被合并在同一类，`The bottleneck is binding, not extraction` 这一论断的强度会受影响（拒答属提取失败，不属绑定失败）。
- **为何不裁决** 两种读法都自洽，取哪一种改变的是对 E16 失败原因的解释，属科学判断而非编辑判断；且需回读 `e16_validation.json`。
- **作者须做** 在 §3.4 明确：`818 of the 896 documents for which a name was produced` 或 `818 of 1,128, counting the 232 declines as unmapped`。**在本轮撰写范围内，句子按原文保留。**

---

## 附：本轮已核对且**未发现问题**的自洽关系（供复核时免查）

以下等式均逐项验算通过，故不列入冲突：

| 关系 | 验算 |
|---|---|
| 漏斗 3,540 → 1,128 | 3,540 − 2,091 − 296 − 25 = 1,128 |
| 语料构成 | 875 + 253 = 1,128 |
| 粗分类覆盖 | 604 + 271 = 875 |
| 主类别分解 | 375 + 33 + 4 = 412；412/604 = 68.2%；412/875 = 47.1%；375/412 = 0.9102 |
| 食品轴交叉 | 603 + 272 = 875（另一仪器，与 604/271 不同轴） |
| 跨语种框架内外 | 438 + 437 = 875；375 + 33 + 26 + 4 = 438；271 + 166 = 437；100 + 66 = 166 |
| 裁决样本 | 104 + 121 + 26 + 19 = 270；(104+121+26)/270 = 0.9296；104/270 = 0.3852 |
| 分词敏感性 | 270 − 38 = 232；104 − 12 = 92；92/232 = 0.3966 |
| 锚点集 | 232 + 52 + 139 = 423 |
| 单遍协议 | 1,037 + 91 = 1,128 |
| 规则层负对照 | 14/50 = 0.28；32 + 18 = 50；14/32 = 0.4375 |
| 三人信度 | 13/80 = 0.1625；64/80 = 0.8000；11/80 = 0.1375；(64−42)/(80−42) = 22/38 = 0.5789 |
| E16 | 818/1,128 = 0.7252（见 CR-4 的分母问题） |
| 三构念门限差 | 0.60 − 0.4885 = 0.1115；0.75 − 0.7390 = 0.0110 |
| 框架敏感性倍数 | 16.30 / 2.63 ≈ 6.2，与 `a factor of six` 一致 |
| 附录 | 423 − 112 = 311 |

---

## 一处**非数值**但需登记的措辞风险

- **位置** §3.7 与 Appendix A 都使用 `top-tier`，而 §3.9 使用 `top-tier` 之外还写 `at this sample size`。
- **风险** 若 CR-1 的裁定结果是「228 含英文」，则 §3.9 的 `128 top-tier Chinese documents` 需同步改为 `128 of the 228 top-tier documents`，否则读者仍会读到两个规模。
- **处置** 与 CR-1 合并裁定，本轮不改。

<!-- v3.1 adjudication 2026-11-06 -->

---

## 裁决记录（2026-11-06，作者批准后执行）

**性质** 上文的四项 CR 已由作者逐项裁定；本节记录裁定、证据与落点。裁决不改变任何 CR 的原始描述，只补「查实结果」。

| 编号 | 查实结果（机器证据） | 落点 |
|---|---|---|
| CR-1 | **228 = 128 中文 + 100 英文**（`silver.jsonl` 按 tier×lang 计数：high zh 128 / high en 100）；`scripts/e9_selftrain.py:123` 的训练集 = `tier == "high"`，不分语种；`e9_split.json` n_train=228 | 附录 A 改为 `trained on the 228 top-tier documents’ high-confidence pseudo-labels (128 Chinese, 100 English)`；§3.7/§3.9 原文已写 `Chinese`，不动 |
| CR-2 | **38 = 8 F + 12 S + 13 I + 5 T**（`e17_segmentation.json → adjudicated_270.dropped_by_verdict`：`{S:12, I:13, T:5, F:8}`） | §3.3 改为 `8 of the 19 false matches (what segmentation is for), 12 of the 104 true subjects, 13 mentions and 5 statute citations`，38 项全部归因 |
| CR-3 | 维持原样（表述密度，不是数值矛盾；两处限定语已在位） | 无改动 |
| CR-4 | **818 含 232 篇拒答**：`e16_preds.jsonl` 逐篇复算 = 1,128 篇中 **896 篇写出名称（phrase≠"无"）、232 篇拒答**；**896 个名称中 586 个（0.6540）无词表命中**，310 个映射成功；`586 + 232 = 818` | §3.4 改为 `produced a name for 896 documents and declined in 232 ... yet 586 of the 896 (0.654)`；Discussion 的 `(818 names carry no lexicon term)` 同步改为 `(586 of the 896 names carry no lexicon term)` |

**CR-4 的论断强度** `The bottleneck is binding, not extraction` 仍成立：绑定失败 586 > 提取失败 232，但比例从 0.7252 降为 0.6540，正文已按分母可读的方式重写。

**新增可复算产物** `data/analysis/e16_denominator.json`（`_tools/v31_e16_denominator.py` 从冻结的 `e16_preds.jsonl` 重算，sha `c250ae50…`；输入 sha `ccd766f1…`）。`numbers.csv` 追加 4 行（`e16.n_named` 896、`e16.n_declined` 232、`e16.n_unmapped_named` 586、`e16.unmapped_share_named` 0.6540178571428571），数据行 584 → 588。旧的 `e16.n_unmapped=818` / `0.7252` 保留但不再被正文引用。

**数字多重集比对（v3 → v3.1，排除 References、`[n]`、`Section N.M`）**
- 新增 distinct：`0.654`、`586`、`896`
- 移除 distinct：`0.7252`、`818`
- 其余出现次数变化：`1,128` 7→5（两句不再以它为分母）、`100` 7→8、`128` 4→5、`13` 3→4、`5` 6→7（均为本次四处改动所致）
- **没有第五个数值被改动**。

**顺带修掉的一个检查器缺陷** 此前 v3 交付声称 `check_numbers.py`「497 个 token 全部有据」，但那次是对 `manuscript_submission_v3.src.md`（引用还是 `{key}`）跑的；对渲染后的 `manuscript_submission_v3.md` 复跑会报 4 个未授权 token，全是多引文组 `[7,8,9]` / `[15,16]` / `[22,23,24]` / `[28,29]`。已在 `_tools/check_numbers.py` 增加规则：紧跟 `[`、后接 `]` 且形如 `\d+(,\d+)+` 的 token 视为引文标记（由 `refs_crossref.json` 授权，不是测量）。v1 回归仍为 497/0。

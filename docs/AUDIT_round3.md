# 计划书—实现科学性一致性审查（第三轮）

时间：2026-11-04（UTC）。对象：`/opt/foods` 流水线，代码版本见 `README.md` 的
invariant 表与 `DEVIATIONS.md` D-30…D-42。

本轮起点是第二轮的两条结论：**实现与计划的偏差已基本收敛，剩下的缺口在数据**；
以及第二轮 S-1 给出的"actor-only 主图 11 节点/2 边"。本轮先修协议与检索两处
**结构性**问题，再用量到的结果重读全部实验门槛。

> **读数快照（先读这一条）**：本文件不是同一时刻的照片，各节的语料快照不同，
> 一律以**行内 sha 和时刻**为准。§二/§三/§五 的对照读的是 **987 行**语料
> （sha `2922e3ea…`，07–10 时段的快照）；**§八 已按 1015 行语料
> （sha `b4685bd7…`，2026-11-04T14:54:16Z）重述全部结论**。§八 与前文数字不一致时
> **以 §八 为准**；前文各节保留当时读数，不逐节回填（回填会让审计记录失去时间锚）。

---

## 一、本轮改了什么（及为什么必须整批重标）

| 编号 | 问题 | 处置 | 影响面 |
|---|---|---|---|
| D-30 | 6,000 字符截断 + `max_tokens=1600` 使**最长的文书**双通道同时解析失败（25/368，中位 5,559 字符 vs 已标注 2,629），且 27 篇的罚则条文落在 6,000 字符之后 ⇒ 锚点也被截断 | 协议 v2：全文上限 20,000 字符、max_tokens A 3,000 / B 4,000 / 裁决 4,000、vLLM `--max-model-len 23040`；`finish_reason` 区分"截断"与"解析失败"；整批重标 | E1 的全部读数 |
| D-31 | §6.2 要求"扩样由管线自动执行"，此前未实现 | `analyze/expansion.py` + 预登记批次表；每批记入 manifest kv 并给文档打 `expansion_batch` 标签 | E2 |
| D-32 | P115 关键词敏感性未做，且被淘汰文书不保留文本 | 全入样帧（clean + filtered + 淘汰原因）重算五个固定变体；淘汰文书文本存入 `data/clean/filtered/` | E1 边界 |
| D-33 | 网络指标可能读到过期 `dataset.jsonl` | 每个网络指标带 `dataset_lag_s` / `stale_dataset` | E2/E3 |
| D-34 | 罚则句只援引程序法时，锚点整篇丢失 | 锚点源顺序改为 罚则条文 → 全部援引条文 → 事实词表；`basis` 区分 `penalty_statute` 与 `cited_statute` | E1 锚点 |
| D-35 | 门户 `resultCount` 远大于可取回行数（每查询 200 行封顶） | 记录到 `coverage_probe.json`；E2 按实测节点数如实降级 | E2 |
| D-36 | **`quanwen_2` 不是全文第二个槽位，而是产品/食品 facet**：`["检验报告","餐饮"]`=1,544 而 `["食品","检验报告"]`=0、`["伪造","检验报告"]`=0 | 预登记批次 B4/B5 改为"全文槽放合取词、第二槽放食品 facet"；B1–B3 原样保留作为已执行记录 | 语料定义 |
| D-37 | `label` 出系统性异常时会把整批文档的 attempt 烧掉 | 起线程池前同步试标一篇，失败即 `RuntimeError` 整段中止 | 运行安全 |
| D-39 | 法条名带换行/`（2019修正）`/前缀`依照`时别名查不到，锚点静默丢失 | `_norm_law()` 只做格式归一（空白、括注、前导连接词），**不做后缀匹配**（避免把实施条例并入本法） | 锚点覆盖 |
| D-40 | 位移编码报 `0 events` 却不记读了多少篇 | 输出带 `denominator{n_docs_in_scope,n_docs_scanned}`；一篇没读则为 `not_estimable` 而非"无位移" | E4 |
| D-41 | `nx.write_graphml` 因 `docs` 是列表而必然失败，异常被 `pass`，留下 0 字节文件 | 导出副本（`docs` 用 `|` 连接）；失败删除残件并记入指标 | 无（无闸门读取） |
| D-42 | E5 稀疏表把不合格的卡方 p 值留在头条字段 | 稀疏时卡方移入 `chi2_unreliable`，`primary_test=fisher_collapsed`，闸门与图题读 `primary_test` | E5 推断口径 |

D-36 是本轮最重要的发现：**第一轮 36 条检索里，凡第二槽是文书类型名的，结构上必然是 0**。
因此"扩样跑了两批、new=0"不是语料枯竭，而是检索写错了。B1 实测 `new=0` 佐证了这一点。

---

## 二、协议 v2 的效果（v1 → v2 同文档对照）

**读数口径**：`data/archive/v1_20261104T0235Z/silver.jsonl`（644 条，sha 见归档目录）
对 `data/silver/silver.jsonl`（987 条，sha `2922e3eaedac110a5d6bd84f67ec479e4697c71c54ab6d1014195ce456d2dd43`），
按 **doc_id 且 text_sha 同时相等**配对，得 **621 对**（23 条因文本或缺失未配上，
不计入任何均值）。

| 量 | v1 | v2 | 差 |
|---|---|---|---|
| 平均一致率 (n=621) | 0.7585 | 0.7026 | **−0.0558**（sd 0.1601，SE 0.0064，≈8.7 SE） |
| high / medium / low | 154 / 192 / 275 | 135 / 109 / 377 | — |

**这不是运行间噪声。** 同协议重标（`data/metrics/stability_v2.json`，48 篇分层抽样，
2026-11-04T04:53–05:16Z）：平均 Δ **+0.0011**，sd 0.0868，SE 0.0125。即
v1→v2 的位移约为重标噪声的 4.5 倍，是系统性的，只能归因于**打包的协议变更**
（`max_tokens` 1,600→3,000/4,000、通道拆分）。

**机制**：两条通道各自独立标注后按跨度对齐，标注越密、两通道在"该锚哪一段"
上的分歧越多，micro-F1 就越低。中文语料的密度本就高于英文（见第八节），
所以真正的解释变量是**文书标注密度**，不是"v2 更差"。

**同时必须说明的漏出（D-46）**：v2 波次 1,041 篇中 54 篇被拒（5.2%），
被拒文书更长（p50 4,810 字符 vs 已标 3,096），偏长偏差仍在。
因此上面所有数字都**条件于"答案能装进 4,000 token 的文书"**。

---

## 三、锚点修订（D-34）

**读数口径**：`data/metrics/anchor_20261104T0704Z.json`（987 条，07:04:21Z，
归档 `data/archive/preretier_20261104T0704Z/silver.jsonl`）。

| 量 | 值 | 分母 |
|---|---|---|
| 记录数 | 987 | — |
| 锚点/分层被改写 | 741 | 987（75.1%） |
| 违规类别改变 | 1 | 987 |
| `anchor_pass` 翻转 | 0 | 987 |
| 取不到正文 | 0 | 987 |

> **D-67 更正（2026-11-04T11:28Z）**：上表的 `changed=741` 是 retier 的
> `changed` 计数器，不是"741 篇的锚点/分层被改写"。用归档
> `data/archive/preretier_20261104T0940Z/silver.jsonl`（987 行）逐条按 JSON
> 规范化重算：语义锚点差异 **0/987**（category 0、basis 0），真实的 tier 变化只有
> `medium→low` **21/987**；其余 720 条是 `anchors.label` 的 tuple 与 silver 的 JSON
> array 之间的类型差异。741 不得读作改写篇数（详见 `DEVIATIONS.md` D-67）。

basis 迁移（前后）：

| basis | 前 | 后 |
|---|---|---|
| penalty_statute | 205 | **218** |
| cited_statute | 63 | **51** |
| statute+fact | 104 | 104 |
| fact_only | 83 | 81 |
| ambiguous_facts | 81 | 82 |
| ambiguous_statute | 23 | 24 |
| 无锚（null） | 428 | 427 |

分层迁移：`high→high` 170、`medium→medium` 179、`low→low` 617、
`low→medium` 21。high 层按语种 **zh 79 / en 91**。

**这 21 条 `low→medium` 是缺陷不是结论（D-47）**：tier 复算当时从 4 位小数的
`metrics.agreement_f1` 反推，而标签阶段用的是未取整值（`micro_f1` 可返
0.7499999999999999）。已改为读 `metrics.agreement_f1_exact`、必要时从通道实体
重算。修正后应为 **high 170 / medium 179 / low 638**，high 层不变
（所以主分析语料的任何数字都不受影响，只有 `high_medium` 敏感性会变）。
修正写入 silver 的时点在下一个周期边界——若本文下方出现 medium 200/低 617，
即表示修正尚未落地。

---

## 四、扩样与语料天花板（D-35、D-36）

**读数口径**：`data/analysis/coverage_probe.json`（50 个探针）、
`state/foods.sqlite` 的 stage 分布、`data/silver/silver.jsonl` 的
`meta.expansion_batch` 计数（均为 2026-11-04T07:5xZ 读数）。

**门户硬上限（实测）**：对 `伪造+食品` 逐页翻取，门户自报 721 条，
第 1–4 页各 50 条（合计 200），**第 5 页返回 0 条** ⇒
每查询最多取回 **200 行**，与自报结果数无关。

**覆盖面**：50 个探针中 12 个零结果、26 个完全可达、**24 个触顶**；
自报结果数合计 **424,707**，实际可达 **5,168（1.2%）**，首页未见过
1,122 条。结论：**覆盖面只能靠检索词广度，不能靠翻页深度**（D-35/D-36）。

**语料构成**（zh = 742：base 494 / B3 103 / B4 145）：

| 波次 | 中文文书 | 其中 high |
|---|---|---|
| base crawl | 494 | 62 |
| B3 | 103 | 7 |
| B4 | 145 | 10 |
| 合计 | 742 | **79** |

英文 openFDA 245 篇（high 91）。全语料 987。

**天花板与网络的关系（D-49/D-50）**：扩样能增加节点，但**不能增加边**——
一篇文书内要有两个以上不同主体才成边，中文 high 79 篇里只有 **7 篇**满足（“两通道各自都含 provider 与 end_user”的严口径是 3 篇，D-54；报结构上限一律用 7/79）。
实测 actor 图的边数已等于文书结构允许的上限（饱和）。因此**继续扩样救不了
§6 网络**，§6 应报 `not_estimable`。

---

## 五、逐条对照第二轮遗留项

| 第二轮 | 状态 | 说明 |
|---|---|---|
| S-1 节点分类 | 已修（D-26） | 第二轮"11 节点/2 边"取自**过期数据集**；全新 extract 后实测 **62 节点/7 边**（9 SERVICE_PROVIDER / 53 END_USER）。第二轮那句话须按 D-33 更正 |
| S-2 E5 语料边界 | 已修（D-27） | high 主表 + high+medium 敏感性 |
| S-3 长文书偏差 | 已修（D-30） | 见第二节 |
| S-4 统计量定义 | 已显式化（D-27） | `mean_agreement` 与 `pooled_micro_f1` 并列 |
| M-1 文献标定 | 已补 | `literature_calibration` |
| M-2 自动扩样 | 已实现（D-31/D-36） | 不是"未实现"，而是"实现了但检索语义写错"，本轮修正 |
| M-3 关键词敏感性 | 已实现（D-32） | 见第六节 |
| M-4 D2 覆盖 | 保持 | D-22：仅总局抽检通告，D2 不进入任何估计量 |
| M-5 faiss/webhook/key | 保持（D-29） | 不影响估计量 |
| M-6 P095 类型收缩 | **前提已变，重开并落地为语料变体**（D-53） | 当初"只记录不落地"是在一致率 **0.7585 > 0.75** 时做的决定；协议 v2 全集一致率 **0.6828 < 0.75**，P095 的触发条件已满足。处置：**E1 状态仍按全集记**（收缩值不得冒充 E1），另出 `data/metrics/tier_shrunk.json` （稳定类型 END_USER/JURISDICTION/PENALTY_EVENT，收缩后 0.8471，high 170→319），下游估计两语料并列。这不改变 §6 的 `not_estimable`——被丢弃的 SERVICE_PROVIDER 正是网络要的类型 |
| M-7 配置与代码脱节 | 已修 | `valid_types()` 读 `label.entity_types`，未知类型直接报错 |

---

## 六、关键词与入样框敏感性（D-32）

**读数口径**：`data/analysis/keyword_sensitivity.json`
（2026-11-04T07:29Z，在最终语料上重算；此前 04:07 那份是在重标中途算的，
`high_tier_n` 只有 10，**已作废**）。入样框 2,384 篇，基线规则（`plan_rule`）
准入 788 篇，其中 high 层 **79** 篇。

| 变体 | 准入 | 与基线 Jaccard | high 保留率 | 丢失的 high 篇数 |
|---|---|---|---|---|
| `plan_rule`（基线） | 788 | 1.0 | 1.0 | 0 |
| `drop_jiamao` | 768 | 0.9746 | 0.9873 | 1 |
| `widen_fraud` | 917 | 0.8593 | 1.0 | 0 |
| `strict_documents` | 736 | 0.9340 | 0.9620 | 3 |
| `proximity_80`（80 字窗口共现） | 217 | **0.2754** | **0.3544** | 51 |

**结论（必须与估计量同印）**：入样框对**词典变体稳健**（Jaccard ≥ 0.86，
high 保留 ≥ 96%），但对**共现规则不稳健**——把"同文共现"收紧成"80 字内共现"
会砍掉 72.5% 的入样框并只保留 35.4% 的 high 层。因此本文所有结论都
**条件于"共现在文书层面成立"**，这一点不是实现细节，是识别假设。

---

## 七、计划书逐条覆盖矩阵

图例：**✅ 已实现并已产出** ｜ **⚠️ 已实现但受外部条件限制（读数如实降级）** ｜
**❌ 未实现（写明原因与是否影响估计量）**。
"依据"一栏只写能复读的落点（模块 / 产物 / 偏差号），不写形容词。

### 7.1 第四部分 数据方案（P041–P062）

| 条目 | 计划要求 | 实现 | 状态 | 依据 |
|---|---|---|---|---|
| P039 | 全自动采集，无"人工下载后投放" | 全部采集器经 requests/API；无人工投件路径 | ✅ | `collect/*.py`；`pipeline.log` 采集日志 |
| P042 D1′ | 约 50 个省市监局处罚公示栏目全自动爬取（requests 优先、Playwright 兜底）；伪造/虚假 + 检验检测报告/认证/溯源码 | 50 站注册表 + 通用适配器（栏目发现、GBK 解码、处罚文书门）；Playwright 仅标记 `needs_playwright` 未启用 | ⚠️ | `collect/municipal.py`；`config/sources.yaml`；实测产出 **1 篇**（D-38）。主量实际来自全国 cfws 门户 |
| P043 D2 | 总局"铁拳"/抽检通告，千级条目 | 列表页采集 + 事件抽取 | ⚠️ | 18 链接 / 14 事件（D-22）；不进任何估计量 |
| P044 D3a | openFDA API 欺诈子集 | 4 条 API 查询 × 150 上限 | ✅ | `collect/openfda.py`；253 条入册 |
| P045 D3b | RASFF 数据集 + 2022 后窗口页 | 门户探测失败后停止 | ❌ | `collect/rasff.py`；计划 §4.2 明示失败非阻断；影响 E5 的 EU 一侧（见 P092） |
| P046 D4 | D2 + 两高案例页自动抽取，百级事件 | 静态页采集 + LLM 事件判定 | ✅ | `collect/gov_events.py`；**490 事件** |
| P047 可选 | 人民法院案例库（Playwright 登录） | 未实现 | ❌ | 计划标注"可选…不影响主线" |
| P048–P056 | 已排除源留档 | 未接入 | ✅ | `DEVIATIONS.md` 记录 |
| P058 | D3a/D3b 只做类型学对照 + 境外样本外验证 | `compare.py` 输出 CN/US 分布与卡方/Fisher（不足期望频数即降级）；英文文本走同一双通道 | ✅ | `analyze/compare.py`；`data/analysis/compare.json` |
| P060 | 合规：不绕访问控制、日志留档 | 政府站点 2 s/req；UA 声明用途 | ✅ | `runtime.gov_rate_seconds`；`pipeline.log` |
| P062 | 磁盘 ≤70 GB（原始≤10／中间≤10／索引≤5／权重≤35／结果≤10） | 无 faiss 索引（D-29），权重 15 GB | ✅ | 实测 **14 GB used / 70 GB (20%)** |

### 7.2 第五部分 架构 L0–L6（P065）与工程要点（P077–P082）

| 层 | 计划要求 | 实现 | 状态 | 依据 |
|---|---|---|---|---|
| L0 | cron/systemd 每日 02:00 增量 | `install_daemon.sh` 幂等安装；夜窗跑链 | ✅ | `scripts/install_daemon.sh`；`logs/daemon.out` |
| L1 | 50 站适配器 + samr + openfda + rasff + spc/spp + alk(可选) | 前五项；alk 未做（计划标可选） | ⚠️ | `collect/` |
| L2 | 去重（标题+案号 hash）、分类、正文抽取、时间规范化、PII 脱敏 | 均有；`dedupe_key = sha256(case_no|title)[:32]` | ✅ | `clean/normalize.py:73,211` |
| L3 | raw 只追加、clean、SQLite manifest 状态机、faiss | 前三项；faiss 未做 | ⚠️ | `manifest.py`；D-29 |
| L4 | 双 LLM 交叉标注 → 分流 → 银标准（逐实体置信度）→ vLLM 全量抽取 → 自训练/自一致性阶梯 | 全部；self-training 以阶梯判定触发，自一致性在裁决通道已常态运行（5 采样多数投票） | ✅ | `label/silver.py:73,127`；`extract/runner.py` |
| L5 网络 | 网络构建（PyG） | networkx 3.5（P107 的可行性清单即 networkx） | ✅ | `analyze/network.py` |
| L5 攻击/恢复 | 定向 vs 随机移除曲线 | 定向/随机 + 最大连通分量曲线，低于阈值出状态卡 | ✅ | `analyze/attack.py` |
| L5 生存 | Cox + bootstrap CI | lifelines；事件数不足即声明不可估 | ✅ | `analyze/survival.py` |
| L5 Hawkes | 再生拟合 | 参数拟合 + 非参数回退；退化即报退化 | ✅ | `analyze/hawkes.py`；`hawkes=degenerate` |
| L5 位移 | 六类型编码 | 六类型计数；无事件即 0 事件如实报告 | ✅ | `analyze/displacement.py` |
| L5 对照 | 中美欧 | 实为中美（EU 缺 RASFF） | ⚠️ | `analyze/compare.py` |
| L6 图表 | Foods 风格模板 | 六面板 300 dpi；未估计项渲染为状态卡而非空图/假曲线 | ✅ | `report/figures.py`；`reports/figures/*.png` |
| L6 稿件 | 英文 LaTeX/Word | 属写作阶段，非流水线 | — | 不在本轮范围 |
| L6 日报 | 每日 webhook | 日报落盘 + `ALERTS.md`；webhook 代码在、地址未配 | ⚠️ | `report/daily.py:88,116` |

| 工程条目 | 计划要求 | 状态 | 依据 |
|---|---|---|---|
| P077 断点续传 | SQLite manifest 状态机，崩溃恢复 | ✅ | `manifest.py`；`scripts/chain_locked.py` |
| P078 限速 | 政府 ≤1 req/2 s + 指数退避；openFDA 免费 key | ✅/❌ | 限速✅；**无 key**（0.35 s 无密钥节奏，D-29） |
| P079 告警 | 3 次退避失败 webhook/邮件；GPU 显存不足自动降 batch | ⚠️ | 无外部通道 ⇒ `ALERTS.md` 显式落盘；vLLM 外置，OOM 降 batch 不适用 |
| P080 磁盘 | 80% 告警 / 95% 自动清理 | ✅ | `runtime.disk_warn_pct/disk_clean_pct` |
| P081 部署 | docker-compose | ❌ | D-1：单机直接跑，环境已固化在 pod |
| P082 规模 | 约 3,500 行 | ✅ | 实测 **5,247 行**（`foods_pipeline` + `scripts`） |
| P120 冒烟 | `make smoke` 通过 | ✅ | `Makefile`；实测 **9/9 OK**（对齐算术、锚点映射、攻击方向、Hawkes 参数回收、入样规则、JSON 修复） |

### 7.3 5.2 三重独立证据链（P067–P075）

| 证据 | 计划要求 | 实现 | 状态 | 依据 |
|---|---|---|---|---|
| ① 双通道一致 | 两模型族 **或** 独立提示词 + 不同温度；span IoU τ=0.5 | prompt-α/T=0 与 prompt-β/T=0.3，实体级 span 对齐 | ✅ | `label/prompts.py`；`label/align.py` |
| ② 规则锚点 | 法条 → 违规类别映射（确定性，公开可复核） | 罚则条文 → 全部援引条文 → 事实词表（D-34），逐篇记 `basis` | ✅ | `label/anchors.py`；`basis_counts` |
| ③ 文献标定 | CAEC_LLM 零样本 ~70% / 微调 ~82% | `literature_calibration` 写入 E1 | ✅ | `data/metrics/e1.json` |
| 裁决通道 | 更强模型单次 **或** 5 次温度采样多数投票 | 5 采样多数投票，T=0.7 | ✅ | `label/silver.py:73,127` |
| 主分析语料 | 只跑高置信子集，全量作敏感性 | `tier=high` 才能进主图；medium 仅见于 D-23 敏感性表 | ✅ | `analysis.network_node_types`；`gates.py` |
| ④ 降级清单 | 低置信类型降级清单 | `tier_counts` + `by_lang` + 类型收缩阶梯（P095 触发条件已满足，改为语料变体落地，见 D-53/M-6） | ✅ | `data/metrics/e1.json` |

### 7.4 第六部分 实验矩阵与失败预案（P088–P099）

| 实验 | 判据（计划） | 流水线是否按判据自动分档 | 状态 |
|---|---|---|---|
| E1 | 一致率 ≥0.85 且锚点 F1 ≥0.80；底线 0.75/0.70 | `gates.py` 按目标/底线双档；锚点样本不足加 `_anchor_insufficient` 后缀 | ✅ |
| E2 | 800 节点 / 400 底线 / <400 转类型学 | 节点数与 `stale_dataset` 同时判 | ✅ |
| E3 | 攻击容忍、Cox、Hawkes | 三个估计器各自可 "不可估" | ✅ |
| E4 | ≥15 事件 / ≥8 / 并入定性 | 事件计数分档 | ⚠️ **0 事件**（主分析语料 57 篇分母）；全中文层正对照 2/391 有上下文命中 ⇒ 仪器能发火但敏感性极低、且构念可能不可观测（D-57）。490 是 D4 政策事件（供 E3 生存/Hawkes），**不是** E4 计数 |
| E5 | 描述性 + 卡方/Fisher；境外性能报告 | 期望频数不足即 `insufficient_data`，不出 p 值 | ✅ |
| 附加 | 置信度分层稳健性（high vs 全量） | `sensitivity.py` | ✅ |
| P095–P099 | 三档失败预案 + 全局兜底 | `gates.actions` 自动写降级动作并记 kv | ✅ |

### 7.5 第八部分 严谨性低成本项（P115）

| 项 | 状态 | 依据 |
|---|---|---|
| 双通道重叠一致率报告 | ✅ | `e1.json`：`mean_agreement` 与 `pooled_micro_f1` 并列 |
| 零样本 / 自训练对比 | ✅ | E1 `ladder`（触发才写，不触发即证明未降级） |
| 关键词敏感性 | ✅ | `analyze/keywords.py` 五个预登记变体（D-32） |
| 固定种子 | ✅ | `analysis.seed: 20261104`；spring_layout/Hawkes/bootstrap 同种子 |
| 代码与银标准数据集开放 | ⏳ | 打包阶段；当前树无第三方凭据（凭据在树外 `D:\_creds_foods_20261104`） |

### 7.6 未实现项总表（诚实清单）

| 项 | 原因 | 是否影响估计量 |
|---|---|---|
| faiss 向量索引（L3） | D-29；无语义检索需求，去重按 hash | 否 |
| docker-compose（P081） | D-1；单 pod 直接部署 | 否 |
| RASFF / EU 一侧（D3b、E5） | 门户数据集取回失败；计划 §4.2 预置为非阻断 | 使 E5 收窄为中美 |
| Playwright 兜底（D1′） | 未安装浏览器；JS 站标 `needs_playwright` | 否（已按事实降级） |
| openFDA 免费 key | 未申请；无密钥节奏已按 0.35 s 控速 | 否 |
| 人民法院案例库（P047 可选） | 计划标可选 | 否 |
| webhook（P079/L6） | 无外部通道；`ALERTS.md` 替代 | 否 |
| D2 千级条目 | 实测 18 链接/14 事件 | 否（不进估计量） |

---

## 八、结论

**读数截至 2026-11-04T14:54:16Z（silver 1015 行，sha `b4685bd77cc2b3e750b40dd692ea62bce1d7c5ea8bffb1a34d4040172e3927b9`）；语料未冻结，daemon 下一周期 2026-11-05T02:00Z。**

- **语料**：1015 篇（zh 763 / en 252；docs `extracted` 1015 = silver 1015）；high 223（zh 124 / en 99）/ medium 335 / low 457；实体行 3,947。
- **E1 failed（不是达标），且必须按两个估计量分开报**：
  - **预注册 E1 = 0.6898**（n_scored 991；636 篇用归档的单次解码通道、24 篇无归档被排除），zh 0.6504 / en 0.8083；低于底线 0.75。**这是论文 E1 该引的数**（D-68）。
  - `e1.json` 头条 **0.7457**（n_scored 1014、zero-entity 1；en 0.8151 / zh 0.7228）是**阶梯后混合**（660 篇 5 采样投票 + 355 篇单次），**不得当作预注册估计量的“提升”，两者不得互相代引**（D-63/D-65/D-68）。
  - 收缩类型（END_USER/JURISDICTION/PENALTY_EVENT）0.8577；锚点 macro 0.2861 / micro 0.8247（n=388），per-class 支撑见 `gates.E1.anchor_support`；门禁统计量未改（D-58）。
- **E2 downgraded**：130 节点 / 9 边；结构上限 = 9（124 篇主语料中仅 9 篇有 ≥2 个不同 actor 节点，即 `docs_with_provider_and_end_user` 亦为 9），边饱和 1.0。§6 报 `not_estimable`（D-49/D-50），不得写成“网络稀疏”或“市场结构”。
- **E3**：attack=`insufficient_nodes`；survival=`inconclusive`；Hawkes=`degenerate_fit`（分支比 0.7525、tie_share 0.5315、非参数 KS p≈1.2e-25、dispersion_index 2.638，p_mc=0）。负/不显著照实报。
- **E4**：主分析语料 **0/124**；同一规则全中文层正对照 **2/760** ⇒ 检测器能发火但敏感性极低（D-57）；`downgraded_to_qualitative`，不扩词表。
- **E5**：`not_estimable_degenerate_main_corpus`；high 层 cn modal FALSE_LABELING 94.35%（117/124）、us 95.96%（95/99）；collapsed Fisher 表 `[[3,121],[0,99]]`，p=0.2561（odds_ratio=inf）；选择不对称 2.418。全层分布仅描述性（D-51）。
- **产物验收**：`verify_products` **28/28 PASS**、2 stale（`anchor_20261104T1451Z.json` 的 `basis_counts`/`f1_exact_stale_docs` 早于 14:54:16Z 的 silver，是 retier 回执，下次 retier 刷新）；`gates.module_status`：`receipt_present=true`、`failed_modules={}`；`graphml.written=true`；displacement `denominator{124,124}`；compare 带 `main_corpus_profile`/`selection_diagnostic`/`test_on_degenerate_table.primary_test`；e1 带 `n_scored_agreement`/`n_zero_entities`/`align_ground_malformed`/`decoding_mix`。
- **残留限制**：
  - `normalized` 在主路径上从未存在（channel A **0/4063**、channel B 1601/3993、最终 `entities` **0/3947**）；`alpha_*` 模板从不请求该字段，最终实体集取自 channel A ⇒ 节点身份一律为原文串（去括号/空白），跨文书合并按字面相等（D-69 更正了 D-62 的归因；D-62 的回填脚本保留，实测产出 0）。
  - 24 篇被投票文书无阶梯前归档，预注册 E1 不含它们；`_snapshot_preladder()` 已在投票前存档，该损失到此为止（D-68）。
  - `tier_shrunk.json` 的 actor 结构是 **silver 实体集上的上界**，§6 结构上限一律引 `network_metrics.actor_coverage`（D-66）。


## 九、发布快照（2026-11-04T15:13Z）

- **语料未冻结**：本快照是**钉住的版本**，不是终版。daemon 下一周期 2026-11-05T02:00Z 后仍会增加文书，届时再出一版（`foods_silver_20261105`）；§八 的全部读数与本快照同源。
- **构建前置**：`chain_locked.py retier extract analyze report` 于 15:08:50Z 全部 rc=0；**silver sha 在构建前后同为 `b4685bd7…`** ⇒ retier+extract 幂等（不是"重跑就会漂"）；`e1_preladder.py` 复算仍为 **0.6898**（991 / 636 代入 / 24 排除，三项不变）；`tier_shrunk.py` 按当前语料重算（high 223→342、medium 335→418、low 457→254，收缩一致率 **0.8577**）；`query_family_agreement.py` 重算；`verify_products` **28/28 PASS、0 stale**。
- **包**（`/opt/foods/release/foods_silver_20261104`，5.0 MB，22 件）：`data/silver.jsonl`（1015 行，sha `b4685bd77cc2b3e750b40dd692ea62bce1d7c5ea8bffb1a34d4040172e3927b9`）、`data/dataset.jsonl`（3,947 行）、`metrics/`（18 个门禁与估计 JSON）、`foods_code.tar.gz`（sha `7f27bfb27e41a779d8ae4e5d8cbf37d9012c4e30d8f3f839aac67666ffc8e0c3`，内含 D-70 与打过补丁的 `scripts/export_release.py`）、`RELEASE.json`、`MANIFEST.tsv`、`MANIFEST.sha256`。
- **校验**：pod 上 `sha256sum -c` **22/22 OK**；整包 tarball sha `9ef85f0c548b55f009cbb64377e7741ec50751ca071aed4b69592e7b2edea39d`；**本机解包后独立复算 22/22 OK**（跨机复算，不是同一台机器的自证）。
- **不含**：原始 HTML/PDF、清洗文本、`state/`、`logs/`、模型权重、`metrics/_module_status.json`（逐周期回执，非结果，D-61）。
- `RELEASE.json` 的 `e1_reported_twice`：预注册 **0.6898**（`metrics/e1_preladder.json`）与阶梯后混合 **0.7457**（`metrics/e1.json`）**不可互换**——这条说明随包发布，读者无法把两者对调（D-63/D-68/D-70）。
- **复发条件**：同一 UTC 日第二次构建会 `REFUSED`（日期戳目录已存在）；重建须 `--out` 或次日再建（D-70）。

## 十、v7 补跑实验（E6–E8）的审计（2026-11-05T01:2xZ）

计划书 v7 新增 E6/E7/E8 三个 Results 实验并要求补跑；E9（QLoRA 自训练）未执行。本节只审这三件产物**能否支撑**论文对应的表，以及它们**不能**支撑什么。

### 10.1 覆盖矩阵（v7 部分）

| 计划书条目 | 状态 | 产物 | 判读 |
|---|---|---|---|
| E6 确定性描述套件（Results 1） | 完成，**降级为粗粒度** | `data/analysis/e6_descriptive.json` | 负对照 0.39 < 0.75 ⇒ 正文只报 5 类粗粒度 |
| E7 行为—危害类型学（Results 2） | 完成 | `data/analysis/e7_typology.json` | 双通道一致率 0.8226 ≥ 0.80 标杆 |
| E8 中美对照（Results 3） | 完成，**不可估** | `data/analysis/e8_us_cn.json` | 美国侧明示造假线索 0/253 ⇒ 只报构成描述 |
| E9 QLoRA 自训练 | **未执行** | — | 训练栈缺失 + vLLM 占显存（D-78），不进发布路径 |

### 10.2 能支撑什么

- 中文 763 篇（`lang=zh`）的**粗粒度**违法类型构成（DATA_FALSIFICATION 367 / UNDETERMINED 226 / MARKET_ORDER 90 / PROCEDURAL 54 / UNLICENSED 26）、规则可判定率 0.7038、食品类别/地域/罚款的描述分布；
- high 层中文 124 篇的行为—危害类型学（7 条目、5 条匿名引文、2 条待人工审计）；
- 中美食品执法文书**体裁构成**的差异，以及"同一构念在两侧不可比"这一可验证的缺席。

### 10.3 不能支撑什么（写作红线）

1. **不能把九类细粒度分布写成主结果**——负对照 0.39 低于 0.75，细粒度表只能随产物发布并附脚注（D-79）。
2. **不能报"中美造假率差异"**——美国侧 `reason_for_recall` 根本不编码故意性，0/253 明示线索 ⇒ `not_estimable_instrument_mismatch`（D-75）。
3. **不能把 openFDA 样本量写成 ~800**——磁盘实测 253（D-75）。
4. **不能把 E7 的 0.8226 当作稳定值**——温度 0.3 采样，两次运行 0.8306 / 0.8226；论文须注明"运行间小幅波动，判定不随波动改变"。
5. **不能拿 v2 映射的结果去回填 E1**——E1 锚点用 v1，Results 1 用 v2，两套映射同时存在是有意的（D-72）。

### 10.4 与前文各节的接口

- §八的预注册 E1 0.6898 不受 E6 影响（锚点读 v1）；Results 1 的分布读 v2。
- E8 复用 E6 的产品间分布；`scripts/verify_products.py` 有"E8 与 E6 同一语料"的 sha 交叉校验。
- 本节数字的时间戳全部取自产物 `at_utc`：E6 `2026-11-05T01:09:50Z`、E7 `2026-11-05T01:15:07Z`、E8 `2026-11-05T01:12:51Z`。**若冻结后的终版重跑这三件（finalize 的 extras 循环会重跑），以终版产物为准并按新 `at_utc` 另记，不回填前文。**

### 10.5 两处修订（2026-11-05T01:2xZ）

- **E8 的表曾错位（D-80）**：首版产物 `table_rows` 写 6 类而表体删掉全零行后只有 5 行，按下标对齐导致 markdown 表头与数字系统性错配；折叠 Fisher 又用删零前的下标索引删零后的表，**首版 p=3.36e-06 实际检验的是 UNLICENSED vs 其余，已作废**。修正后（`at_utc` 2026-11-05T01:23:55Z）：表为 FORGED 30/0、FAKE_CERTIFICATION 4/0、FALSE_LABELING 333/97、UNLICENSED 26/0、OTHER 0/156；折叠 Fisher **cn [333,60] vs us [97,156]、OR 8.93、p=2.44e-34**。映射表、类别集合、可估性判据均未变，`not_estimable_instrument_mismatch` 不变。
- **E6 残差有了描述（D-81）**：63 篇 `basis=none` 中，**13 篇**的罚则只引《行政处罚法》（形式机制），其余多数引的是《计量法》《商品条码管理办法》《专利法》《反不正当竞争法第九条》等**不在五类造假框架内**的法。只描述、不分类；`resolved_share` 0.7038 与粗粒度分布不变。法名抽取串（"经营者违反本法""本法""本条例"）不可当作独立法律加总。

### 10.6 终版冻结后的数字替换（2026-11-05T04:10Z；权威以 `data/reports/finalize_20261105.json` 为准）

§10 各小节的数字全部来自 01:2xZ 那次**未冻结**语料（763 篇中文 / sha `b4685bd7…`），**只作过程留档，不得引用**。
终版 `status="released"`（`finished_utc 2026-11-05T03:57:03Z`），语料 **1128** 篇、sha `a1deda2c…`，`verify_products` 37/37 pass / 0 stale，包 25/25 校验通过。替换表：

| 项 | 旧（作废） | 终版（引用这个） |
|---|---|---|
| E6 中文分母 | 763 | **875**（`at_utc` 03:54:28Z） |
| E6 规则可判定 | 537/763 = 0.7038 | **604/875 = 0.6903** |
| E6 粗粒度 | 367/226/90/54/26 | **412 / 271 / 100 / 66 / 26** |
| E6 负对照 | 0.39 | **0.28** |
| E6 `basis=none` 残差 | 63（其中 13 篇仅援引《行政处罚法》） | **100（其中 19）** |
| E6 食品可归类率 | — | **603/875 = 0.689**（UNMATCHED 272） |
| E7 | 0.8226，n=124，裁决 22 | **0.8203，n=128，裁决 23，codebook 49 条** |
| E8 中国侧 | 393 | **438**（frame 875，UNRESOLVED 271） |
| E8 折叠 Fisher | cn[333,60] vs us[97,156]，OR 8.93，p=2.44e-34 | **cn[375,63] vs us[97,156]，OR 9.5729，p=2.16e-37** |
| E1 阶梯后混合 | 0.7457 / n=1015 | **0.7460 / n=1128**；稳定类型子集 **0.8610** |
| E1 预注册单次 | 0.6898 / n=991 / lost 24 | **0.6966 / n=1037 / lost 91**（D-87） |
| 锚点 micro | 0.8247 / n=388 | **0.7825 / n=423** |
| 锚点 macro(≥20) | 0.6798 | **0.4195** |

**★锚点 macro 的口径陷阱（D-88）**：0.6798 = (0.908+0.4516)/2（只含 FALSE_LABELING 与 UNLICENSED），0.4195 = (0.8801+0+0.3784)/3——
差别来自 **OTHER 的 support 从 19 涨到 31、跨过预注册的"支持 ≥20"线**，不是模型突变（同轮 micro 只从 0.8247 到 0.7825）。
**不许改这条线把数拉回去**；报数必须带类清单与 support。另：模型把 798/1128（70.7%）判成 FALSE_LABELING，对 OTHER 类从不输出（0/31），
对 UNLICENSED 仅 14/52 正确——这是"仪器在未定型类上不可用"的直接证据。

**冻结期运维事故**：D-83/D-84（root 跑链把 silver 改成 644；受害文书实为 **2** 篇，296 篇 `failed` 全是 `awaiting_pdf`）、
D-85（`release/` 不可组写致 export `PermissionError`）、D-86（25 篇协议层不可标，且这批文书中位长度是语料的 **1.80×**）、
corpus_drift（链内 `retier` 一次性语义改动；之后幂等）。

### 10.7 T1 结案（年份是采样窗口产物）与 E9 仪器修正（2026-11-05T04:20Z）

**T1 —— E6 的 2026 年占 69.5% 不能说成趋势。** 两条独立证据：
1. **门户默认排序 = 发布日倒序**（`collect/cfws.py` 载荷 `"sortFields": ""`）。活探 page 1：`伪造/食品` 由 `2026-10-16` 单调降到 `2026-07-28`；`检验报告/食品` 由 `2026-10-19` 降到 `2026-09-30`。
2. **每个查询只发 4 页 = 200 行**（`2026-11-05T04:24Z` 实测：`检验报告/食品` `resultCount=6,760`，page2/3/4 各 50 行、**page5 = 0、page6 = 0**；`伪造/食品` `resultCount=720` 同形）。
   `max_pages_per_query: 40` 因此形同虚设。全量探测产物 `data/reports/t1_coverage_probe.json`（`at_utc 2026-11-05T04:14:40Z`，sha `ca3c9d2493618c960631a5f23fde71f3cf093596b9ab5f81a78c709f0241bcbc`），92 个已注册查询：
   16 个查询 `resultCount > 200`，其合计 **27,850**，而**单查询登记数最高只有 201**；`检验报告/食品` **6,760 → 174**、`虚假/食品` **5,260 → 88**、`冒用认证标志` **1,471 → 197**。
   **口径提示（D-90 更正）**：逐查询登记数只记"第一次看到该文的查询"（按 `doc_id` 去重）⇒ 是**下界**，不能拿某查询的登记数低于 resultCount 反推"丢件"，也不能拿它等于 resultCount 证明"完整覆盖"。
⇒ 语料 = "按发布日倒序、每查询前 200 行"的并集；年份构成是**采样窗口 + 门户存量**，不是处罚年份事实。
**写作红线**：禁 `increasing / rising / 近年上升 / 逐年增长`；不得称"全国 N 篇"；只写"本采样帧内、默认排序前 ~200 行所见的构成"，并附上表 3 个 `resultCount vs 登记数` 例证作为覆盖上界。
（佐证：2026-08/09 峰值在 `filtered_out` 385/501 与 `extracted` 120/161 里同时出现 ⇒ 是采集端的形状，不是标定筛出来的。）

**E9 —— 首跑作废是仪器问题，不是模型问题（D-89）。** `_predict` 原来把裸 prompt 直接 `tok(prompt)` 喂给 instruct 模型；
而标注路径（`label/llm.py`）是把 `messages` 交给 `/chat/completions`，由 vLLM 套 ChatML。后果实测：基座臂 **49/50 篇解析不出类别**。
若照原样跑完，adapter 只需学会输出 JSON 就能把 macro 锚点 F1 从 ~0 抬过 **+3 点** 判据——那是把"格式学习"报成"伪标签训练有效"。
修法：新增 `_chat()`（`apply_chat_template(add_generation_prompt=True)`），推理与训练同渲染；协议参数未动。
新增两道防线：`invalid_base_arm`（基座可解析率 <0.5 则不得 positive）与 `n_ctx_truncated` / `sensitivity_untruncated`
（`MAX_LEN 3072` tokens 远短于标注路径的 `label.doc_text_chars = 20000` 字符；两臂同截断，delta 不受影响，但**绝对 F1 不得与 E1 的 0.7825 并列**）。重跑 04:17:16Z 开窗。

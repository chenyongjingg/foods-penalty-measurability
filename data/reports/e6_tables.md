# E6 确定性描述表（Results 1）

- 生成时刻：2026-11-05T03:54:28Z
- 语料：875 篇，sha `a1deda2c57ccf5ee…`
- 法规映射表版本：v2；食品词典版本：v1
- 规则可判定比例：0.6903

## 1 违规类型分布（确定性，规则引擎）

| 类别 | 篇数 | 占比 |
|---|---:|---:|
| FALSE_LABELING | 375 | 0.4286 |
| UNRESOLVED | 271 | 0.3097 |
| PROCEDURAL_NONCOMPLIANCE | 66 | 0.0754 |
| TRADEMARK_INFRINGEMENT | 57 | 0.0651 |
| FALSE_ADVERTISING | 38 | 0.0434 |
| FORGED_INSPECTION_REPORT | 33 | 0.0377 |
| UNLICENSED_OPERATION | 26 | 0.0297 |
| PRODUCT_QUALITY | 5 | 0.0057 |
| FAKE_CERTIFICATION | 4 | 0.0046 |

### 粗粒度（负对照未过底线时，Results 1 报这一张）

| 粗类 | 篇数 | 占比 |
|---|---:|---:|
| DATA_FALSIFICATION | 412 | 0.4709 |
| UNDETERMINED | 271 | 0.3097 |
| MARKET_ORDER | 100 | 0.1143 |
| PROCEDURAL | 66 | 0.0754 |
| UNLICENSED | 26 | 0.0297 |

## 2 判定依据分布

| basis | 篇数 |
|---|---:|
| penalty_statute | 322 |
| statute+fact | 160 |
| none | 100 |
| ambiguous_statute | 96 |
| ambiguous_facts | 75 |
| cited_statute | 61 |
| fact_only | 61 |

## 3 年度趋势（篇数）

| 年 | 篇数 |
|---|---:|
| 2023 | 6 |
| 2024 | 94 |
| 2025 | 167 |
| 2026 | 608 |

## 4 食品类别（主类）

| 类别 | 篇数 | 占比 |
|---|---:|---:|
| UNMATCHED | 272 | 0.3109 |
| FOOD_ADDITIVE | 85 | 0.0971 |
| PREPACKAGED_FOOD | 74 | 0.0846 |
| MEAT_PRODUCT | 66 | 0.0754 |
| ALCOHOL | 63 | 0.0720 |
| GRAIN_BAKERY | 61 | 0.0697 |
| CONDIMENT | 44 | 0.0503 |
| EDIBLE_AGRICULTURAL | 42 | 0.0480 |
| BEVERAGE | 36 | 0.0411 |
| DAIRY | 28 | 0.0320 |
| OIL | 28 | 0.0320 |
| HEALTH_FOOD | 22 | 0.0251 |
| FROZEN | 18 | 0.0206 |
| CATERING_RAW_MATERIAL | 17 | 0.0194 |
| TEA | 12 | 0.0137 |
| INFANT_FOOD | 7 | 0.0080 |

## 5 地域（按发文机关）

| 层级 | 篇数 |
|---|---:|
| county | 578 |
| city | 251 |
| province_named | 35 |
| other | 11 |

### 市级 top 15

| 市 | 篇数 |
|---|---:|
| unresolved | 614 |
| 晋江市 | 11 |
| 南安市 | 8 |
| 广汉市 | 8 |
| 鄂州市 | 8 |
| 巢湖市 | 7 |
| 射洪市 | 6 |
| 广德市 | 6 |
| 仙桃市 | 5 |
| 南昌市 | 5 |
| 安庆市 | 5 |
| 莆田市 | 5 |
| 赣州市 | 5 |
| 黄石市 | 5 |
| 太仓市 | 4 |

## 6 处罚力度（罚款，元）

- 有罚款金额的文书：565/875
- 中位数 5000.0；p25 1700.0；p75 15000.0；p90 55000.0；最大 805231.0

## 7 负对照（规则 vs 双通道 LLM）

- 样本：50/50（seed 20261104）
- 规则 vs 通道 A：0.28
- 规则 vs 通道 B：0.28
- 主判据（两者均值）：0.28 → **below_floor**
- 通道 A vs B：0.74
- 事后诊断（非判据，D-79）：规则可判定率 0.64；在可判定子集上 vs A 0.4375、vs B 0.4375

粒度判定：**coarse**

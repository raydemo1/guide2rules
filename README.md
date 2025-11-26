# guide2rules

通过大模型（GLM）将“数据分类分级指南”自动转化为可执行的业务规则（business‑rules），并生成可审计的证据与规范化的数据项。项目采用分层管线：先抽取领域分类骨架，再对每条细粒度路径批量枚举最小数据项，随后做术语归一与规则融合，最终产出可在运行时加载的规则集，并对表格数据进行自动分类与分级。

核心目标

- 将不同领域的指南结构化为统一的层级分类骨架与术语表
- 为每条路径抽取最小数据项及路径级证据，保证可追溯
- 归一化同义项与口径，合并静态抽取与动态规则，生成规则集并进行去重与冲突消解
- 在运行时加载规则，对字段进行分类分级并输出审计

整体流程

1. 读指南：把 PDF/Word 读成“段落/标题/表格”的结构化片段
2. 搭骨架：先从文本或表格里提炼领域的分类树和术语表
3. 找路径：把分类树按层级拆成很多“level1/level2/…/levelN”的路径（每条路径代表一个最细分类）
4. 抽最小项：针对每条路径，到上下文片段中找“最小数据项”（如 身份证号、路线编号等），并给出证据与匹配关键词/正则
5. 统一口径：用术语表把同义词合成标准名称（如“行政区划代码”与“区划代码”统一）
6. 生成规则：把所有最小项与动态 Excel 规则合并、去重、冲突消解，生成分类与分级两套可执行规则
7. 运行时分类分级：读取 Excel 数据，套用规则，自动写出“分类路径/分级/规则 ID/审计”四列

分层管线（实现细节）

Layer 1 ｜知识层（骨架与术语）

- 输入：guide/<domain>/\*.{pdf,docx,doc}
- 关键步骤：
  - 统一读取：doc/docx 先转 PDF（src/convert_to_pdf.py:4‑33,35‑56）；PDF 解析用 pdfplumber（src/pdf_plumber_text.py:128‑198），一次性抽出三类片段：title、paragraph、table
  - 表格增强：对表格做“向下填充 + 简单几何识别”以还原合并单元格（src/pdf_plumber_text.py:91‑111），并按首列聚组（src/pdf_plumber_text.py:113‑126）
  - 优先表格直解析：若表格像“字段定义表/主数据表”，直接构造分类树与路径的最小项（src/layer1_table_parser.py:87‑173,176‑257）
  - 回退 LLM：如表格不足以还原骨架，则拼接标题/段落文本，喂给 GLM 产 taxonomy/glossary（src/layer1_reader.py:23‑92），并对返回结构做校验修复（src/layer1_reader.py:95‑127）
  - 构造 seeds：沿分类树叶子生成路径数组与叶子 items（src/layer1_reader.py:129‑166）
- 输出：
  - artifacts/<domain>/<doc>.taxonomy.json（分类树，可能为空 levels_definition）
  - artifacts/<domain>/<doc>.glossary.json（术语与同义词）
  - artifacts/<domain>/<doc>.taxonomy_seeds.json（paths 与可能的叶子 items）
  - artifacts/<domain>/<doc>.fragments.json（结构化片段：标题/段落/表格）
  - 若表格直解析：artifacts/<domain>/<doc>.items.pre_extracted.json 与 <doc>.tables.json
- 主要代码：
  - src/layer1_reader.py（主流程：main 在 src/layer1_reader.py:168‑317）
  - src/pdf_plumber_text.py（PDF 结构化片段）
  - src/layer1_table_parser.py（表格直解析分类树与预抽取 items）

Layer 1.5 ｜域内目录合并（跨文档）

- 作用：当同一领域有多份指南时，合并它们的分类树为“域内目录”，并生成对应 seeds，方便后续批量抽取
- 步骤：
  - 扫描 artifacts/<domain> 下所有 \*.taxonomy.json 并载入（src/layer1_5_catalog.py:6‑13）
  - 将多棵树按“名称/层级”归并为一棵大树（src/layer1_5_catalog.py:47‑73,81‑93）
  - 从合并树提炼路径与叶子 items，写出 seeds（src/layer1_5_catalog.py:95‑128）
- 输出：
  - artifacts/<domain>/taxonomy.merged.json
  - artifacts/<domain>/taxonomy_seeds.merged.json
- 入口：src/layer1_5_catalog.py:131‑147

Layer 2 ｜抽取器（路径级证据 + 最小项枚举，并行）

- 输入：taxonomy_seeds.json 或 taxonomy_seeds.merged.json；对应的 fragments.json
- 核心：
  - 可变层级路径：path 是数组 [seg1,seg2,…]，深度按原文；不强行补齐（src/layer2_extractor.py:176‑185）
  - 分组并行：按前 N 层分桶，再按 batch 切片，并发调用 GLM（src/layer2_extractor.py:144‑156,358‑385）
  - 片段筛选：为每组/路径挑相关片段，评分来源于“路径词 + 通用关键词 + 域关键词”（src/layer2_extractor.py:92‑114,395‑418），关键词来源可配置（config/layer2_keywords.json）
  - 严格 JSON：统一 system 提示，入参含 {domain,seeds,fragments}，返回 extraction 列表，项结构固定（src/layer2_extractor.py:176‑205,212‑217,159‑174）
  - 预抽取增强：若 Layer 1 已从表格提到叶子 items，则直接让 LLM“补分级与匹配”，跳过证据检索（src/layer2_extractor.py:307‑324,260‑275）
- 输出：artifacts/<domain>/<base>.extraction.detailed.json
- 入口：src/layer2_extractor.py:420‑466；按域遍历，可用命令行指定域

Layer 2.5 ｜数据项归一化（同义统一 + 扁平化）

- 输入：_.extraction.detailed.json 与对应 _.glossary.json
- 处理：
  - 从术语表构造“synonym→canonical”映射（src/layer2_5_normalize_items.py:6‑35）
  - 将 extraction.items 扁平化为记录：每条包含 path、item{name,canonical,patterns}、level、conditions/exceptions、共享 citation（src/layer2_5_normalize_items.py:37‑80）
- 输出：artifacts/<domain>/<base>.items.normalized.json
- 入口：src/layer2_5_normalize_items.py:83‑130

Layer 3 ｜规则生成（分类 + 分级，两阶段执行）

- 数据来源：
  - 静态抽取：把 Layer 2 的 extraction 逐项转行，字段包含 FieldName/Category/Level/PatternKeywords/PatternRegex/Citation/Source（src/layer3_business_rules_builder.py:228‑252）
  - 动态规则：读取 excels/<domain> 下的 .csv/.xlsx（简化版占位，后续可替换为 pandas/openpyxl）（src/layer3_business_rules_builder.py:254‑273）
- 冲突消解：按 FieldName|Category 合并，较小 Priority 优先，同级合并关键词/正则与条件/例外（src/layer3_business_rules_builder.py:34‑88）
- 生成两类规则：
  - 分类规则：根据 FieldName 包含的关键词，设置 category_path 与分类规则 ID（src/layer3_business_rules_builder.py:91‑131）
  - 分级规则：同时命中“字段名关键词”与“值文本正则”，设置分级与审计（src/layer3_business_rules_builder.py:133‑181）
- 输出：
  - rules/<domain>/categorization_rules.json
  - rules/<domain>/classification_rules.json
  - rules/<domain>/export_rule_data.json（用于前端构建规则 UI 的变量/动作定义）
- 入口：src/layer3_business_rules_builder.py:213‑294

Layer 4 ｜运行时分类与分级（Excel 批处理）

- 功能：把一份包含“字段名/分类路径（可空）/字段样本”的 Excel，跑过分类与分级规则，输出四列结果
- 列识别：自动匹配列名，优先中文表头；兼容多种变体（src/layer4_classifier.py:36‑51）
- 两阶段执行：
  - 阶段 1（分类）：根据字段名关键词设置 category_path（src/rules/actions.py:33‑36）；可选“命中即停”
  - 阶段 2（分级）：匹配字段名关键词 + 值文本正则，写入 result_level、result_rule_id，并追加审计（src/rules/actions.py:9‑26,27‑31）
- 输出：在 outputs/<domain>/ 下生成同名 .classified.xlsx，附加列：分类路径/分级/规则 ID/审计（src/layer4_classifier.py:93‑160,161‑169）
- 命令：
  - 单文件：python src/layer4_classifier.py <domain> --input <xlsx> [--category "默认分类路径"] [--stop-first true] [--sheet Sheet1]
  - 目录批量（测试用）：python src/layer4_classifier.py <domain>

LLM 客户端与示例提示

- 客户端：ZhipuAI SDK（GLM 4.6），带并发控制与重试退避（src/llm_client.py:8‑10,11‑42）
- 示例提示：
  - Layer 1 示例 taxonomy/glossary（src/prompt_examples.py:1‑163）
  - Layer 2 示例 extraction（src/prompt_examples.py:165‑280）

依赖与配置

- 第三方库：pdfplumber、zhipuai、openpyxl、tqdm、business‑rules
- 关键配置文件（可选）：
  - config/domains.json（文件名到领域的映射；环境变量 DOMAINS_CONFIG 可重写，src/domains.py:8‑36,39‑48）
  - config/layer2_keywords.json（通用/域内关键词；环境变量 L2_KEYWORDS_CONFIG 可重写，src/layer2_extractor.py:11‑56,58）
  - config/layer2_params.json（并发/批量/片段限制；环境变量 L2_PARAMS_CONFIG 可重写，src/layer2_extractor.py:61‑87）
  - config/layer2_grouping.json（路径分桶深度与 token 深度；环境变量 L2_GROUPING_CONFIG 可重写，src/layer2_extractor.py:116‑131）
- LLM 环境变量：
  - GLM_API_KEY 或 ZHIPUAI_API_KEY（必需）
  - GLM_MODEL（默认 glm‑4.6）
  - LLM_CONCURRENCY（并发信号量，默认 2）
  - LLM_RETRY / LLM_BACKOFF_SEC（重试次数与退避基线）

运行流程（建议顺序）

1. 准备指南：把对应领域的指南放到 guide/<domain>/ 下（支持 pdf/docx/doc）
2. 运行 Layer 1：python src/layer1_reader.py
3. 可选 Layer 1.5（跨文档目录聚合）：python src/layer1_5_catalog.py
4. 运行 Layer 2：python src/layer2_extractor.py [<domain>]
5. 运行 Layer 2.5：python src/layer2_5_normalize_items.py
6. 运行 Layer 3：python src/layer3_business_rules_builder.py
7. 运行 Layer 4（可选，对 Excel 样本做分类分级）：python src/layer4_classifier.py <domain> --input <xlsx>

产物目录（更新版）

- 骨架与术语：artifacts/<domain>/<doc>.taxonomy.json、artifacts/<domain>/<doc>.glossary.json
- 路径 seeds 与片段：artifacts/<domain>/<doc>.taxonomy_seeds.json、artifacts/<domain>/<doc>.fragments.json
- 域内合并：artifacts/<domain>/taxonomy.merged.json、artifacts/<domain>/taxonomy_seeds.merged.json
- 抽取明细：artifacts/<domain>/<base>.extraction.detailed.json
- 归一化项：artifacts/<domain>/<base>.items.normalized.json
- 规则文件：rules/<domain>/categorization_rules.json、rules/<domain>/classification_rules.json、rules/<domain>/export_rule_data.json
- 分类分级输出：outputs/<domain>/<file>.classified.xlsx

设计亮点（为什么这样做）

- 以“路径”为最小上下文单位：大模型抽取时只看相关片段，降低幻觉并提升可追溯性
- 两阶段规则：先把“归类”做稳，再在分类上下文里做“分级”，易审计与调参
- 术语归一：把“字段名口径”提前统一，后续规则更稳定
- 表格直解析优先：节省 token 与成本；必要时才回退 LLM

后续路线

- Layer 1 目录词表可配置；域关键词自动选择
- Layer 2 分组级缓存与失败重试，提升稳定性与速度
- Layer 3 支持 xlsx 决策表生成与更完善的动态规则管道
- 评估与审计脚本：覆盖率/证据存在率/冲突一致率，以及报告导出
- 前端上传指南与规则设计 UI；支持 agent 联网获取领域指南

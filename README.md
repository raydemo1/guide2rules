# guide2rules

通过大模型（GLM）将“数据分类分级指南”自动转化为可执行的业务规则（business-rules），并生成可审计的证据与规范化的数据项。项目采用分层管线实现：先抽取领域分类骨架，再对每条细粒度路径批量枚举最小数据项，随后归一化并与人工/Excel 动态规则合并，最终产出可在运行时加载的规则集。

**核心目标**

- 将不同领域的指南（PDF）结构化为统一的四级分类骨架与术语表。
- 为每条 `level4` 路径抽取最小数据项及路径级证据，保证可追溯。
- 归一化同义项与口径，合并静态抽取与动态规则，生成 business-rules 规则集并进行去重与冲突消解。
- 为后续规则引擎运行时加载与 REST 接口集成打基础。

**端到端思路**

- 先由大模型抽取“分类骨架”（Layer 1），再对骨架的每个 `level4` 路径批量枚举最小数据项（Layer 2），并保留路径级证据。
- 使用术语表归一化同义项（Layer 2.5），将抽取得到的最小项转为标准字段名与口径。
- 将抽取结果与人工/Excel 动态规则合并（Layer 3），生成 OpenRules 决策表并进行去重与冲突消解。
- 后续在运行时加载决策表，对数据字段进行分类分级并输出标签与审计。

## 分层管线

### Layer 1 ｜知识层（骨架）

- 输入：`guide/<domain>/*.pdf`
- 动作：
  - 读取 PDF 文本为逐页 `pages`（`src/pdf_text.py` 的 `read_pdf_text` 使用 `pypdf`）
  - 拼接全文并构造消息：`system` 说明仅返回严格 JSON；`examples` 来自 `get_layer1_examples(domain)`；`user` 包含来源与全文（`src/layer1_reader.py:41-60`）
  - 调用 GLM 并截取首尾大括号确保合法 JSON（`src/layer1_reader.py:63-71`）；补充 `taxonomy.domain/source`
  - 遍历 `taxonomy.tree` 生成四级路径 `paths` 与 `levels`（`build_seeds`，`src/layer1_reader.py:83-121`）
  - 将每页文本生成 `fragments=[{page,text}]`（`build_fragments`，`src/layer1_reader.py:123-127`）
  - 写出产物：`taxonomy.json`、`glossary.json`、`taxonomy_seeds.json`、`fragments.json`
- 产物：
  - `artifacts/<domain>/<doc>.taxonomy.json`
  - `artifacts/<domain>/<doc>.glossary.json`
  - `artifacts/<domain>/<doc>.taxonomy_seeds.json`（含 `paths`：`level1..level4`）
  - `artifacts/<domain>/<doc>.fragments.json`
- 代码：`src/layer1_reader.py`

### Layer 1.5 ｜域内目录

- 动作：
  - 扫描域目录下的 `*.taxonomy.json` 并加载（`load_taxonomies`，`src/layer1_5_catalog.py:6-21`）
  - 遍历各 `tree`，在 `level3->children->level4->items` 处聚合候选项并按四级路径去重（`build_catalog`，`src/layer1_5_catalog.py:24-78`）
  - 生成 `paths=[{level1..level4, items[]}]`
- 产物：`artifacts/<domain>/catalog.json`
- 代码：`src/layer1_5_catalog.py`

### Layer 2 ｜抽取器（路径级证据 + 最小项枚举，批量并行）

- 动作：
  - 读取 `taxonomy_seeds.json` 与 `fragments.json`（`run_for_artifact_dir`，`src/layer2_extractor.py:151-161`）
  - 若存在 `paths`：
    - 以 `(level1,level2)` 分组并按 `L2_BATCH_SIZE` 切片（`group_paths`，`src/layer2_extractor.py:48-59`）
    - 为每组选择相关片段：四级路径词 + 通用关键词 + 域关键词评分，去重并截断至 `L2_PER_PATH_FRAG_LIMIT`/`L2_GROUP_FRAG_LIMIT`（`filter_fragments_for_group/path`，`src/layer2_extractor.py:62-84,218-243`）
    - 以 `ThreadPoolExecutor(max_workers=L2_WORKERS)` 并行调用大模型（`extract_structured`），每条 `level4` 路径返回一次 `citation` 与 `items[]`（`src/layer2_extractor.py:94-143,175-205`）
    - 汇总所有分组的 `extraction` 写出 `*.extraction.detailed.json`
  - 若无 `paths`：走旧模式返回分类级结果，写出 `*.extraction.json`（`src/layer2_extractor.py:207-215`）
  - 大模型入参：`{domain, seeds, fragments}`；出参：`{domain, source, extraction}`，其中 `extraction` 的每项结构为 `{path, citation, items[]}`（`src/layer2_extractor.py:100-111,119-141`）
- 并行参数：`L2_WORKERS`、`L2_BATCH_SIZE`、`L2_PER_PATH_FRAG_LIMIT`、`L2_GROUP_FRAG_LIMIT`
- 产物：`artifacts/<domain>/<doc>.extraction.detailed.json`
- 代码：`src/layer2_extractor.py`

### Layer 2.5 ｜数据项归一化

- 动作：
  - 加载术语表并构造 `synonym->canonical` 映射（`load_glossary`，`src/layer2_5_normalize_items.py:6-34`）
  - 将 `extraction.items[]` 扁平化为记录，并为每个 `name` 添加 `canonical`；保留共享 `citation` 与 `path`（`normalize_items`，`src/layer2_5_normalize_items.py:37-78`）
  - 写出 `*.items.normalized.json`
- 产物：`artifacts/<domain>/<doc>.items.normalized.json`
- 代码：`src/layer2_5_normalize_items.py`

### Layer 3 ｜ business-rules 规则生成与运行（合并/去重/冲突消解）

- 动作：
  - 读取静态抽取文件与动态规则（CSV/XLSX），统一为规则行并进行冲突消解：键 `FieldName|Category`、等级优先（S4>S3>S2>S1）、同级取较小 `Priority`，合并 `Condition/Exception/Citation/Source` 与 `PatternKeywords/PatternRegex`
  - 将规则行转换为 business-rules JSON：
    - 条件：`field_name equal_to`、`category_path equal_to`，并以 `value_text contains/matches_regex` 组合关键词与正则
    - 动作：`set_classification(level, rule_id)`、`append_audit(citation, source)`
  - 导出变量/动作定义供前端构建规则 UI（`export_rule_data`）
- 产物：
  - `rules/<domain>/rules.json`
  - `rules/<domain>/export_rule_data.json`
- 代码：`src/layer3_business_rules_builder.py`、`src/rules/variables.py`、`src/rules/actions.py`

### LLM 客户端与示例提示

- 客户端：ZhipuAI SDK（GLM 4.6）`src/llm_client.py`
- 示例提示：`src/prompt_examples.py`（为金融域提供骨架与“最小 item”示例）

### 读取与转换依赖

- PDF 读取：`pdfplumber`
- Word 转换：优先 `docx2pdf`；Windows 平台可回退 `pywin32`（Word COM）
- 不使用 `unoconv`

## 运行流程

1. 准备指南文件：将对应领域的指南放入 `guide/<domain>/`（支持 `*.pdf`、`*.docx`、`*.doc`）
2. 配置动态规则：将 Excel 规则放入 `excels/<domain>/`
3. 按顺序运行以下脚本：
   - `python src/layer1_reader.py`
   - `python src/layer1_5_catalog.py`（可选，根据是否需要跨文档目录聚合）
   - `python src/layer2_extractor.py`
   - `python src/layer2_5_normalize_items.py`
   - `python src/layer3_business_rules_builder.py`

## 产物目录

- 骨架与术语：`artifacts/<domain>/<doc>.taxonomy.json`、`artifacts/<domain>/<doc>.glossary.json`
- 路径 seeds 与片段：`artifacts/<domain>/<doc>.taxonomy_seeds.json`、`artifacts/<domain>/<doc>.fragments.json`
- 抽取明细：`artifacts/<domain>/<doc>.extraction.detailed.json`
- 归一化项：`artifacts/<domain>/<doc>.items.normalized.json`
- business-rules 规则：`rules/<domain>/rules.json`、`rules/<domain>/export_rule_data.json`

## 后续需要实现的功能

- 补充多领域（交通、政务、气象等）的 Layer 2 最小 item 示例（如：车牌号/司机编号/户籍号/税号）。
- Layer 1 增加“目录页提取与标题行过滤”的可配置词表，并按域自动选择关键词。
- Layer 2 引入分组级缓存与失败重试，提升大文档稳定性与速度。
- Layer 3 支持 `.xlsx` 决策表生成与运行时样例。
- 评估与审计：

  - 覆盖率、证据存在率、冲突一致率的统计脚本；
  - 报告导出（`classification_results.json`、`audit_report.json`）。

- 用 langchain 进行拼接，或者 langgraph 进行额外的专家审议，更加严格和标准
- 加入前端设计，可以上传指南或者 agent 联网搜索指定领域，动态规则设计完成。前端在第一步上传指南时，需要选择领域以及输入标准号
- 在模版中间卡一下，可以生成一个模版供参考。如果完全考虑不到的内容是否可以只到四级分类。因为目的是对字段进行分类
- l3 需要补充规则的具体内容，正则和关键词

- 测试交科院给的数据，并进行效果评估，生成评估报告

## 目录索引（关键文件）

- `src/layer1_reader.py`｜知识层骨架与 seeds/fragments 生成
- `src/layer1_5_catalog.py`｜域内目录聚合
- `src/layer2_extractor.py`｜分组并行抽取，路径级证据 + 多 item
- `src/layer2_5_normalize_items.py`｜同义归一与扁平化
- `src/layer3_business_rules_builder.py`｜合并生成 business-rules 规则集
- `src/rules/variables.py`｜规则变量定义
- `src/rules/actions.py`｜规则动作定义
- `src/llm_client.py`｜ GLM 客户端
- `src/prompt_examples.py`｜少样本示例

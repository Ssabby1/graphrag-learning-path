# GraphRAG Learning Path 改造路线图与 TODO

> 文档用途：这是当前仓库下一阶段改造的唯一执行入口。新的开发线程应先完整阅读本文件，再检查仓库与运行环境，从“阶段 0”开始按顺序实施。除非新的实验证据推翻现有判断，不要重新扩张产品范围。
>
> 当前状态：阶段 0 至阶段 5 已完成；当前 baseline 已冻结，图推理、跨语言检索、关系级 Evidence Pack、Citation Validator 和结构化双语 Answer Generator 已接入 GraphRAG 主链；Reranker 默认关闭；下一轮进入阶段 6 的报告、前端与公开展示收尾。
>
> 最后确认日期：2026-08-31。

---

## 1. 最终项目定位

将项目从“具备 GraphRAG 接口形式的毕业设计原型”升级为：

> **面向课程学习规划场景的、先修约束与关系证据驱动、可量化评测的多语言 GraphRAG 系统。**

项目以中文完整图谱作为主要真实数据集，同时支持中文、英文和中英混合查询；公开展示采用英文优先、中文保留的方式，以适配新加坡及 APAC 的 AI 开发 / AI PM 求职场景。

项目必须围绕一条克制、可验证的主线展开：

```text
自然语言问题
  -> Target Resolver（识别目标知识点）
  -> Path Planner（只依据先修图决定必要学习路径）
  -> Evidence Retriever（为已确定路径选择关系证据）
  -> Evidence Pack（结构化、可追溯的证据集合）
  -> Answer Generator（只基于 Evidence Pack，并按用户问题语言生成解释）
  -> Citation Validator（确定性校验引用）
  -> 前端展示路径与“为什么推荐”
```

核心原则：

1. **图决定路径，向量不改变路径。**
2. **检索负责找证据，生成负责组织表达。**
3. **LLM 不能引用 Evidence Pack 之外的事实。**
4. **每个模块单独评测，不能用一个综合分数掩盖局部问题。**
5. **先建立 baseline，再替换实现；不预设 Hybrid 或 Reranker 一定更好。**
6. **公开展示必须可复现，同时不公开受版权约束的完整教材数据。**
7. **核心架构必须与语言解耦；中文是主要真实数据，不是系统边界。**
8. **GitHub 与演示采用英文优先，但不得通过翻译包装掩盖真实能力。**

---

## 2. 为什么采用这条路线

该项目用于支持 AI 开发 / AI PM 求职。现有简历已经通过其他经历证明了以下能力：

- LLM Workflow、Prompt Engineering、Structured Output、Guardrails；
- FastAPI、SQLite、Docker、数据处理与异常治理；
- 多阶段 Agent、Evidence Pack、测试、部署和产品闭环。

因此，本项目不应重复建设复杂账号、SQLite 状态系统或 Multi-Agent。它最需要补强、也最能形成能力互补的是：

- 多语言及跨语言语义检索；
- 图约束推理；
- 关系级 grounding；
- citation 校验；
- RAG/GraphRAG 分模块评测；
- 对实验结果保持诚实的工程决策。

完成后，三个主要经历应形成如下分工：

| 经历 | 核心能力证据 |
| --- | --- |
| GEO 内容智能体 | Agent Workflow、Prompt、Guardrails |
| AI 效能分析看板 | 后端、数据、SQLite、Docker、权限与部署 |
| GraphRAG Learning Path | Retrieval、Graph Reasoning、Grounding、Evaluation |

### 2.1 新加坡 / APAC 展示策略

本项目不需要把完整 190 个中文知识点全部人工翻译，也不需要更换业务主题。需要完成的是：

- `README.md` 使用英文，`README.zh-CN.md` 保留中文入口；
- 架构图、核心评测表和演示视频使用英文；
- 公开合成 sample 提供中英双语名称、描述和 aliases；
- 检索层默认评估多语言 embedding，不写死纯中文模型；
- 评测集同时包含中文、英文和中英混合查询；
- 回答语言默认跟随用户问题语言，并允许显式覆盖；
- API 字段和内部 schema 保持英文命名；
- 完整本地图谱可以继续以中文为主，不为展示目的批量生成未经审核的英文翻译。

目标演示案例：

```text
English query:
What should I learn before studying Karnaugh maps?

Resolved Chinese concept:
卡诺图构成 (G000079)

Answer:
An English explanation with relationship-level citations.
```

---

## 3. 已核验的仓库与数据事实

### 3.1 完整图谱

- 去重知识点：190 个；
- 全部关系：827 条；
- `PREREQUISITE_OF`：409 条；
- `RELATED_TO`：299 条；
- `CONTAINS`：119 条；
- 409 条先修关系均有非空 `evidence_text`、`source_images`、`confidence_max`；
- 全部 827 条关系的上述三个字段均非空；
- 当前先修图无重复先修边、无自环，是 DAG；
- 最长先修路径为 16 条边，即 17 个知识点；
- 48 个目标节点的最大祖先深度超过 8。

### 3.2 当前实现的关键问题

1. `backend/app/repositories/graph_repository.py` 将先修查询限制为 8 层，会静默遗漏深层必要先修节点。
2. 当前 tokenizer 仅匹配英文字母、数字和下划线，中文查询可能形成空向量；它也无法完成英文问题到中文概念的跨语言语义匹配。
3. 当前所谓 vector backend 是 hashing fallback，不是真实的多语言语义 embedding。
4. 当前 reranker 是 token overlap，不是真正的语义 reranker。
5. `build_grounded_answer()` 主要格式化 Prompt 文本，没有真正生成自然中文 grounded answer。
6. 当前 `evidence` 主要是节点 ID，而不是可以证明关系的结构化证据。
7. 190 个知识点中只有 23 个有 description，只有 7 个有 alias；仅对名称和 description 建索引，语料过于稀疏。
8. 当前概念语料接口只返回 ID、名称、description，没有章节、邻居和关系证据。
9. 当前图谱校验脚本默认只检查不超过 12 层的环，报告本身不能证明任意长度无环。
10. 公开仓库只提交了 3 个示例节点；完整数据和 Neo4j 运行目录被忽略，一键初始化在全新 clone 中不自洽。
11. 当前 Windows 虚拟环境和依赖目录不能在 macOS 直接复用，需要重建跨平台开发环境。

### 3.3 数据质量边界

字段完整不等于证据内容充分：

- 409 条先修关系只有约 369 个不同的 `evidence_text`；
- 大量证据是“前置知识点/后置知识点”模板；
- 部分证据只是抽取标签或结构描述，不能支撑丰富的教学结论；
- `confidence_max` 表示抽取过程的置信度，不是教学正确率。

因此，任何 API、前端或 README 都必须使用以下命名：

```json
{
  "confidence": 0.92,
  "confidence_type": "extraction_confidence",
  "verification_status": "unreviewed"
}
```

只有经过记录的人工检查后，才能将 `verification_status` 改为 `human_verified`。

---

## 4. 本轮范围与明确非目标

### 4.1 本轮必须完成

- [ ] 分层评测集与当前 baseline；
- [ ] 完整先修祖先闭包与长链处理；
- [ ] 完整 DAG、深度与截断校验；
- [ ] 概念级和关系级两套检索语料；
- [ ] 多语言 embedding、跨语言检索、持久化缓存和检索模式切换；
- [ ] 可插拔 Reranker 与消融实验；
- [ ] Neo4j 关系属性查询；
- [ ] 关系级 Evidence Pack；
- [ ] Citation Integrity 确定性校验；
- [ ] 真正的 AnswerGenerator、按问题语言回答及中英文 fallback；
- [ ] 四类分模块评测报告；
- [ ] 前端“为什么推荐这一步”；
- [ ] 10–20 节点公开合成样例；
- [ ] 跨平台运行说明、README 与集成测试。
- [ ] 英文优先展示、双语公开样例和跨语言评测。

### 4.2 本轮不做

- 学习状态持久化；
- 复杂用户、登录、权限系统；
- Multi-Agent；
- 多课程、多学科；
- 题库、社区、排行榜、评论；
- 语音交互或移动端 App；
- 复杂推荐算法集合；
- 为了“智能”增加额外 LLM 调用；
- 整体重构前端；
- 上传完整教材原文、原始图片或其他受版权约束的数据。

如果新需求落入非目标范围，应先完成本路线图的 P0，再单独评估，不得穿插实现。

---

## 5. 目标模块边界

### 5.1 Target Resolver

职责：把用户问题解析为一个目标知识点，必要时返回候选列表或拒绝识别。

输入：

```json
{
  "question": "想学卡诺图，应该先掌握什么？",
  "top_k": 5,
  "response_language": "auto"
}
```

输出建议：

```json
{
  "target_concept_id": "G000079",
  "candidates": [
    {
      "concept_id": "G000079",
      "score": 0.91,
      "rank": 1,
      "source": "vector"
    }
  ],
  "resolution_source": "vector",
  "query_language": "zh",
  "rejected": false,
  "rejection_reason": null
}
```

约束：

- 只识别目标，不生成学习路径；
- 必须支持无匹配拒绝；
- 必须支持英文问题识别中文概念，以及中英混合别名；
- `response_language=auto` 时识别问题主要语言，显式传入 `zh` 或 `en` 时服从调用方；
- 阈值必须来自开发集或明确的规则，不能随意拍值；
- 相同模型、语料和输入的结果必须稳定。

### 5.2 Path Planner

职责：只依据 `PREREQUISITE_OF` 图、目标和已掌握知识点生成学习路径。

输入：

```json
{
  "target_concept_id": "G000079",
  "mastered_concepts": []
}
```

输出建议：

```json
{
  "target_concept_id": "G000079",
  "path": ["G000063", "G000069", "G000079"],
  "graph_nodes": ["G000063", "G000069", "G000079"],
  "graph_edges": [
    ["G000063", "G000069"],
    ["G000069", "G000079"]
  ],
  "meta": {
    "has_cycle": false,
    "truncated": false,
    "max_depth": 2,
    "node_count": 3,
    "edge_count": 2,
    "planner_strategy": "cached_graph_ancestor_closure"
  }
}
```

约束：

- Vector Retrieval 不得向 `path` 增加节点；
- 必须覆盖完整祖先闭包，除非明确返回 `truncated=true`；
- 必须过滤已掌握节点；
- 必须保持未掌握节点之间的拓扑约束；
- 目标节点若未掌握，必须位于路径末尾；
- 不能仅提高深度常量来掩盖截断问题。

### 5.3 Evidence Retriever

职责：在已确定路径及其子图中，为解释选择最相关的关系证据。

默认候选范围：

```text
Path Planner 输出的 PREREQUISITE_OF 边
```

可选补充范围：

```text
与路径节点直接相连的 RELATED_TO 边
```

但补充关系必须标记为 `supplementary_context`，不能支撑“必要先修”结论，也不能改变路径。

输出的每条 evidence 必须有稳定 ID。建议使用：

```text
prereq:{from_concept_id}:{to_concept_id}
related:{from_concept_id}:{to_concept_id}
```

### 5.4 Evidence Pack

目标结构：

```json
{
  "evidence_pack_version": "1.0",
  "target_concept_id": "G000079",
  "path": ["G000063", "G000069", "G000079"],
  "items": [
    {
      "evidence_id": "prereq:G000069:G000079",
      "evidence_type": "required_prerequisite",
      "from_concept": {
        "id": "G000069",
        "name": "逻辑函数表达式"
      },
      "relation": "PREREQUISITE_OF",
      "to_concept": {
        "id": "G000079",
        "name": "卡诺图构成"
      },
      "reason": "后置知识点：卡诺图构成；前置知识点：逻辑函数表达式",
      "source_chapters": ["第三章"],
      "source_images": ["img_03_01"],
      "confidence": 0.92,
      "confidence_type": "extraction_confidence",
      "verification_status": "unreviewed",
      "retrieval": {
        "graph_score": 1.0,
        "vector_score": 0.81,
        "rrf_score": 0.0325,
        "rerank_score": 0.88,
        "source": "graph+vector"
      }
    }
  ]
}
```

注意：

- `source_chapters` 需要定义清晰的推导规则，例如取关系两端概念章节的去重并集；
- `source_images` 是数据来源标识，不得在公开仓库中自动发布原始教材图片；
- `verification_status` 需要独立审核记录支撑；
- Evidence Pack 应由确定性代码构建，不交给 LLM 自由生成。

### 5.5 Answer Generator

输入只能包括：

- 用户问题；
- Path Planner 输出；
- 路径节点元数据；
- Evidence Pack。

建议结构化输出：

```json
{
  "answer": "建议先学习逻辑函数表达式，再学习卡诺图构成。逻辑函数表达式是理解卡诺图表示方法的必要基础。",
  "cited_evidence_ids": [
    "prereq:G000069:G000079"
  ],
  "answer_source": "llm",
  "answer_language": "zh"
}
```

确定性后处理必须保证：

- 引用 ID 全部存在于当前 Evidence Pack；
- 去除或拒绝未知引用；
- 结构化输出无法解析时使用 fallback；
- LLM 超时、网络错误、鉴权错误时使用 fallback；
- fallback 根据 `response_language` 返回正常中文或英文答案，不返回 Prompt 模板；
- `answer_source` 明确为 `llm` 或 `fallback`；
- `answer_language` 明确记录最终输出语言；
- API 元数据中记录使用的生成模型或 fallback 策略。

### 5.6 Citation Validator

需要区分三个指标：

1. **Citation Integrity**：引用的 evidence ID 是否存在，可由代码保证；
2. **Citation Correctness**：引用的证据是否支持对应结论，需要人工或 Judge；
3. **Citation Completeness**：关键事实性结论是否都有引用，需要句子级检查。

硬性验收：

- Citation Integrity = 100%；
- Invalid Evidence ID = 0。

Citation Correctness 和 Completeness 必须报告实际测量值，不能预设 100%。

---

## 6. 建议的代码结构

在尽量保持现有结构的前提下，建议新增或调整为：

```text
backend/app/
  core/
    config.py
  repositories/
    graph_repository.py
  graph/
    prerequisite_index.py
    graph_snapshot.py
  retrieval/
    base.py
    corpus_builder.py
    embedding_backend.py
    embedding_cache.py
    concept_retriever.py
    evidence_retriever.py
    fusion.py
    reranker.py
  evidence/
    models.py
    pack_builder.py
    citation_validator.py
  services/
    target_resolver.py
    path_service.py
    answer_generator.py
    graphrag_service.py
  schemas/
    evidence.py
    evaluation.py
evals/
  datasets/
    target_resolver.jsonl
    path_planner.jsonl
    evidence_retriever.jsonl
    answer_generator.jsonl
  annotations/
    evidence_reviews.jsonl
  runner.py
  metrics.py
  report.py
  reports/
tests/
  ...
```

这只是建议边界，不要求为了目录美观进行大规模搬迁。优先保持小步、可测试、可回滚。

---

## 7. 图推理实现要求

### 7.1 推荐实现

不要在每次请求中枚举所有变长路径。建议：

1. `GraphRepository` 查询全部 Concept 和直接 `PREREQUISITE_OF` 边；
2. 构建进程内 `PrerequisiteGraphIndex`；
3. 保存正向和反向邻接表；
4. 对目标沿反向邻接表计算完整祖先闭包；
5. 在诱导子图上进行确定性拓扑排序；
6. 用节点 ID 作为相同优先级下的稳定 tie-breaker；
7. 通过数据版本、更新时间或内容哈希刷新缓存。

当前规模下，加载 190 个节点和 409 条边成本很低，优先保证正确性和可解释性。

### 7.2 安全限制

配置中应提供：

- `GRAPH_MAX_NODES`；
- `GRAPH_MAX_EDGES`；
- `GRAPH_QUERY_TIMEOUT_SECONDS`；
- 可选 `GRAPH_CACHE_TTL_SECONDS`。

限制触发时必须返回明确错误或 `truncated=true`，不得静默输出不完整路径。

### 7.3 完整校验

图谱验证脚本需要新增：

- 全量 DAG 检查；
- 完整最长路径长度；
- 深度分布；
- 深度超过配置阈值的目标数；
- 全部目标祖先闭包统计；
- 数据集哈希；
- 关系证据字段完整率；
- 人工确认关系数量及比例。

### 7.4 路径语义待明确项

已掌握节点的处理需要固定规则并写入测试：

- 如果用户掌握中间节点 `M`，是否默认认为 `M` 的所有祖先也已具备？
- 当前实现只移除 `M`，但可能仍保留 `M` 上游的 `A`；这未必符合用户语义。

推荐产品规则：

> 默认将已掌握节点及其全部祖先视为可跳过，但保留在 graph context 中用于解释；如未来需要复习模式，再通过明确参数改变规则。

实施前应把该规则写进测试和 API 文档，避免隐式行为。

---

## 8. 检索语料与索引设计

### 8.1 概念级语料

每个 Concept 生成一个确定性的 `retrieval_text`：

```text
知识点：{name}
编号：{concept_id}
别名：{aliases}
英文名称：{name_en}
英文别名：{aliases_en}
章节：{source_chapters}
难度：{difficulty}
描述：{description}
英文描述：{description_en}
直接前置知识：{predecessor_names}
直接后继知识：{successor_names}
```

注意：

- 字段顺序固定；
- 列表排序固定；
- 缺失字段使用空值或统一占位，不能随机变化；
- 完整中文数据没有英文元数据时允许为空，跨语言能力主要由多语言 embedding 和人工确认的 aliases 提供；
- 公开 sample 必须提供经人工确认的中英双语字段；
- 不要把过多包含其他概念名称的原始关系文本直接堆入 Target Resolver，避免目标歧义；
- 对高频、易混淆且缺 description 的概念优先人工补充简短定义；
- 人工补充内容应与原始抽取数据分开保存并标记来源。

### 8.2 关系级语料

每条关系生成一个 evidence document：

```text
证据编号：{evidence_id}
前置知识点：{from_name} ({from_id})
关系：{relation_type}
后置知识点：{to_name} ({to_id})
证据文本：{evidence_text}
章节：{source_chapters}
抽取置信度：{confidence_max}
```

### 8.3 Embedding

实现 `EmbeddingBackend` 接口，至少包含：

```python
class EmbeddingBackend(Protocol):
    @property
    def model_id(self) -> str: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
```

默认候选应优先选择支持中文、英文和跨语言检索的 SentenceTransformers 兼容模型，例如 `intfloat/multilingual-e5-base`。可以将中文专用模型作为对照组，但不能未经评测写死为默认方案。模型必须可通过环境变量替换，正式采用前要核对许可证、下载体积、查询前缀要求、运行内存和目标平台性能。

模型选择至少比较：

- 中文查询 -> 中文概念；
- 英文查询 -> 英文/双语公开概念；
- 英文查询 -> 中文概念；
- 中英混合查询 -> 中文概念；
- 索引构建时间、单次查询延迟和内存占用。

严禁测试时自动联网下载模型。单元测试使用 deterministic fake embedding；真实模型测试标记为 integration/slow。

### 8.4 持久化缓存

索引缓存 key 至少包含：

- corpus 内容哈希；
- embedding model ID；
- embedding dimension；
- normalization 设置；
- 索引 schema version。

缓存文件可以使用 NumPy `.npz` 和 JSON metadata。190 个概念规模无需为了简历引入复杂向量数据库。

缓存验收：

- 第一次启动构建索引；
- 后续启动命中缓存；
- 语料或模型变化自动重建；
- 缓存损坏自动重建并记录日志；
- 相同输入排序稳定。

### 8.5 检索模式

统一支持：

```text
graph_only
vector_only
hybrid_rrf
hybrid_rrf_rerank
```

每个 hit 建议返回：

```json
{
  "id": "...",
  "rank": 1,
  "source": "graph+vector",
  "graph_rank": 1,
  "vector_rank": 3,
  "graph_score": 1.0,
  "vector_score": 0.82,
  "rrf_score": 0.0323,
  "rerank_score": 0.91
}
```

不存在的阶段分数使用 `null`，不要伪造为 0。

### 8.6 Reranker

- 提供 `Reranker` 接口；
- 初始可评估支持中文、英文和跨语言文本对的 cross-encoder；
- 对比无 rerank 与有 rerank；
- 记录延迟与质量变化；
- 指标没有稳定提升时默认关闭；
- README 如实写结论，不为保留简历关键词强行启用。

---

## 9. 四模块评测设计

评测集建议围绕至少 30 个核心业务场景构建，但应派生为四个独立任务文件，并额外加入 Target Resolver 负样本。Target Resolver 首版建议包含约 20 条中文问题和至少 10 条英文或中英混合问题；如果负样本导致总数超过 30，应保留额外样本，不必为了固定总数删除覆盖场景。

### 9.1 A. Target Resolver

数据：

```json
{
  "case_id": "target-001",
  "question": "想学卡诺图，应该先掌握什么？",
  "acceptable_target_ids": ["G000079"],
  "should_reject": false,
  "query_language": "zh",
  "tags": ["short_query", "alias"]
}
```

需要覆盖：

- 精确名称；
- 别名；
- 自然语言描述；
- 英文查询识别中文概念；
- 中英混合查询；
- 英文缩写或国际通用别名；
- 易混淆知识点；
- 错别字或口语表达；
- 无关问题；
- 信息不足；
- 多目标歧义。

指标：

- Top-1 Accuracy；
- MRR@K；
- Top-K Recall；
- 应拒绝样本的拒绝准确率；
- 不应拒绝样本的误拒绝率；
- 按 `zh`、`en`、`mixed` 分组的 Top-1 Accuracy 和 Recall@K；
- Cross-Lingual Target Accuracy。

### 9.2 B. Path Planner

数据：

```json
{
  "case_id": "path-001",
  "target_concept_id": "G000079",
  "mastered_concepts": [],
  "human_required_prerequisite_ids": ["..."],
  "human_forbidden_ids": [],
  "review_status": "human_verified"
}
```

分两层评估：

#### 工程正确性

使用独立 CSV 图算法作为 oracle，验证：

- Structural Closure Recall；
- Topological Violation Rate；
- Mastered Filter Correctness；
- Graph Truncation Rate；
- 路径长度与最大深度；
- 所有 190 个目标的祖先闭包一致性。

#### 教学正确性

使用人工审核 gold set，验证：

- Human-Reviewed Prerequisite Precision；
- Human-Reviewed Prerequisite Recall；
- 不必要节点比例；
- 遗漏必要节点比例。

不能只把当前图谱输出复制成 gold，否则只能验证实现是否复现当前图谱，不能证明教学合理性。

### 9.3 C. Evidence Retriever

数据：

```json
{
  "case_id": "evidence-001",
  "question": "为什么学习卡诺图前要掌握逻辑函数表达式？",
  "target_concept_id": "G000079",
  "path": ["G000069", "G000079"],
  "relevant_evidence_ids": ["prereq:G000069:G000079"],
  "graded_relevance": {
    "prereq:G000069:G000079": 3
  }
}
```

指标：

- Evidence Recall@K；
- MRR；
- nDCG@K；
- Citation Integrity；
- 人工 Citation Correctness。

### 9.4 D. Answer Generator

每条评测记录应固定问题、路径和 Evidence Pack，避免把上游检索错误混入生成器单测。

Answer Generator 必须分别包含中文回答、英文回答和自动语言选择案例；相同 Evidence Pack 下的不同语言回答应引用同一组有效 evidence ID。

指标：

- 结构化输出成功率；
- fallback 成功率；
- Invalid Evidence ID 数量；
- Citation Integrity；
- Citation Correctness；
- Citation Completeness；
- Unsupported Claim Rate；
- 先修关系方向表达正确率；
- 人工 Faithfulness 评分；
- Answer Language Match Rate；
- P50/P95 延迟。

### 9.5 报告要求

每次评测同时生成：

- 机器可读 JSON；
- 人类可读 Markdown；
- 运行配置快照；
- 数据集版本/哈希；
- 模型 ID；
- Git commit；
- 单例失败明细；
- P50/P95 延迟；
- 指标的分子和分母。

示例：

```text
Target Top-1 Accuracy: 26/30 = 86.7%
Citation Correctness: 71/80 = 88.8%
```

约 30 条案例适合作品集的方向性验证，不得声称具有普遍统计显著性。

---

## 10. 证据人工审核

至少人工审核 30–50 条核心 `PREREQUISITE_OF` 关系，优先选择：

- 公开演示会使用的目标；
- 最长链上的关系；
- 高入度/高出度节点相关关系；
- 卡诺图、逻辑函数、编码器、时序逻辑等代表性知识点；
- 置信度较低或证据文本较短的关系；
- 容易混淆关系方向的案例。

审核记录建议：

```json
{
  "evidence_id": "prereq:G000069:G000079",
  "decision": "verified",
  "reviewer": "project_author",
  "reviewed_at": "2026-08-30",
  "dataset_hash": "...",
  "notes": "关系方向和教材章节一致"
}
```

可选 decision：

```text
verified
rejected
needs_revision
uncertain
```

不要直接修改原始抽取置信度来表达人工判断；抽取置信度和人工审核状态必须分开。

---

## 11. API 契约调整

### 11.1 `/planner/interpret`

增加候选列表、分数、拒绝状态、查询语言和 resolver 元数据。保持旧字段兼容，前端迁移完成后再决定是否移除旧字段。

### 11.2 `/path/recommend`

保留：

- `target_concept_id`；
- `path`；
- `graph_nodes`；
- `graph_edges`。

增加：

- 完整 meta；
- 结构化 path steps；
- 截断状态；
- 最大深度；
- 每步的直接支撑关系 ID。

### 11.3 `/graphrag/query`

建议目标返回：

```json
{
  "answer": "建议先学习……",
  "answer_source": "llm",
  "answer_language": "zh",
  "path": ["G000063", "G000069", "G000079"],
  "path_steps": [],
  "evidence_pack": {
    "evidence_pack_version": "1.0",
    "items": []
  },
  "citations": [
    {
      "evidence_id": "prereq:G000069:G000079",
      "kind": "relationship"
    }
  ],
  "meta": {
    "answer_source": "llm",
    "retrieval_strategy": "graph_scoped_hybrid_rrf",
    "embedding_model": "...",
    "query_language": "zh",
    "reranker": "none",
    "has_cycle": false,
    "truncated": false,
    "latency_ms": {
      "planner": 0,
      "retrieval": 0,
      "generation": 0,
      "total": 0
    }
  }
}
```

兼容策略：

- 首轮尽量新增字段而不立即删除旧字段；
- 为 schema 增加版本；
- 请求允许使用 `response_language=auto|zh|en`；
- 前后端同步迁移；
- 契约变化必须有 API 测试。

---

## 12. 前端最小改造

只增加与可信解释直接相关的体验：

- 路径节点可点击；
- 展开“为什么推荐这一步”；
- 显示直接支撑的下一知识点；
- 显示必要先修/补充背景；
- 显示章节、证据文本、抽取置信度和人工审核状态；
- 显示回答引用的 evidence；
- fallback 时明确但不过度强调“本地模板回答”；
- UI 文案、问题输入和最终回答支持中英文；
- 自动模式下回答语言跟随问题，用户也可以显式切换；
- 截断或图异常时显示警告，不能假装路径完整。

不进行整体 UI 重构。可以将当前大组件中与 evidence 展示直接相关的部分拆成小组件，但不要在本轮做无关的设计系统建设。

---

## 13. 公开样例与可复现性

### 13.1 Sample dataset

公开样例扩展为 10–20 个纯合成节点，必须能演示：

- 单链先修；
- 分支；
- 汇合；
- 多级长链；
- 已掌握节点过滤；
- 目标不存在；
- 至少一条 `RELATED_TO`；
- 较低抽取置信度；
- 每条关系都有证据；
- 中英双语 `name`、`description` 和 aliases；
- 至少一个中文自然语言查询；
- 至少一个英文查询识别中文/双语概念的跨语言案例；
- 至少一个中英混合查询。

公开 sample 推荐字段：

```json
{
  "concept_id": "sample_kmap",
  "name_zh": "卡诺图",
  "name_en": "Karnaugh Map",
  "aliases": ["K-map", "卡诺图"],
  "description_zh": "使用图形排列表示和化简逻辑函数的方法",
  "description_en": "A graphical method for representing and simplifying Boolean functions"
}
```

### 13.2 数据选择

启动和导入逻辑：

1. 用户显式指定 CSV 时使用指定文件；
2. 本地完整数据存在时允许使用完整数据；
3. 完整数据不存在时自动使用 `data/seed/`；
4. 日志明确显示当前是 `sample` 还是 `full_local`；
5. API overview 和评测报告记录 dataset profile。

### 13.3 运行方式

目标至少支持：

- Windows PowerShell；
- macOS/Linux shell；
- 推荐增加 Docker Compose 管理 Neo4j、后端和前端。

不要提交跨平台不可复用的 `.venv`、`node_modules` 或 Neo4j 本地数据库状态。

---

## 14. 测试清单

### 14.1 图推理

- [ ] 超过 8 层的长链完整返回；
- [ ] 16 边/17 节点链完整返回；
- [ ] 分支与汇合拓扑正确；
- [ ] 所有祖先均被覆盖；
- [ ] 环路被完整检测；
- [ ] 自环被检测；
- [ ] 目标不存在；
- [ ] 孤立目标；
- [ ] 目标已掌握；
- [ ] 中间节点已掌握；
- [ ] 已掌握节点祖先跳过规则；
- [ ] 安全限制触发时显式 truncated/error；
- [ ] 输出排序稳定。

### 14.2 检索

- [ ] 中文、英文和中英混合查询向量非零；
- [ ] 英文查询可以识别人工标注的中文目标概念；
- [ ] 多语言模型与中文专用模型至少完成一次对照评测；
- [ ] alias 能召回正确概念；
- [ ] 章节和邻居信息进入 concept corpus；
- [ ] relation evidence 使用独立索引；
- [ ] 相同输入排序稳定；
- [ ] 缓存命中；
- [ ] 语料变化触发缓存失效；
- [ ] 缓存损坏可恢复；
- [ ] graph/vector/RRF 分数正确保留；
- [ ] RRF 单元测试；
- [ ] reranker 开关有效；
- [ ] 模型不可用时行为明确。

### 14.3 Evidence 与 citation

- [ ] 每条 evidence ID 稳定且唯一；
- [ ] Evidence Pack 只包含允许范围内的关系；
- [ ] 必要先修与补充背景明确区分；
- [ ] confidence 类型正确；
- [ ] verification 状态来自审核记录；
- [ ] citation 必须引用存在的 evidence；
- [ ] 未知 evidence ID 被拒绝或移除；
- [ ] citation 与 evidence 一一对应；
- [ ] 公开模式不泄漏受限原始图片。

### 14.4 Answer Generator

- [ ] 正常结构化 LLM 输出；
- [ ] LLM 超时；
- [ ] 鉴权失败；
- [ ] 无效 JSON；
- [ ] 未知 citation；
- [ ] 空回答；
- [ ] Evidence Pack 为空；
- [ ] fallback 返回正常中文或英文；
- [ ] 自动回答语言与问题语言一致；
- [ ] 显式 `response_language` 覆盖有效；
- [ ] `answer_source` 正确；
- [ ] 不再返回 `Question / Path / Evidence / Answer:` Prompt 文本。

### 14.5 API 与集成

- [ ] `/planner/interpret` 契约；
- [ ] `/path/recommend` 完整路径契约；
- [ ] `/graphrag/query` 完整链路；
- [ ] citation referential integrity；
- [ ] Neo4j 不可用时 503；
- [ ] Neo4j 查询异常；
- [ ] embedding/reranker 不可用时降级；
- [ ] 前端可以展示 evidence；
- [ ] sample dataset 端到端演示；
- [ ] CI 不依赖真实 LLM API Key；
- [ ] CI 不自动下载大型模型。

---

## 15. 分阶段实施与提交顺序

### 阶段 0：环境与基线冻结

- [x] 检查 Git 状态，保留用户已有改动；
- [x] 阅读 README、运行说明、现有测试和本文件；
- [x] 为当前平台重建干净 Python/Node 环境；
- [x] 运行后端测试和前端构建；
- [x] 保存当前 API 样例输出；
- [x] 建立四类 eval 文件格式；
- [x] 写入首批人工案例，包括中文、英文、中英混合和拒绝样本；
- [x] 运行当前 hashing/token-overlap baseline；
- [x] 保存 baseline JSON/Markdown，并按语言分组，不覆盖后续报告。

完成标准：当前实现的真实能力已经被可重复记录。

### 阶段 1：图推理正确性

- [x] 新增完整图 snapshot/index；
- [x] 移除静默深度 8 截断；
- [x] 实现完整祖先闭包；
- [x] 明确 mastered ancestor 规则；
- [x] 增加安全限制和 meta；
- [x] 扩展完整 DAG 校验；
- [x] 增加长链及全目标结构测试；
- [x] 输出深度分布和数据哈希。

完成标准：对全部 190 个目标，应用输出与独立 CSV oracle 的祖先闭包一致；结构性先修约束违反率为 0；任何限制触发均不静默。

### 阶段 2：检索语料与多语言检索

- [x] 扩展 Neo4j 概念元数据查询；
- [x] 构建 concept corpus；
- [x] 构建 edge evidence corpus；
- [x] 定义 embedding 接口；
- [x] 实现真实多语言 embedding；
- [x] 实现英文查询到中文概念的跨语言检索；
- [x] 实现持久化缓存；
- [x] 实现四种检索模式；
- [x] 返回各阶段排名和分数；
- [x] 添加中文、英文、中英混合检索与稳定性测试；
- [x] 运行 Target Resolver baseline 对比。

完成标准：中文、英文和中英混合查询非空、排序稳定、缓存有效；英文问题能够识别标注的中文概念；每个检索结果的来源和分数可追溯。

### 阶段 3：Reranker 消融

- [x] 定义 Reranker 接口；
- [x] 接入多语言 cross-encoder 候选实现；
- [x] 记录质量和延迟；
- [x] 对比启用/禁用；
- [x] 根据真实结果决定默认值；
- [x] 在报告中记录结论。

完成标准：默认策略由评测结果决定，而不是由简历关键词决定。

### 阶段 4：关系证据与 Citation

- [x] Neo4j 返回关系属性；
- [x] 定义 evidence schema；
- [x] 构建稳定 evidence ID；
- [x] 构建 Evidence Pack；
- [x] 区分必要先修与补充背景；
- [x] 导入人工审核状态；
- [x] 实现 Citation Validator；
- [x] 添加 evidence/citation 测试；
- [x] 运行 Evidence Retriever 评测。

完成标准：Citation Integrity 为 100%，Invalid Evidence ID 为 0，所有证据均可追溯到图关系。

### 阶段 5：Answer Generator

- [x] 定义 AnswerGenerator 接口；
- [x] 实现受 Evidence Pack 限制的 Prompt；
- [x] 使用结构化输出；
- [x] 实现引用后校验；
- [x] 实现中英文确定性 fallback；
- [x] 实现自动回答语言选择和显式覆盖；
- [x] 记录 answer source 与延迟；
- [x] 添加超时、格式错误和幻觉引用测试；
- [x] 运行 Answer Generator 评测。

完成标准：前端收到与问题语言一致的正常回答；LLM 不可用时中英文均可解释；未知 citation 不会进入最终响应。

### 阶段 6：报告、前端与公开展示

- [ ] 生成四模块独立报告；
- [ ] 生成功能消融表；
- [ ] 前端增加“为什么推荐”；
- [ ] 扩展公开 sample dataset；
- [ ] 修复跨平台 setup；
- [ ] 清理矛盾或过期校验报告；
- [ ] 更新 README 求职展示结构；
- [ ] 将 `README.md` 调整为英文默认入口，并保留中文 README；
- [ ] 增加英文架构图和英文演示 GIF；
- [ ] 展示至少一个英文查询到中文概念的跨语言案例；
- [ ] 完成端到端测试。

完成标准：新用户可以用公开样例运行完整链路，README 中每一项技术声明都有代码、测试或实验报告支撑。

---

## 16. README 最终结构

完成核心改造后，README 调整为：

1. `README.md` 使用英文，首屏提供中文 README 链接；
2. 一句话英文项目定义；
3. 英文演示 GIF 或截图，优先展示跨语言查询；
4. 用户问题与产品价值；
5. 系统架构；
6. GraphRAG 核心链路；
7. Graph/Vector/LLM 职责边界；
8. 多语言和跨语言检索设计；
9. Evidence Pack 与 citation 示例；
10. 完整图谱规模与数据质量边界；
11. 四模块评测、语言分组指标和消融结果；
12. 关键技术决策，包括 embedding/reranker 是否默认开启；
13. Sample 与完整本地数据说明；
14. 本地运行与测试。

推荐项目描述：

> A multilingual, prerequisite-constrained GraphRAG system that combines complete prerequisite-graph reasoning, cross-lingual retrieval, relationship-level Evidence Packs, deterministic citation validation, and modular evaluation to produce explainable and traceable learning paths.

不要继续把“本科毕业设计”作为 README 第一卖点；可在项目背景中说明。不要把项目描述成“一个中文数字逻辑学习网站”，应强调语言无关架构、中文真实数据验证和 APAC 多语言适用性。

---

## 17. 最终 Definition of Done

只有同时满足以下条件，本轮改造才算完成：

### 正确性

- [ ] 全部目标祖先闭包与独立 oracle 一致；
- [ ] 结构性先修约束违反率为 0；
- [ ] 不存在静默截断；
- [ ] 完整 DAG 校验通过；
- [ ] mastered 语义已明确并测试。

### 检索

- [ ] 中文、英文和中英混合查询不会产生空向量；
- [ ] 至少一个英文查询可以正确识别中文概念；
- [ ] 多语言模型选择有真实对照结果；
- [ ] 概念与关系使用独立语料和索引；
- [ ] 相同输入排序稳定；
- [ ] 检索来源和阶段分数完整；
- [ ] Reranker 默认状态由消融决定。

### Grounding

- [ ] evidence 为关系级结构；
- [ ] Evidence Pack 可追溯；
- [ ] Citation Integrity = 100%；
- [ ] Invalid Evidence ID = 0；
- [ ] Citation Correctness、Completeness 和 Unsupported Claim Rate 报告实测值；
- [ ] 抽取置信度不被误称为教学正确率。

### 生成

- [ ] 返回与用户问题语言一致的自然中文或英文回答；
- [ ] 不再返回 Prompt 模板；
- [ ] LLM 结构化输出有效；
- [ ] LLM 异常时 fallback 可用；
- [ ] `answer_source` 明确；
- [ ] `answer_language` 明确；
- [ ] 回答只能引用当前 Evidence Pack。

### 评测与工程

- [ ] 四模块分别评测；
- [ ] JSON 和 Markdown 报告可重复生成；
- [ ] 报告记录配置、数据哈希、模型和 Git commit；
- [ ] 后端测试、前端构建和端到端样例通过；
- [ ] 公开 sample 可以完整演示；
- [ ] 公开 sample 包含人工确认的中英双语元数据；
- [ ] 英文 README、架构图和跨语言演示可供非中文招聘者独立理解；
- [ ] 全新 clone 有自洽运行路径；
- [ ] README 的声明均有可核验证据。

---

## 18. 新线程开始工作时的操作约定

新的实现线程应按以下方式开始：

1. 完整阅读本文件；
2. 查看 `git status`，不要覆盖用户已有改动；
3. 检查仓库是否存在 `AGENTS.md` 或新的项目规则；
4. 阅读相关源码、测试和数据 schema；
5. 只处理当前阶段，不跨阶段大规模修改；
6. 修改公共 schema 前先补或更新契约测试；
7. 每个阶段完成后运行对应测试和评测；
8. 报告真实结果，不预设 Hybrid/Rerank/LLM 必然提升；
9. 不在测试中依赖真实 API Key 或自动下载大型模型；
10. 不提交完整私有数据、教材原图、`.env`、`.venv`、`node_modules` 或本地 Neo4j 状态。

可以直接给新线程以下任务：

> 请完整阅读仓库根目录 `IMPLEMENTATION_ROADMAP.md`，检查当前 Git 状态和运行环境，然后严格从“阶段 0：环境与基线冻结”开始实施。先建立四模块评测数据契约，并用中文、英文、中英混合及拒绝样本记录当前 baseline；不要提前扩展非目标功能。项目采用中文完整图谱作为主要真实数据，但检索与生成架构必须支持多语言，GitHub 展示采用英文优先。每完成一个阶段，运行对应测试与评测，并更新本文件中的 TODO 状态和实测结果。

---

## 19. 实施记录

后续每个阶段完成后，在此追加简要记录，不要删除历史：

| 日期 | 阶段 | Git commit | 主要结果 | 测试/评测 | 未解决问题 |
| --- | --- | --- | --- | --- | --- |
| 2026-08-30 | 方案冻结 | - | 确定先修约束、关系证据驱动、可评测的多语言 GraphRAG 路线；中文完整图谱作为主要真实数据，英文优先展示 | 尚未实施 | 从阶段 0 开始 |
| 2026-08-30 | 阶段 0 | `dfe94a5`（工作区实现，尚未提交） | 建立四类 JSONL 评测契约；加入 36 条 Target Resolver（含 20 中文、7 英文、3 混合正例与 6 拒绝样本）、10 条 Path、6 条 Evidence、6 条 Answer 案例；新增离线 baseline runner、配置/哈希快照、失败明细和 API 样例 | 后端 `32 passed`；前端 Vite 构建成功；Planner Top-1 `20/30=66.7%`，英文 `0/7=0%`；hashing Vector Top-1 `1/30=3.3%`、Recall@5 `2/30=6.7%`；完整闭包召回 `1503/1514=99.3%`，11/190 个目标发生静默遗漏；关系 Evidence Recall `0/6`；结构化 Answer `0/6`，Prompt 泄漏 `6/6` | Python 3.14 触发依赖弃用警告；npm 报告 9 个依赖漏洞、前端 bundle >500 kB；这些不阻塞阶段 0，后续单独处理。下一轮严格从阶段 1 开始 |
| 2026-08-30 | 阶段 1 | `dfe94a5`（工作区实现，尚未提交） | 新增不可变 `GraphSnapshot`、进程内 TTL 缓存和双向邻接索引；Neo4j 只读取全量直接边，不再枚举固定深度路径；确定性完整祖先闭包与拓扑排序；mastered 节点及其祖先从学习路径跳过但保留图上下文；安全限制显式返回 `truncated`、省略计数、深度、策略和数据哈希；校验脚本支持 Neo4j 与跨平台 CSV 离线模式 | 后端 `43 passed`（含 17 节点长链、分支汇合、环、自环、截断、缓存、mastered 语义、190/190 全目标独立 CSV oracle）；Structural Closure Recall `1514/1514=100%`；拓扑约束违反率 `0`；完整 DAG PASS；最长路径 16 边；48 个目标深度超过 8；前端构建成功 | Python 3.14 仍有依赖弃用警告；完整数据未公开时全量 oracle 测试会明确 skip，公开 seed 流程继续可用。下一轮从阶段 2 开始 |
| 2026-08-30 | 阶段 2 | `bf1e63a` | 构建确定性的概念与关系证据双语料；Neo4j 查询补齐双语元数据、章节、邻居与关系属性；加入可插拔 embedding、E5 query/passage 前缀、原子 JSON 缓存、损坏恢复、四种检索模式、逐阶段排名/分数；新增少量可审计的项目人工双语 aliases；Target Resolver 使用最低分与 Top-1 margin 拒绝无关问题 | macOS ARM64 Python 3.13 + `sentence-transformers 6.0.0` 成功加载 `intfloat/multilingual-e5-small`（384 维）；后端 `54 passed`；完整本地语料 190 个概念、708 条可检索关系；Target Top-1 `30/30=100%`、Recall@5 `30/30=100%`、拒绝 `6/6=100%`、跨语言 Top-1 `10/10=100%`；概念缓存 1 次 rebuild/35 次 hit，关系缓存 rebuild 后命中；P50/P95 `22.106/24.123 ms` | 结果来自 36 条方向性小数据集，部分演示目标使用同仓库人工 aliases，不声称统计显著性；真实模型首次运行需约 470 MB 下载，CI 单测仍使用 fake backend 且禁止隐式下载。下一轮从阶段 3 开始 |
| 2026-08-31 | 阶段 3 | `6e9c61e` | 实现可插拔 CrossEncoder、离线加载、显式 token fallback、稳定 tie-break 与降级元数据；以固定 E5 Top-8 候选对比 none、token-overlap 和 `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`；按预先声明的质量、语言分组与 P95 延迟门槛决定默认策略 | 后端 `58 passed`；无重排 Top-1 `26/30=86.7%`、MRR@5 `0.925`；token Top-1 `25/30=83.3%`、MRR@5 `0.911`；CrossEncoder Top-1 `25/30=83.3%`、MRR@5 `0.897`，英文分组回退；CPU P50/P95 `54.7/110.0 ms`，MPS `31.3/137.0 ms`；CPU/MPS 排序一致 | CrossEncoder 质量门槛未通过，默认继续使用 `hybrid_rrf` 且不启用 reranker；MPS 在受限沙箱内不可见，宿主环境验证通过；小样本仅为方向性结论。下一轮从阶段 4 开始 |
| 2026-08-31 | 阶段 4 | `d3a821d` | 新增关系级 Evidence Pack 1.0、必要先修/补充背景类型、关系属性追踪、图范围 Evidence Retriever 与 Citation Validator；GraphRAG 引用由 concept ID 切换为稳定 relationship evidence ID；未知引用由确定性后处理拒绝；抽取置信度与人工审核状态保持分离 | 后端 `61 passed`；708 条关系语料全局 Vector Recall@5 `5/6=83.3%`、MRR@5 `0.708`、nDCG@5 `0.738`；Graph-scoped Recall/MRR/nDCG/Top-1 均 `6/6=100%`；Citation Integrity `6/6=100%`；Invalid Evidence ID `0`；热缓存全局 P50/P95 `57.6/58.3 ms`、图范围 `51.7/52.4 ms` | 仅 6 条人工标注方向性 fixture，不能代表总体 Citation Correctness；生产关系仍以 `verification_status` 独立标记，大部分为 `unreviewed`；自然语言 Answer Generator 留待阶段 5。下一轮从阶段 5 开始 |
| 2026-08-31 | 阶段 5 | `d3a821d`（阶段 4 检查点；阶段 5 工作区实现） | 新增结构化 AnswerGenerator 接口和 Evidence Pack 限定 Prompt；支持 OpenAI-compatible JSON 输出、生成后 Citation Validator、自动/显式中英文选择、确定性双语 fallback、生成来源/模型/延迟/完整率元数据；删除旧 PromptTemplate formatter 与未使用的 LangChain 依赖 | 后端 `68 passed`；离线 fallback 结构成功、语言匹配、Citation Integrity、必要引用完整率、关系方向表达均 `6/6=100%`，Prompt 泄漏 `0/6`；结构化 fake-LLM 契约 `6/6`；格式错误、超时、幻觉引用 guardrail `3/3`，最终 Invalid Evidence ID `0` | 本轮未调用外部 LLM，fake LLM 只验证结构契约，不能代表真实模型质量；Unsupported Claim Rate 与人工 Faithfulness 明确未测量。下一轮进入阶段 6 |

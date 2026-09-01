# GraphRAG 学习路径

[English README](README.md) · [阶段 6 评测汇总](evals/reports/stage6_summary.md) · [执行路线图](IMPLEMENTATION_ROADMAP.md)

这是一个面向课程学习规划的多语言 GraphRAG 系统：先用先修图谱决定完整学习路径，再在该路径范围内检索关系证据，最后生成只引用 Evidence Pack 的中英文回答，并对引用做确定性校验。

## 核心边界

- 图谱决定学习顺序，向量检索不能改变路径；
- Target Resolver 支持中文、英文和中英混合查询；
- 完整 Evidence Pack 覆盖路径中的全部关系，另从中选取有限证据交给 Answer Generator；
- Evidence Pack 使用稳定的关系级 ID，可追溯到证据文本；
- Answer Generator 默认跟随问题语言，也允许显式选择；
- 外部 LLM 不可用时使用确定性双语 fallback；
- 未知 citation 在 API 返回前会被移除。
- `ok`、`already_mastered`、`not_found`、`truncated`、`cycle` 状态会阻止异常路径生成普通回答。

## 公开样例

仓库提供 15 个合成双语知识点和 18 条人工整理的先修证据，可公开复现完整链路。完整本地图谱包含 190 个中文知识点和 409 条先修关系，但受源材料约束不随公开仓库分发。

```text
英文问题：What should I learn before studying Karnaugh maps?
识别目标：卡诺图构成 / Karnaugh Map Construction (c_006)
结果：英文学习路径解释 + 关系级引用
```

## macOS / Linux

需要 Python 3.11–3.13 和 Node.js 18+。公开 CSV 图谱模式不需要 Docker 或 Java。

```bash
./setup.sh
./start-dev.sh
```

使用 `./stop-dev.sh` 停止服务。

默认是完全离线的轻量演示，不安装或暗中下载模型，前端会明确显示“降级 Hashing”。如需真实多语言 E5 检索，运行 `./setup.sh --embeddings`；该显式选项会安装 `sentence-transformers` 并下载约 470 MB 模型。

## Windows PowerShell

```powershell
.\setup.ps1
.\start-dev.ps1
.\stop-dev.ps1
```

Windows 默认同样使用公开 CSV 样例，全新 clone 不再依赖未跟踪的 Neo4j 目录。使用 `.\setup.ps1 -Embeddings` 显式安装和下载 E5。

访问地址：前端 <http://127.0.0.1:5173>，API 文档 <http://127.0.0.1:8000/docs>。

## 验证

```bash
cd backend
.venv-unix/bin/python -m pytest
cd ../frontend
npm run build
```

四模块独立报告、限制说明和功能消融结果见 [阶段 6 评测汇总](evals/reports/stage6_summary.md)。

新增 GraphRAG 契约回归使用 42 节点、107 条路径关系验证：完整证据覆盖率 `100%`，仅选取 8 条证据进入回答上下文；目标不存在、已掌握、截断和环路状态均有独立门控。

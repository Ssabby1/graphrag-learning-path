# 基于知识图谱的个性化学习路径推荐系统

本仓库是一个可本地运行的毕业设计项目，主题为“基于知识图谱的个性化学习路径推荐系统”。系统围绕数字逻辑课程构建知识图谱，并结合先修依赖推理、路径排序、检索增强解释与前端可视化，支持从目标知识点到个性化学习路径的生成与展示。

## 快速运行

第一次使用请先安装 Python、Node.js 和 JDK。详细步骤见：

[项目运行说明.md](./项目运行说明.md)

初始化：

```powershell
.\setup.ps1
```

启动：

```powershell
.\start-dev.ps1
```

停止：

```powershell
.\stop-dev.ps1
```

启动后访问：

- 前端页面：http://127.0.0.1:5173
- 后端接口文档：http://127.0.0.1:8000/docs
- Neo4j 浏览器：http://127.0.0.1:7474

## 目录结构

- `backend/`：FastAPI 后端源码，包含图谱查询、路径推荐、GraphRAG 和解释服务。
- `frontend/`：Vue 3 前端源码，包含知识点选择、路径展示和问答交互界面。
- `neo4j/`：Neo4j Community 本地运行目录。
- `章节数据/`：课程知识点与关系抽取、整理、汇总后的数据。
- `scripts/`：Neo4j 数据导入、图谱校验等脚本。
- `docs/`：项目综述、系统架构、数据模型、接口与实验说明。
- `成果材料/`：论文、答辩 PPT、演示稿和关键图片等成果文件。

## 技术栈

- 前端：Vue 3、Vite、Axios、ECharts
- 后端：FastAPI、Uvicorn、NetworkX、LangChain Core
- 数据库：Neo4j Community
- 数据处理：Python CSV 脚本

## 常用命令

后端测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

前端构建：

```powershell
cd frontend
npm run build
```

重新导入图谱数据：

```powershell
$env:NEO4J_PASSWORD="kg_learning_path_2026"
.\backend\.venv\Scripts\python.exe scripts\import_data.py --clear-target
```

图谱质量校验：

```powershell
$env:NEO4J_PASSWORD="kg_learning_path_2026"
.\backend\.venv\Scripts\python.exe scripts\validate_graph.py --report backend\docs\graph_validation_report.md
```

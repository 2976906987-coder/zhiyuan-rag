# 知源：可追溯 RAG 智能知识库问答系统

Python + FastAPI + LLM API + RAG + Qdrant 向量数据库。面向技术文档，关注检索对比、有效引用、版本过滤与文档生命周期。

## 快速运行（Windows / PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start-demo.ps1
```

打开 http://127.0.0.1:8000 ，上传 samples 下的两个文档，然后提问“默认端口是什么？”。API 文档在 /docs。

离线演示使用确定性词项哈希向量和原文摘录，不调用 LLM，不具有真实语义模型能力。向量仍由真实 Qdrant 本地引擎持久化与检索。演示与真实 API 使用独立数据目录，不能混用索引。

## 接入真实 LLM / Embedding API

复制 .env.example 为 .env，在本地填写：

- MODEL_MODE=api
- LLM_BASE_URL、LLM_API_KEY、LLM_MODEL：兼容 /chat/completions 的模型服务
- EMBEDDING_BASE_URL、EMBEDDING_API_KEY、EMBEDDING_MODEL、EMBEDDING_DIM：兼容 /embeddings 的向量模型服务；维度必须与实际返回一致
- 可选 RERANK_BASE_URL、RERANK_API_KEY、RERANK_MODEL：兼容 /rerank，返回 results 数组，包含 index 与 relevance_score

在新终端运行 `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。密钥仅存 .env，不放前端或提交仓库。更换 Embedding 模型或维度时使用新 DATA_DIR 并重新入库。API 会把导入文本发往你配置的模型服务。

## 检索链路

1. 解析 UTF-8 TXT/Markdown、文字 PDF，保存页码，800 字符切块、150 字符重叠。
2. 批量 Embedding API → Qdrant；SQLite 维护文档状态、内容哈希、版本与分块原文。
3. 按版本和 ready 状态过滤 → 向量 Top20 + 中文字符/二元词 BM25 Top20 → RRF 融合 → 可选 Rerank API → TopK。
4. 证据门控 → LLM API 生成 → 校验引用编号 → 回答与来源。RRF 分数不是置信概率；当前拒答阈值为未校准启发式，需用真实语料调优。
5. 删除先标记不可见，再清理 Qdrant 与 SQLite；失败可重试。生成后再次核对文档是否仍可用，避免并发删除后返回旧引用。

引用校验仅检查编号是否有效、是否存在引用，不证明答案的每个事实均受原文支持。资料中的提示注入通过系统指令降低风险，尚无完整隔离与对抗评测。

## 接口

| 接口 | 用途 |
|---|---|
| GET /api/health | 运行模式与数据库类型 |
| GET /api/documents | 文档状态与分块数量 |
| POST /api/documents | multipart file + version，最大 10 MB |
| DELETE /api/documents/{id} | 删除原文分块及向量 |
| POST /api/search | question、mode、version、top_k |
| POST /api/chat | 回答、来源、耗时、token usage、trace_id |
| POST /api/chat/stream | SSE 输出生成中的 token，结束时返回引用校验后的完整结果；草稿明确标记待校验 |

同名同版本相同内容自动去重，不同内容返回冲突。版本更新通过新版本上传，查询时显式选择版本；不自动推断“最新版本”。当前不保留原始 PDF，仅保留页码和解析片段。多轮会话记忆、文档下载和 PDF 页面高亮尚未实现。

## 测试与评测

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 先启动应用并上传 samples 下的两个文档
.\.venv\Scripts\python.exe eval/run.py
# 配置重排模型后对比四组
.\.venv\Scripts\python.exe eval/run.py --rerank
```

测试使用嵌入式 Qdrant 和模拟模型响应，验证导入、去重、版本过滤、引用失败、删除、持久化与 API 合约。它不能代替真实供应商联调。

初始评测集只有 5 个自建样例问题，输出文档级 Recall@5、MRR@5 和平均检索延迟，不能作为简历质量提升数据。后续应扩展到 80–100 个标注问题，按文档/问题家族拆分调参与保留测试集，补充无答案、冲突、跨段落问题及人工依据评审。

## Docker

配置 .env 后运行 `docker compose up --build -d`。应用仅绑定本机 8002 端口，Qdrant 不对外暴露；数据使用命名卷持久化。Compose 路径需要 Docker Desktop / Linux 容器。Qdrant 本地模式默认无需 Docker，适合开发验收。已补齐数据库就绪等待、健康检查与独立验收脚本；当前机器缺少可用 Docker，实际容器构建和运行仍待验证，详见 [部署与可靠性说明](DEPLOYMENT.md)。

## MVP 边界与后续

单用户、本地受信环境、单进程运行（不要启用多个 uvicorn worker）。同步导入通过线程池执行；状态可查询，重启中断的导入会标为 failed。BM25 每次查询重建，适合小语料，不是高并发实现。追踪记录包含问题和片段，存本地 SQLite。没有认证、生产任务队列或租户隔离，不直接部署到公网。

下一阶段：真实模型联调、评测标注与消融实验、异步导入任务、章节切分、支持性校验、多轮会话、权限控制。简历应据实际实现与实测数据描述贡献，不声称生产规模或预设准确率。


## 真实文档评测（第二阶段）

新增固定 FastAPI 0.115.0 官方中文语料，16 篇文档，80 道初稿问题（64 道可回答、16 道资料外问题）。完整说明见 [eval/README.md](eval/README.md)，实测报告由 [eval/report.py](eval/report.py) 从原始结果生成。

```powershell
.\.venv\Scripts\python.exe eval/build_dataset.py
.\.venv\Scripts\python.exe eval/benchmark.py --split dev --answers 8 --output eval/results/dev.json
.\.venv\Scripts\python.exe eval/benchmark.py --split test --answers 8 --output eval/results/test.json
.\.venv\Scripts\python.exe eval/report.py
```

评测库独立于用户知识库；运行会调用真实 Embedding / Rerank / LLM 服务。数据集标签待人工复核，证据锚点指标不等于答案准确率。不要把初稿实验的数值声称为生产环境效果。

真实模式启动使用 `start-api.ps1`，端口 8001；演示模式仍使用 `start-demo.ps1`，端口 8000。修改 .env 后重启相应服务才能加载配置。

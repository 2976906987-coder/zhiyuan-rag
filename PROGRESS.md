# 项目进度（2026-10-18）

当前定位：可演示、具备对比实验的 RAG 求职项目。核心功能与部署验收已有结果，尚不等同于生产级系统。

| 模块 | 状态与证据 |
| --- | --- |
| Python / FastAPI / LLM API / Qdrant | 已实现；支持本地演示和真实模型 |
| 文档上传、去重、版本、删除、持久化 | 已实现，有系统测试 |
| 向量、BM25、混合检索、Rerank | 已实现，有四方案评测 |
| 流式回答、引用、拒答、Markdown | 已实现，有引用和渲染测试 |
| 超时、有限重试、上游错误脱敏、流式中断 | 已实现；最新完整回归 25 项通过（2026-10-18），含评测版本防混用测试 |
| Docker 演示模式 | 已有 passed 报告：data/docker-verification.json，5 项检查；本轮未重跑 |
| Docker 真实云模型 | 已有 passed 报告：data/docker-real-verification.json，7 项检查；本轮未重跑 |
| 评测 | 80 题、16 篇文档；新版锚点检查通过，dev/test 结果均匹配当前标签；本轮 test 128 次检索无错误，8 道回答抽查完成 |
| 自动回归 | 新增 GitHub Actions，运行 Python / Markdown / Compose 静态检查和离线 Docker 验收；已在 GitHub Actions 实测通过 |

本轮完整 Python 回归 25 项通过，Markdown 格式与安全检查、Compose 静态检查及锚点定位检查通过。此前审批额度阻塞已解除。测试仅有一条第三方 TestClient 弃用提示，不影响此次通过。本轮 GitHub Linux CI 已通过，包含离线 Docker 全链路验收；真实模型容器联调沿用此前记录。新版 test 首位证据命中率：向量 50%，重排 65.625%；检索中位延迟约 941 / 2134 ms。这是 32 道可回答题的锚点指标，不是答案准确率。

## 下一阶段优先级

1. GitHub 发布与 CI 已完成：https://github.com/2976906987-coder/zhiyuan-rag 。首次通过记录：https://github.com/2976906987-coder/zhiyuan-rag/actions/runs/39129690080 。
2. 新版 test 重测已完成；仍需独立人工语义复核。已有自动定位检查不能替代人工审核。
3. 已补充 docs/DEMO_AND_RESUME.md，包含演示脚本、简历草稿和面试讲解；实际截图、视频尚未录制。
4. 需要多人使用时再增加认证、知识库隔离、后台导入任务和并发压测；目前不宣称具备这些能力。

## 自动化范围

`.github/workflows/verify.yml` 在 push、pull request 或手动触发时运行。Docker 验收只使用演示模型和临时数据，不配置云模型密钥。真实云模型脚本仍由本地按需执行。CI 配置已推送，首次运行全部通过；Docker 验收 JSON 已作为工作流产物保存。

# 可靠性与 Docker 验证

## 当前状态

- 已实现模型连接与读取超时、有限退避重试、脱敏错误提示、流式中断检测和存储就绪检查。
- 已完成容器化部署实测：2026-10-18，Docker Desktop 29.8.2 / Compose v5.6.0，基础镜像 `python:3.12-slim`、`qdrant/qdrant:v1.19.1`。
- 独立验收 `scripts/verify_docker.py` 在演示模式下通过全部 5 项检查：Compose 配置、镜像构建与启动、容器内上传/检索/问答、两个容器重启后数据保留、删除清理。
- 离线验收覆盖镜像构建、容器启动、Qdrant 服务端存储与数据持久化，全程不调用付费 API。
- 已用 `.env` 真实密钥完成容器内真实云模型联调（`scripts/verify_docker_real.py`）：真实 Embedding 入库、LLM 与 Rerank 问答、资料外问题拒答全部通过。该脚本会产生少量 API 费用。
- 验收结果分别落盘 `data/docker-verification.json` 与 `data/docker-real-verification.json`（`data/` 已被 `.gitignore` 忽略，不入库）；最近一次结果见「独立容器验收」一节。

## 可靠性边界

默认连接超时 10 秒、读取无活动超时 60 秒；连接失败以及上游 HTTP 429/502/503/504 最多重试 2 次，带退避。较长的 Retry-After 会直接向用户返回失败，不提前重试。鉴权和余额错误不重试。读取超时、生成中断不自动重放；这有助于避免重复生成，但不能保证上游不会重复计费。

流式输出检测结束标记、空回答和长度截断，失败时页面清除未完成的草稿并提示重试。180 秒生成时长检查在收到下一行时执行，并非严格的总耗时截止；等待数据仍受读取超时约束。错误消息不包含上游响应正文或密钥。

`/api/health` 表示应用可响应，`/api/ready` 检查 SQLite 与 Qdrant；不调用付费模型 API。容器启动先等待 Qdrant，Docker 健康检查使用 ready 接口。单进程运行，不支持多 worker 共用嵌入式存储。尚未实现熔断、用户限流、认证或后台任务队列。

## 启动

安装并启动支持 Linux 容器的 Docker Desktop 后，在项目目录执行：

```powershell
docker compose config --quiet
docker compose up --build -d
```

配置使用本地 `.env`，不要把该文件提交或复制进镜像。浏览器打开 http://127.0.0.1:8002 。默认仅本机可访问；Qdrant 不向宿主机暴露端口。`APP_PORT` 可修改入口端口。镜像使用固定的直接 Python 依赖版本，传递依赖及基础镜像尚未全部锁定。

```powershell
docker compose ps
docker compose logs --tail 80 app
docker compose down
```

`down` 保留数据卷。不要加 `-v`，否则会删除卷内数据。本地 `data/api` 不会自动迁移到 Docker 命名卷，需要重新上传。

## 独立容器验收

```powershell
node scripts/check_compose.cjs
.\.venv\Scripts\python.exe scripts/verify_docker.py
```

第二个命令需要可用 Docker，使用随机 Compose 项目、独立数据卷和端口 18002；演示模型配置覆盖云模型密钥，不调用付费 API。验证构建、就绪、上传问答、两个容器重启后数据保留、删除清理。结果写入 `data/docker-verification.json`。脚本结束关闭自己的容器并保留自己的卷，不触碰现有服务；多次运行会留下多个独立验收卷。

最近一次验收结果（2026-10-18，本机 Docker Desktop 29.8.2）：`passed`，检查项 `compose_config`、`build_and_start`、`upload_retrieve_answer`、`restart_persistence`、`delete_cleanup` 全部通过；验收容器与网络已在脚本结束后自动清理。该结果仅代表演示模式（离线）全链路。

### 真实云模型联调（会产生少量费用）

```powershell
.\.venv\Scripts\python.exe scripts\verify_docker_real.py
```

该脚本使用 `.env` 真实密钥、独立 Compose 项目与端口 18004，验证容器内 `model_mode=api`、真实 Embedding 入库、默认混合检索 + LLM 问答、Rerank 问答（如已配置）以及资料外问题拒答；结束后删除自己的容器与卷，不触碰现有服务。

最近一次结果（2026-10-18，本机 Docker Desktop 29.8.2）：`passed`，检查项 `compose_config`、`build_and_start`、`health_api_mode`、`real_embedding_ingest`、`real_llm_answer`、`real_rerank_answer`、`refuse_out_of_scope` 全部通过。此为最小规模冒烟（单文档、数次调用），用于证明容器内可连通真实模型，不代表压测或稳定性结果。

## 回归测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

自动测试使用临时存储和模拟上游响应；不证明云模型当前可用，也不替代实际 Docker 验收。

# RAG 实测报告

本轮结论：在保留测试集 32 道可回答题上，重排将首位证据锚点命中率从纯向量的 62.5% 提升至 81.25%（+18.75 个百分点），检索中位延迟从 921 ms 增至 2107 ms。两组共 256 次检索无接口错误。抽查 8 道资料外问题均返回拒答，不能据此推断完整拒答准确率。

本轮未根据 dev 结果调参，test 使用同一检索配置；回答抽查为不同题目，不能用于跨组生成质量比较。

数据集：FastAPI 0.115.0 官方中文文档，16 篇。问题集共 80 题：64 道可回答题、16 道资料外问题。按整篇文档分为 dev/test，各 40 题。

**标签是代理编写的初稿，尚未经独立人工复核；指标不能解释为真实用户问题准确率。**

证据命中要求检索片段来自指定文档且包含标注锚点；锚点可能较短，因此仅作为检索代理指标。文档召回不等于召回完整回答依据。语料是固定历史版本，不代表当前 FastAPI 行为。

## dev：complete

语料：16 篇 / 170 个分块；Embedding：`BAAI/bge-m3`；重排：`BAAI/bge-reranker-v2-m3`；生成：`deepseek-v4-pro`。

| 检索方案 | 尝试/失败 | 文档 Recall@5 | 证据 Hit@5 | 证据 MRR@5 | 首位证据命中 | P50/P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| vector | 32/0 | 100.0% | 96.9% | 0.831 | 71.9% | 922/969 |
| bm25 | 32/0 | 87.5% | 84.4% | 0.720 | 65.6% | 11/15 |
| hybrid | 32/0 | 93.8% | 93.8% | 0.801 | 71.9% | 935/1102 |
| rerank | 32/0 | 100.0% | 100.0% | 0.984 | 96.9% | 2158/2499 |

延迟包含真实 Embedding 和可选重排网络调用，无查询缓存；每题轮换方案顺序，仅测一轮。失败单独计数，表中质量指标按成功请求统计。未计算人民币成本，因为供应商定价与计费 Token 记录尚不完整。

### 检索失败案例

- q003 / vector：FastAPI 的 OpenAPI 描述默认从哪个 URL 获取？ → first-steps.md, query-params.md, path-params.md
- q004 / bm25：为什么不建议在生产环境使用 --reload？ → middleware.md, body.md, body-updates.md, response-model.md, background-tasks.md
- q027 / hybrid：HTTPException 的 detail 必须是字符串吗？ → query-params.md, path-params.md, cors.md
- q027 / bm25：HTTPException 的 detail 必须是字符串吗？ → query-params.md, cors.md, request-files.md, path-params.md
- q043 / hybrid：示例中的处理耗时被写入哪个响应头？ → handling-errors.md, background-tasks.md, response-status-code.md
- q043 / bm25：示例中的处理耗时被写入哪个响应头？ → background-tasks.md, handling-errors.md, cors.md
- q044 / bm25：跨域前端如何读取中间件新增的自定义响应头？ → cors.md, handling-errors.md, middleware.md
- q057 / bm25：只修改资源的部分字段通常使用什么 HTTP 方法？ → first-steps.md, request-files.md, request-forms.md, cors.md

### 回答与拒答抽查（待人工评审）

**q001 · answerable：FastAPI 默认的交互式 API 文档在哪个路径？**

FastAPI 默认的交互式 API 文档位于 `/docs` 路径。[1][4]

系统拒答标记：False；引用编号有效：True；耗时：5584 ms。

参考要点：/docs

**q002 · answerable：ReDoc 文档默认从哪里访问？**

ReDoc 文档默认从 `http://127.0.0.1:8000/redoc` 访问 [1][2]。这是 FastAPI 内置的备选 API 文档入口 [2]。

系统拒答标记：False；引用编号有效：True；耗时：7955 ms。

参考要点：/redoc

**q003 · answerable：FastAPI 的 OpenAPI 描述默认从哪个 URL 获取？**

FastAPI 的 OpenAPI 描述默认从 `http://127.0.0.1:8000/openapi.json` 获取 [1]。

系统拒答标记：False；引用编号有效：True；耗时：10782 ms。

参考要点：/openapi.json

**q004 · answerable：为什么不建议在生产环境使用 --reload？**

现有资料不足以回答“为什么不建议在生产环境使用 `--reload`”的具体原因。资料中仅说明：`--reload` 的作用是让服务器在更新代码后重新启动，并且“仅在开发时使用该选项” [1]。资料没有给出该选项不适合生产环境的技术理由（如性能、稳定性、安全性等），因此无法依据现有资料解释具体原因。

系统拒答标记：True；引用编号有效：True；耗时：9792 ms。

参考要点：开发自动重载会增加资源消耗，生产应关闭。

**n001 · unanswerable：本公司的 DeepSeek API 密钥具体是什么？**

现有资料不足以回答本公司的 DeepSeek API 密钥具体是什么。

提供的参考资料 [1] 至 [5] 内容涉及 FastAPI 路径参数、测试文件、响应模型等，均未包含 DeepSeek API 密钥相关信息，因此无法依据这些资料给出该密钥。

系统拒答标记：True；引用编号有效：True；耗时：7160 ms。

参考要点：现有资料不足以回答

**n003 · unanswerable：这套系统上周真实的日活用户数是多少？**

现有资料不足以回答。

提供的参考资料 [1][2][3][4][5] 分别涉及 FastAPI 的请求体更新、路径参数、响应模型和后台任务，均未包含“上周真实的日活用户数”或任何日活用户数据。因此无法从这些资料中获知该系统上周真实的日活用户数。

系统拒答标记：True；引用编号有效：True；耗时：8549 ms。

参考要点：现有资料不足以回答

**n005 · unanswerable：我们团队值班人员的手机号码是什么？**

现有资料不足以回答。

提供的参考资料 [1][2][3][4][5] 均未包含团队值班人员的手机号码。

系统拒答标记：True；引用编号有效：True；耗时：6951 ms。

参考要点：现有资料不足以回答

**n007 · unanswerable：上一次线上故障损失了多少金额？**

现有资料不足以回答。

提供的参考资料 [1][2][3][4][5] 均为 FastAPI 文档片段，内容涉及更新部分数据、HTTP 状态码、路径参数等，未提及“上一次线上故障”或损失金额 [1][2][3][4][5]。

系统拒答标记：True；引用编号有效：True；耗时：8007 ms。

参考要点：现有资料不足以回答

## test：complete

语料：16 篇 / 170 个分块；Embedding：`BAAI/bge-m3`；重排：`BAAI/bge-reranker-v2-m3`；生成：`deepseek-v4-pro`。

| 检索方案 | 尝试/失败 | 文档 Recall@5 | 证据 Hit@5 | 证据 MRR@5 | 首位证据命中 | P50/P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| vector | 32/0 | 100.0% | 90.6% | 0.740 | 62.5% | 921/1181 |
| bm25 | 32/0 | 96.9% | 93.8% | 0.747 | 62.5% | 15/18 |
| hybrid | 32/0 | 100.0% | 96.9% | 0.811 | 68.8% | 914/1454 |
| rerank | 32/0 | 100.0% | 96.9% | 0.885 | 81.2% | 2107/2779 |

延迟包含真实 Embedding 和可选重排网络调用，无查询缓存；每题轮换方案顺序，仅测一轮。失败单独计数，表中质量指标按成功请求统计。未计算人民币成本，因为供应商定价与计费 Token 记录尚不完整。

### 检索失败案例

- q005 / rerank：路径参数声明为 int 后，字符串数字会如何处理？ → query-params.md, path-params.md, body.md
- q016 / vector：FastAPI 能在同一个接口中接收路径参数和请求体吗？ → body.md, path-params.md, query-params.md, request-files.md, first-steps.md
- q030 / bm25：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q030 / hybrid：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q030 / vector：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q048 / vector：发送简单邮件通知是否必须引入大型消息队列？ → background-tasks.md
- q063 / bm25：jsonable_encoder 从哪里导入？ → handling-errors.md, background-tasks.md, request-files.md, request-forms.md, testing.md

### 回答与拒答抽查（待人工评审）

**q005 · answerable：路径参数声明为 int 后，字符串数字会如何处理？**

路径参数声明为 `int` 后，URL 中的字符串数字会被自动转换为 `int` 类型，并进行类型校验。

- 路径参数本质上是 URL 的组成部分，类型本应是字符串；但声明 `int` 类型后，值会转换为声明的类型，并执行类型校验 [1][2]。
- 与路径参数相关的流程包括**数据解析**和**数据校验**，这些同样适用于查询参数 [1]。
- 因此，如果路径中传入的是合法数字字符串（如 `/items/123`），会得到整数值 `123`；如果传入的不是合法整数，则校验不通过。现有资料未说明校验失败时的具体响应形式 [1][2]。

系统拒答标记：False；引用编号有效：True；耗时：18375 ms。

参考要点：自动解析为整数。

**q013 · answerable：FastAPI 请求体模型应该继承哪个基类？**

FastAPI 请求体模型应该继承 Pydantic 的 `BaseModel` 基类 [1][3]。资料中明确说明“把数据模型声明为继承 `BaseModel` 的类” [1]，并从 `pydantic` 导入 `BaseModel` [3]。示例代码也展示为 `class Item(BaseModel)` [1][2][4]。

系统拒答标记：False；引用编号有效：True；耗时：8204 ms。

参考要点：Pydantic BaseModel。

**q021 · answerable：FastAPI 通过哪个对象声明表单字段？**

FastAPI 通过 `Form` 对象声明表单字段 [1][5]。资料显示接收表单字段时要使用 `Form` [5]，并且可以使用 `Form` 声明与 `Body`、`Query`、`Path`、`Cookie` 相同的元数据和验证 [1]。小结也提到使用 `Form` 声明表单数据输入参数 [2]。

系统拒答标记：False；引用编号有效：True；耗时：8584 ms。

参考要点：从 fastapi 导入 Form。

**q029 · answerable：response_model 应设置在函数参数还是装饰器参数中？**

_model 应设置在**路径操作装饰器**的参数中，而不是函数参数中 [1][2]。

资料明确指出，`response_model` 是装饰器方法（如 `get`、`post` 等）的一个参数，它不属于*路径操作函数* [1]。总结部分也说明应使用*路径操作装饰器*的 `response_model` 参数来定义响应模型 [2]。

系统拒答标记：False；引用编号有效：True；耗时：6131 ms。

参考要点：设置在路径操作装饰器。

**n002 · unanswerable：我们的生产数据库密码是多少？**

现有资料不足以回答“生产数据库密码是多少”。

资料中未包含任何生产数据库密码信息，仅涉及 FastAPI 示例代码中的明文密码字段、响应模型安全提醒及测试用的 `fake_secret_token = "coneofsilence"` 等内容，但这些都不是生产数据库密码[1][2][3][4][5]。

系统拒答标记：True；引用编号有效：True；耗时：6322 ms。

参考要点：现有资料不足以回答

**n004 · unanswerable：内部 Atlas 服务 2027 年的迁移时间是什么？**

现有资料不足以回答。提供的参考资料中未提及“内部 Atlas 服务”或“2027 年的迁移时间”相关信息。

系统拒答标记：True；引用编号有效：True；耗时：5738 ms。

参考要点：现有资料不足以回答

**n006 · unanswerable：本项目服务器当前 CPU 温度是多少？**

现有资料不足以回答。参考资料 [1][2][3][4][5] 均为 FastAPI 使用文档，内容涉及路径参数、响应状态码、应用启动、错误处理等，未包含本项目服务器当前 CPU 温度数据。

系统拒答标记：True；引用编号有效：True；耗时：7904 ms。

参考要点：现有资料不足以回答

**n008 · unanswerable：公司给研发团队分配的年度预算是多少？**

现有资料不足以回答。

系统拒答标记：True；引用编号有效：True；耗时：6294 ms。

参考要点：现有资料不足以回答

## 标注审核

已确认 q004 的参考答案超出原文；详见 [LABEL_REVIEW.md](LABEL_REVIEW.md)。当前不报告答案准确率，检索指标仅反映锚点匹配。

## 可复现方式

```powershell
.\.venv\Scripts\python.exe eval/build_dataset.py
.\.venv\Scripts\python.exe eval/benchmark.py --split dev --answers 8 --output eval/results/dev.json
.\.venv\Scripts\python.exe eval/benchmark.py --split test --answers 8 --output eval/results/test.json
.\.venv\Scripts\python.exe eval/report.py
```

运行 benchmark 会调用配置的真实服务并可能产生费用。评测库位于 data/benchmark-fastapi，独立于交互知识库。原始逐题结果、来源片段和回答保存在 eval/results。测试集在本轮不用于调参；未来若根据这些结果修改检索，应另建新保留集。

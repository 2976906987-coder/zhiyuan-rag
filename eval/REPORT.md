# RAG 实测报告

数据集：FastAPI 0.115.0 官方中文文档，16 篇。问题集共 80 题：64 道可回答题、16 道资料外问题。按整篇文档分为 dev/test，各 40 题。

**证据锚点已于 2026-10-18 完成精修并逐题核对原文（v2，见 `eval/refine_anchors.py` 与 `audit_labels.py`）：64 个锚点均能在指定文档定位，跨文档锚点为 0；但仍为单轮 AI 辅助复核、非独立多人金标准，指标不能等同于真实用户问题的答案准确率。**

证据命中要求检索片段来自指定文档且包含标注锚点；锚点是定位答案的连续原文片段，少数代码锚点在不同语言示例标签页中重复（属于答案本身）。文档召回不等于召回完整回答依据。语料是固定历史版本，不代表当前 FastAPI 行为。

## dev：complete

语料：16 篇 / 170 个分块；Embedding：`BAAI/bge-m3`；重排：`BAAI/bge-reranker-v2-m3`；生成：`deepseek-v4-pro`。

| 检索方案 | 尝试/失败 | 文档 Recall@5 | 证据 Hit@5 | 证据 MRR@5 | 首位证据命中 | P50/P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| vector | 32/0 | 100.0% | 93.8% | 0.708 | 53.1% | 624/895 |
| bm25 | 32/0 | 90.6% | 78.1% | 0.638 | 53.1% | 14/24 |
| hybrid | 32/0 | 90.6% | 87.5% | 0.728 | 62.5% | 600/847 |
| rerank | 32/0 | 100.0% | 100.0% | 0.897 | 81.2% | 1522/1943 |

延迟包含真实 Embedding 和可选重排网络调用，无查询缓存；每题轮换方案顺序，仅测一轮。失败单独计数，表中质量指标按成功请求统计。未计算人民币成本，因为供应商定价与计费 Token 记录尚不完整。

### 检索失败案例

- q003 / vector：FastAPI 的 OpenAPI 描述默认从哪个 URL 获取？ → first-steps.md, query-params.md, path-params.md
- q004 / vector：--reload 选项有什么作用？文档建议在什么环境使用？ → first-steps.md, request-files.md, background-tasks.md, path-params.md, query-params.md
- q004 / hybrid：--reload 选项有什么作用？文档建议在什么环境使用？ → request-files.md, path-params.md, static-files.md, background-tasks.md
- q026 / bm25：找不到资源时如何返回 404？ → response-status-code.md, handling-errors.md, cors.md
- q026 / hybrid：找不到资源时如何返回 404？ → handling-errors.md, response-status-code.md, testing.md
- q027 / hybrid：HTTPException 的 detail 必须是字符串吗？ → query-params.md, path-params.md, cors.md
- q027 / bm25：HTTPException 的 detail 必须是字符串吗？ → query-params.md, cors.md, request-files.md, path-params.md
- q043 / hybrid：示例中的处理耗时被写入哪个响应头？ → handling-errors.md, background-tasks.md, response-status-code.md
- q043 / bm25：示例中的处理耗时被写入哪个响应头？ → background-tasks.md, handling-errors.md, cors.md
- q044 / bm25：跨域前端如何读取中间件新增的自定义响应头？ → cors.md, handling-errors.md, middleware.md
- q049 / bm25：教程中的 TestClient 需要先安装哪个 HTTP 客户端包？ → handling-errors.md, request-files.md, testing.md
- q050 / bm25：FastAPI 可以搭配哪个 Python 测试框架？ → testing.md, body.md, path-params.md

### 回答与拒答抽查（待人工评审）

**q001 · answerable：FastAPI 默认的交互式 API 文档在哪个路径？**

FastAPI 默认的交互式 API 文档位于 `/docs` 路径 [1][4]。

系统拒答标记：False；引用编号有效：True；耗时：4745 ms。

参考要点：/docs

**q009 · answerable：不属于路径参数的普通函数参数会被解释成什么？**

不属于路径参数的普通函数参数（即类型为 `int`、`float`、`str`、`bool` 等单类型的参数）会被解释为**查询参数** [1][3]。

系统拒答标记：False；引用编号有效：True；耗时：7470 ms。

参考要点：查询参数。

**q017 · answerable：接收上传文件前需要安装哪个额外包？**

接收上传文件前需要安装 `python-multipart` 额外包 [1]。

系统拒答标记：False；引用编号有效：True；耗时：4213 ms。

参考要点：python-multipart。

**q025 · answerable：为什么 HTTPException 应使用 raise 而不是 return？**

根据现有资料，`HTTPException` 应使用 `raise` 而不是 `return`，原因如下：

1. `HTTPException` 是额外包含了与 API 有关数据的常规 Python 异常。因为是 Python 异常，所以不能 `return`，只能 `raise` [1]。

2. 当在路径操作函数中触发 `HTTPException` 时，FastAPI 会立即终止请求，不再继续执行路径操作函数中的后续代码，并把 `HTTPException` 的 HTTP 错误发送给客户端 [1]。

3. 资料还提示，在介绍依赖项与安全的章节中可以了解更多用 `raise` 异常代替 `return` 值的优势，但本资料未展开具体内容 [1]。

系统拒答标记：False；引用编号有效：True；耗时：8066 ms。

参考要点：它是异常，应抛出以中断请求处理。

**n001 · unanswerable：本公司的 DeepSeek API 密钥具体是什么？**

现有资料不足以回答“本公司的 DeepSeek API 密钥具体是什么”。

参考资料中仅包含 FastAPI 文档片段，例如路径参数处理、测试示例和响应模型安全说明，未出现任何与 DeepSeek API 密钥相关的信息 [1][2][3][4][5]。其中出现的 `"coneofsilence"` 只是 FastAPI 测试示例里的 `fake_secret_token`，不是 DeepSeek API 密钥 [3][4]。

系统拒答标记：True；引用编号有效：True；耗时：6784 ms。

参考要点：现有资料不足以回答

**n003 · unanswerable：这套系统上周真实的日活用户数是多少？**

现有资料不足以回答。

系统拒答标记：True；引用编号有效：True；耗时：6038 ms。

参考要点：现有资料不足以回答

**n005 · unanswerable：我们团队值班人员的手机号码是什么？**

现有资料不足以回答。参考资料 [1][2][3][4][5] 中均未提及团队值班人员的手机号码，仅涉及 FastAPI 的后台任务与响应状态码等内容。

系统拒答标记：True；引用编号有效：True；耗时：4909 ms。

参考要点：现有资料不足以回答

**n007 · unanswerable：上一次线上故障损失了多少金额？**

现有资料不足以回答。提供的参考资料 [1][2][3][4][5] 仅涉及 FastAPI 文档内容，未包含任何关于线上故障损失金额的信息。

系统拒答标记：True；引用编号有效：True；耗时：7391 ms。

参考要点：现有资料不足以回答

## test：complete

语料：16 篇 / 170 个分块；Embedding：`BAAI/bge-m3`；重排：`BAAI/bge-reranker-v2-m3`；生成：`deepseek-v4-pro`。

| 检索方案 | 尝试/失败 | 文档 Recall@5 | 证据 Hit@5 | 证据 MRR@5 | 首位证据命中 | P50/P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| vector | 32/0 | 100.0% | 81.2% | 0.628 | 50.0% | 941/1356 |
| bm25 | 32/0 | 96.9% | 90.6% | 0.622 | 43.8% | 12/18 |
| hybrid | 32/0 | 100.0% | 93.8% | 0.720 | 56.2% | 932/1514 |
| rerank | 32/0 | 100.0% | 93.8% | 0.759 | 65.6% | 2134/2744 |

延迟包含真实 Embedding 和可选重排网络调用，无查询缓存；每题轮换方案顺序，仅测一轮。失败单独计数，表中质量指标按成功请求统计。未计算人民币成本，因为供应商定价与计费 Token 记录尚不完整。

### 检索失败案例

- q005 / vector：路径参数声明为 int 后，字符串数字会如何处理？ → query-params.md, path-params.md
- q005 / rerank：路径参数声明为 int 后，字符串数字会如何处理？ → query-params.md, path-params.md, body.md
- q006 / vector：固定路径 /users/me 和动态路径哪个应先声明？ → static-files.md, first-steps.md, path-params.md
- q016 / vector：FastAPI 能在同一个接口中接收路径参数和请求体吗？ → body.md, path-params.md, query-params.md, request-files.md, first-steps.md
- q021 / vector：FastAPI 通过哪个对象声明表单字段？ → path-params.md, testing.md, body.md, request-forms.md, request-files.md
- q021 / hybrid：FastAPI 通过哪个对象声明表单字段？ → request-forms.md, request-files.md, query-params.md
- q030 / bm25：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q030 / hybrid：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q030 / rerank：怎样防止返回的用户对象泄漏密码字段？ → response-model.md
- q030 / vector：怎样防止返回的用户对象泄漏密码字段？ → response-model.md, request-forms.md
- q039 / bm25：FastAPI 使用什么中间件配置跨域？ → cors.md, middleware.md
- q048 / vector：发送简单邮件通知是否必须引入大型消息队列？ → background-tasks.md

### 回答与拒答抽查（待人工评审）

**q005 · answerable：路径参数声明为 int 后，字符串数字会如何处理？**

路径参数在 URL 中本质是字符串；当路径参数声明为 `int` 后，FastAPI 会将字符串数字转换为 `int` 类型，并进行类型校验 [1][2]。

资料 [1] 指出，URL 中的值本应是字符串，但声明 Python 类型（如 `int`）后，这些值会转换为声明的类型并进行类型校验；同时，所有应用于路径参数的流程也适用于查询参数 [1]。资料 [2] 展示了把路径参数 `item_id` 声明为 `int` 的示例 [2]。

因此，如果路径参数是字符串数字（例如 `"123"`），它会被解析为整数 `123` [1][2]。如果字符串不是合法数字，资料未明确说明具体错误响应，现有资料不足以回答该错误情况。

系统拒答标记：True；引用编号有效：True；耗时：17015 ms。

参考要点：自动解析为整数。

**q013 · answerable：FastAPI 请求体模型应该继承哪个基类？**

FastAPI 请求体模型应该继承 Pydantic 的 `BaseModel` 基类[1][3]。声明时需要从 `pydantic` 导入 `BaseModel`，然后让模型类继承它[3]。例如：

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
```

[1][3]

系统拒答标记：False；引用编号有效：True；耗时：6573 ms。

参考要点：Pydantic BaseModel。

**q021 · answerable：FastAPI 通过哪个对象声明表单字段？**

FastAPI 通过 `Form` 对象声明表单字段。资料指出：“接收的不是 JSON，而是表单字段时，要使用 `Form`。”[5] 并且“声明表单体要显式使用 `Form`，否则，FastAPI 会把该参数当作查询参数或请求体（JSON）参数。”[1]

系统拒答标记：False；引用编号有效：True；耗时：10778 ms。

参考要点：从 fastapi 导入 Form。

**q029 · answerable：response_model 应设置在函数参数还是装饰器参数中？**

_model 应设置在**装饰器参数**中，而不是函数参数中。[1][2]

资料明确指出：`response_model` 是“装饰器”方法（如 `get`、`post` 等）的一个参数，不属于*路径操作函数*。[1] 总结部分也说明应使用*路径操作装饰器*的 `response_model` 参数来定义响应模型。[2]

系统拒答标记：False；引用编号有效：True；耗时：6176 ms。

参考要点：设置在路径操作装饰器。

**n002 · unanswerable：我们的生产数据库密码是多少？**

现有资料不足以回答。  

资料中唯一出现的类似凭据是 `fake_secret_token = "coneofsilence"` 和 `fake_db` 测试数据，这些是文档示例中的假数据，并非生产数据库密码 [4][5]。资料还强调不要存储或返回用户的明文密码 [1][2][3]，但未提供任何生产数据库密码。

系统拒答标记：True；引用编号有效：True；耗时：8876 ms。

参考要点：现有资料不足以回答

**n004 · unanswerable：内部 Atlas 服务 2027 年的迁移时间是什么？**

现有资料不足以回答。

查阅提供的参考资料 [1][2][3][4][5]，内容均为 FastAPI 文档片段，涉及错误处理、请求体更新、中间件、请求体与请求文件等主题，未提及“内部 Atlas 服务”或“2027 年的迁移时间” [1][2][3][4][5]。因此无法给出该迁移时间。

系统拒答标记：True；引用编号有效：True；耗时：8480 ms。

参考要点：现有资料不足以回答

**n006 · unanswerable：本项目服务器当前 CPU 温度是多少？**

现有资料不足以回答。

提供的资料仅涉及 FastAPI 的路径参数与顺序 [1]、HTTP 状态码 [2]、应用启动步骤 [3]、错误处理 [4][5]，均未包含本项目服务器当前 CPU 温度或任何硬件温度监控数据 [1][2][3][4][5]。因此无法依据现有资料给出 CPU 温度。

系统拒答标记：True；引用编号有效：True；耗时：10126 ms。

参考要点：现有资料不足以回答

**n008 · unanswerable：公司给研发团队分配的年度预算是多少？**

现有资料不足以回答。提供的参考资料均为 FastAPI 技术文档片段，其中未包含任何关于公司研发团队年度预算的信息。

系统拒答标记：True；引用编号有效：True；耗时：5293 ms。

参考要点：现有资料不足以回答

## 标注审核

v2 复核（2026-10-18）：64 个证据锚点全部精修为在指定文档唯一或仅在答案处出现的连续原文片段，跨文档锚点清零（质检 `eval/audit_labels.py` 通过）；q004 原题（“为什么不建议生产环境使用 --reload”）的参考答案超出固定版本原文，已改为询问 `--reload` 的作用与建议使用环境，详见 [LABEL_REVIEW.md](LABEL_REVIEW.md)。当前不报告答案准确率，检索指标仅反映锚点匹配。

## 可复现方式

```powershell
.\.venv\Scripts\python.exe eval/build_dataset.py
.\.venv\Scripts\python.exe eval/refine_anchors.py
.\.venv\Scripts\python.exe eval/audit_labels.py
.\.venv\Scripts\python.exe eval/benchmark.py --split dev --answers 8 --output eval/results/dev.json
.\.venv\Scripts\python.exe eval/benchmark.py --split test --answers 8 --output eval/results/test.json
.\.venv\Scripts\python.exe eval/report.py
```

运行 benchmark 会调用配置的真实服务并可能产生费用。评测库位于 data/benchmark-fastapi，独立于交互知识库。原始逐题结果、来源片段和回答保存在 eval/results。测试集在本轮不用于调参；未来若根据这些结果修改检索，应另建新保留集。

当前数据集 SHA256：`f83daa84267cdd8b48b2245d59f15005860d31f08cff3254e3392d3f62217a3b`。复现时如运行 build_dataset.py，必须接着运行 refine_anchors.py 和 audit_labels.py，再运行 benchmark；否则会恢复早期标签。

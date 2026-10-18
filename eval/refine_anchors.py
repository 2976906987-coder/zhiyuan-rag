"""One-off label refinement for eval/benchmark.jsonl.

Replaces overly short / non-unique / cross-file evidence anchors with
continuous substrings that uniquely locate the answer in the expected
document, and revises q004 (the original reference answer went beyond the
source). Every replacement anchor is verified to occur in the expected
document before writing; the script aborts on any mismatch.

Idempotent: running it again produces the same content.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'eval' / 'benchmark.jsonl'
CORPUS = ROOT / 'eval' / 'corpus' / 'fastapi'

NEW_STATUS = 'reviewed-anchor-verified'

# case_id -> evidence anchor (a continuous substring of the expected file)
ANCHORS = {
 'q001': '自动生成的交互式 API 文档',
 'q002': '可选的自动生成文档',
 'q003': '/openapi.json',
 'q004': '让服务器在更新代码后重新启动。仅在开发时使用该选项。',
 'q005': '函数接收并返回的值是 `3`（ `int`），不是 `"3"`',
 'q006': '之前声明 `/users/me`',
 'q007': '继承自 `str` 和 `Enum` 的子类',
 'q008': '结尾部分的 `:path` 说明该参数应匹配',
 'q009': '会把该参数自动解释为',
 'q010': '把默认值设为 `None` 即可声明',
 'q011': '声明为 `bool` 类型，FastAPI 会自动转换',
 'q012': '把查询参数设置为**必选**，就不要声明默认值',
 'q013': '从 `pydantic` 中导入 `BaseModel`',
 'q014': '默认值为 `None` 的模型属性也是可选的',
 'q015': '是客户端发送给 API 的数据。**响应体**是 API 发送给客户端的数据',
 'q016': '支持同时声明路径参数和请求体',
 'q017': '传文件，要预先安装',
 'q018': 'spooled',
 'q019': 'return {"filename": file.filename}',
 'q020': '移动到文件开头',
 'q021': '而是表单字段时，要使用 `Form`',
 'q022': '表单数据的「媒体类型」编码一般为',
 'q023': '包含文件的表单编码为',
 'q024': '可在一个*路径操作*中声明多个 `Form` 参数',
 'q025': '不能 `return`，只能 `raise`',
 'q026': '触发状态码为 `404` 的异常',
 'q027': '可以用参数 `detail` 传递任何能转换为 JSON 的值',
 'q028': '添加自定义异常控制器',
 'q029': '`response_model` 参数来定义响应模型',
 'q030': '确保私有数据被过滤掉',
 'q031': '仅返回显式设定的值',
 'q032': '例如 `List[Item]`',
 'q033': '`status_code` 参数声明用于响应的 HTTP 状态码',
 'q034': '`201` 表示**已创建**',
 'q035': '因此，该响应不能包含响应体',
 'q036': 'IntEnum',
 'q037': '源是协议（`http`，`https`）',
 'q038': '不包括所有涉及凭据的内容',
 'q039': '应用中使用 `CORSMiddleware` 来配置',
 'q040': '向后端发送一个 HTTP `OPTIONS` 请求',
 'q041': 'response = await call_next(request)',
 'q042': '使用装饰器 `@app.middleware("http")`',
 'q043': 'response.headers["X-Process-Time"]',
 'q044': '的 `expose_headers` 参数中',
 'q045': '返回响应后',
 'q046': '用 `.add_task()` 方法将任务函数传到',
 'q047': '它们往往需要更复杂的配置，即消息/作业队列管理器',
 'q048': '您需要执行小型后台任务（如发送电子邮件通知）',
 'q049': '`pip install httpx`',
 'q050': '标准的 `pytest` 约定',
 'q051': '测试函数是普通的 `def`，不是 `async def`',
 'q052': '传一个JSON体，传一个Python对象',
 'q053': '使用 `StaticFiles`从目录中自动提供',
 'q054': '在特定路径添加一个完全',
 'q055': '文档不会包含已挂载应用',
 'q056': '指向包含你的静态文件的目录名',
 'q057': '操作用于更新 *部分* 数据',
 'q058': '只包含创建 `item` 模型时显式设置的数据',
 'q059': '以 JSON 格式存储的数据（比如，使用 NoSQL 数据库时）',
 'q060': '把模型中所有的属性标记为可选',
 'q061': '提供了`jsonable_encoder()`函数',
 'q062': 'ISO格式化',
 'q063': '## 使用`jsonable_encoder`',
 'q064': '它将返回一个Python标准数据结构',
}

# q004: the original "why not in production" answer was not supported by the
# fixed-version source, so the question/answer are scoped to what the source
# actually states (what --reload does and which environment it is meant for).
REVISIONS = {
 'q004': {
   'question': '--reload 选项有什么作用？文档建议在什么环境使用？',
   'reference_answer': '让服务器在代码更新后重新启动；仅在开发时使用，不用于生产。',
 },
}


def main():
    docs = {p.name: p.read_text(encoding='utf-8') for p in CORPUS.glob('*.md')}
    cases = [json.loads(line) for line in DATA.read_text(encoding='utf-8').splitlines()]

    # Verify every anchor before mutating anything.
    errors = []
    for case in cases:
        if case['kind'] != 'answerable':
            continue
        cid = case['id']
        anchor = ANCHORS[cid]
        for fname in case['expected_files']:
            if fname not in docs:
                errors.append('%s: missing file %s' % (cid, fname))
            elif anchor not in docs[fname]:
                errors.append('%s: anchor not found in %s -> %r' % (cid, fname, anchor))
    if errors:
        print('Refinement aborted, anchor problems:')
        for e in errors:
            print('  ', e)
        raise SystemExit(1)

    changed_anchors = 0
    changed_text = 0
    for case in cases:
        cid = case['id']
        if case['kind'] == 'answerable':
            new_anchor = ANCHORS[cid]
            if case['evidence'][0]['anchor'] != new_anchor:
                case['evidence'][0]['anchor'] = new_anchor
                changed_anchors += 1
            if cid in REVISIONS:
                rev = REVISIONS[cid]
                if case['question'] != rev['question']:
                    case['question'] = rev['question']
                    changed_text += 1
                if case['reference_answer'] != rev['reference_answer']:
                    case['reference_answer'] = rev['reference_answer']
        case['label_status'] = NEW_STATUS

    DATA.write_text('\n'.join(json.dumps(c, ensure_ascii=False) for c in cases) + '\n',
                    encoding='utf-8')
    print('Refined anchors changed: %d; question/answer revisions: %d; total cases: %d'
          % (changed_anchors, changed_text, len(cases)))
    print('label_status set to %r for all cases' % NEW_STATUS)


if __name__ == '__main__':
    main()

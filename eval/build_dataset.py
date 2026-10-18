"""Author-curated questions, source anchors validated against pinned files.

Draft labels require independent human review before resume-quality claims.
Entire source documents belong to one split to avoid paraphrase leakage.
"""
import json
from pathlib import Path

# question | source anchor | reference answer
GROUPS = {
'first-steps': [
('FastAPI 默认的交互式 API 文档在哪个路径？','/docs','/docs'),
('ReDoc 文档默认从哪里访问？','/redoc','/redoc'),
('FastAPI 的 OpenAPI 描述默认从哪个 URL 获取？','/openapi.json','/openapi.json'),
('为什么不建议在生产环境使用 --reload？','--reload','开发自动重载会增加资源消耗，生产应关闭。')],
'path-params': [
('路径参数声明为 int 后，字符串数字会如何处理？','解析','自动解析为整数。'),
('固定路径 /users/me 和动态路径哪个应先声明？','/users/me','固定路径先声明，避免被动态路径匹配。'),
('如何限制路径参数只能取预定义值？','Enum','用继承 str 和 Enum 的枚举定义。'),
('如何让一个路径参数包含斜杠？',':path','使用 Starlette 的 path 转换器，例如 {file_path:path}。')],
'query-params': [
('不属于路径参数的普通函数参数会被解释成什么？','查询参数','查询参数。'),
('查询参数默认值设置为 None 表示什么？','None','该参数可选。'),
('查询参数 short 可以自动转换为布尔值吗？','bool','声明为 bool 时支持布尔解析。'),
('怎么声明一个必须由客户端提供的查询参数？','必选','不提供默认值即可声明必需参数。')],
'body': [
('FastAPI 请求体模型应该继承哪个基类？','BaseModel','Pydantic BaseModel。'),
('请求体中的非必填字段怎么声明？','None','为字段提供默认值，例如 None。'),
('请求体与响应体分别表示什么？','请求体','客户端发送的是请求体，服务端返回的是响应体。'),
('FastAPI 能在同一个接口中接收路径参数和请求体吗？','路径参数','可以，按路径声明及模型类型区分。')],
'request-files': [
('接收上传文件前需要安装哪个额外包？','python-multipart','python-multipart。'),
('大文件上传为何更适合 UploadFile 而不是 bytes？','spooled','采用 spooled 文件，超过内存阈值转到磁盘。'),
('UploadFile 怎么获取上传文件名？','filename','filename 属性。'),
('上传文件读取后，怎样回到开头重新读取？','seek','调用 await file.seek(0)。')],
'request-forms': [
('FastAPI 通过哪个对象声明表单字段？','Form','从 fastapi 导入 Form。'),
('普通表单通常用什么内容类型编码？','application/x-www-form-urlencoded','application/x-www-form-urlencoded。'),
('包含文件的表单使用什么编码类型？','multipart/form-data','multipart/form-data。'),
('表单字段和 JSON Body 字段能在同一请求中同时接收吗？','JSON','不能把同一个表单请求同时当作 JSON 请求体。')],
'handling-errors': [
('为什么 HTTPException 应使用 raise 而不是 return？','raise','它是异常，应抛出以中断请求处理。'),
('找不到资源时如何返回 404？','404','抛出 HTTPException(status_code=404, detail=...)。'),
('HTTPException 的 detail 必须是字符串吗？','JSON','可以是可转换为 JSON 的数据。'),
('如何注册自定义异常处理器？','exception_handler','使用 @app.exception_handler 装饰器。')],
'response-model': [
('response_model 应设置在函数参数还是装饰器参数中？','路径操作装饰器','设置在路径操作装饰器。'),
('怎样防止返回的用户对象泄漏密码字段？','过滤','定义不含密码的输出模型，过滤额外字段。'),
('响应时怎样只返回显式设置过的字段？','response_model_exclude_unset','设置 response_model_exclude_unset=True。'),
('response_model 可以使用 Pydantic 模型列表吗？','List','可以声明模型列表。')],
'response-status-code': [
('如何在路径装饰器里指定返回状态码？','status_code','使用 status_code 参数。'),
('创建资源常用哪个 HTTP 状态码？','201','201 Created。'),
('204 响应可以包含响应体吗？','不能包含响应体','不可以，204 表示无内容。'),
('status_code 除整数外能接受 IntEnum 吗？','IntEnum','可以，例如 http.HTTPStatus。')],
'cors': [
('浏览器判断源是否相同，需要比较哪三个部分？','协议','协议、域名及端口。'),
('为什么带 Cookie 的跨域请求不宜只配置通配符来源？','凭据','通配符不能覆盖所有涉及凭据的通信，应显式列出来源。'),
('FastAPI 使用什么中间件配置跨域？','CORSMiddleware','CORSMiddleware。'),
('浏览器的跨域预检请求使用哪种 HTTP 方法？','OPTIONS','OPTIONS。')],
'middleware': [
('中间件如何把请求交给后续路径处理？','call_next','调用 await call_next(request)。'),
('HTTP 中间件用什么装饰器定义？','@app.middleware','@app.middleware("http")。'),
('示例中的处理耗时被写入哪个响应头？','X-Process-Time','X-Process-Time。'),
('跨域前端如何读取中间件新增的自定义响应头？','expose_headers','在 CORS 配置 expose_headers。')],
'background-tasks': [
('BackgroundTasks 中的任务在返回响应前还是之后执行？','返回响应后','返回响应后执行。'),
('怎样向后台任务对象添加任务函数？','add_task','通过 add_task 传入函数及参数。'),
('繁重且需要多进程或多服务器的后台计算适合什么方案？','Celery','考虑 Celery 等任务队列。'),
('发送简单邮件通知是否必须引入大型消息队列？','小型后台任务','不必须，同进程小型任务可用 BackgroundTasks。')],
'testing': [
('教程中的 TestClient 需要先安装哪个 HTTP 客户端包？','httpx','httpx。'),
('FastAPI 可以搭配哪个 Python 测试框架？','pytest','pytest。'),
('普通 TestClient 测试是否需要定义为 async def？','def','普通同步 def 即可。'),
('测试请求发送 JSON 时应使用哪个参数？','json','使用 json 参数。')],
'static-files': [
('FastAPI 提供静态文件使用哪个类？','StaticFiles','StaticFiles。'),
('挂载静态文件的 mount 表示什么？','独立','在路径上挂载一个独立应用，处理其子路径。'),
('挂载的静态文件应用会出现在主应用 OpenAPI 中吗？','OpenAPI','不会，挂载应用独立。'),
('静态文件的目录通过哪个参数指定？','directory','directory 参数。')],
'body-updates': [
('只修改资源的部分字段通常使用什么 HTTP 方法？','PATCH','PATCH。'),
('部分更新时如何避免未传字段的默认值覆盖已有值？','exclude_unset','使用 exclude_unset=True 提取显式传入字段。'),
('更新数据存入 JSON 数据库前可以用什么转换工具？','jsonable_encoder','jsonable_encoder。'),
('更新接口若希望所有字段都能省略，应如何定义模型？','可选','把所有字段标为可选并设置默认值。')],
'encoder': [
('如何把 Pydantic 模型转换成 JSON 兼容数据？','jsonable_encoder','使用 jsonable_encoder。'),
('datetime 转成 JSON 兼容格式后是什么类型？','str','字符串，例如 ISO 格式。'),
('jsonable_encoder 从哪里导入？','fastapi.encoders','fastapi.encoders。'),
('jsonable_encoder 返回的是 JSON 字符串还是 Python 数据结构？','dict','返回 JSON 兼容的 Python 数据结构，例如 dict。')],
}
NEGATIVE = [
'本公司的 DeepSeek API 密钥具体是什么？','我们的生产数据库密码是多少？',
'这套系统上周真实的日活用户数是多少？','内部 Atlas 服务 2027 年的迁移时间是什么？',
'我们团队值班人员的手机号码是什么？','本项目服务器当前 CPU 温度是多少？',
'上一次线上故障损失了多少金额？','公司给研发团队分配的年度预算是多少？',
'请给出我们线上 Qdrant 集群的内网 IP。','我们公司的客户合同编号是什么？',
'项目目前存储了多少个真实客户账户？','明天杭州的实时天气如何？',
'当前硅基流动账户余额具体是多少？','我们生产环境实际每秒请求数是多少？',
'团队为本项目购买的云服务器订单号是什么？','最近一次备份的文件校验和是多少？']


def main():
    cases = []
    for group_index, (name, questions) in enumerate(GROUPS.items()):
        text = Path(f'eval/corpus/fastapi/{name}.md').read_text(encoding='utf-8')
        for question, anchor, reference in questions:
            if anchor not in text:
                raise ValueError(f'Missing evidence anchor: {name}: {anchor}')
            cases.append({'id': f'q{len(cases)+1:03}', 'group':name, 'split':'dev' if group_index%2 == 0 else 'test', 'kind':'answerable', 'question':question, 'expected_files':[name+'.md'], 'evidence':[{'file':name+'.md','anchor':anchor}], 'reference_answer':reference, 'label_status':'draft-agent-authored'})
    for i, question in enumerate(NEGATIVE):
        cases.append({'id':f'n{i+1:03}','group':'unanswerable-'+str(i),'split':'dev' if i%2==0 else 'test','kind':'unanswerable','question':question,'expected_files':[],'evidence':[],'reference_answer':'现有资料不足以回答','label_status':'draft-agent-authored'})
    Path('eval/benchmark.jsonl').write_text('\n'.join(json.dumps(c,ensure_ascii=False) for c in cases)+'\n',encoding='utf-8')
    print(f'Validated {len(cases)} draft cases; 64 answerable + 16 unanswerable')


if __name__ == '__main__':
    main()

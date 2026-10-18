# Atlas 示例服务部署手册

此文档是本项目自建的测试样例，不是第三方产品的真实说明。

## 网络配置
Atlas 服务默认监听 8080 端口。通过 PORT 环境变量可以修改监听端口。健康检查路径为 /health。

## 启动条件
运行 Atlas 需要 Python 3.12 和 PostgreSQL 连接地址。启动前设置 DATABASE_URL。数据库不可用时服务启动失败。

## 日志
设置 LOG_LEVEL=DEBUG 开启调试日志。生产环境建议使用 INFO。

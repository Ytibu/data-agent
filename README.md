# 掌柜问数（Data Agent）

掌柜问数面向订单数仓的自然语言查询场景。当前仓库包含元知识构建脚本和 Vue 问数页面。构建脚本整理表、字段、指标及其业务别名，为后续检索提供索引。问数页面通过查询接口展示处理进度、表格结果和错误信息，完整问数流程需要单独提供查询服务。

## 元知识写入哪里

| 存储 | 构建产物 |
| --- | --- |
| MySQL 元数据库 | 表、字段、指标及指标与字段的关系。字段类型和示例取值从 MySQL 数仓读取。 |
| Qdrant | 字段和指标的名称、描述、别名对应的向量，分别写入 `data-agent-column` 和 `data-agent-metric`。 |
| Elasticsearch | 开启 `sync: true` 的字段的去重取值，写入 `data-agent-column` 全文索引。 |

## 本地构建元知识

### 1. 安装 Python 依赖

安装 Python 3.11 和 `uv`，在仓库根目录执行以下命令。

```sh
uv sync --locked
uv run --locked python -m app.scripts.build_meta_knowledge --help
```

### 2. 准备服务与配置

编辑 [conf/app_config.yaml](conf/app_config.yaml)，填写本地或测试环境的连接信息。

| 配置项 | 准备工作 |
| --- | --- |
| `db_dw` | 准备可读取的 MySQL 数仓。使用仓库的示例元知识配置时，需要有 `fact_order`、`dim_region`、`dim_customer`、`dim_product`、`dim_date` 及其配置所列字段。 |
| `db_meta` | 预先创建 MySQL 元数据库，并按 [ORM 模型](app/models/mysql/) 建好 `table_info`、`column_info`、`metric_info`、`column_metric` 四张表。构建脚本使用这些表进行数据写入。 |
| `embedding`、`qdrant` | 准备 Hugging Face 兼容的嵌入服务和可写的 Qdrant。`qdrant.embedding_size` 需与嵌入模型的输出维度一致。 |
| `es` | 准备可写的 Elasticsearch。启用字段取值同步时，创建索引需要 `ik_max_word` 分词器。 |

在 [conf/meta_config.yaml](conf/meta_config.yaml) 中按实际数仓调整 `tables` 和 `metrics`。表和字段名称应与物理库一致，指标通过 `表名.字段名` 引用关联字段，例如 `fact_order.order_amount`。在需要按具体取值检索的字段上设 `sync: true`。真实密码和 API 密钥请保留在本地。

### 3. 执行构建

```sh
uv run --locked python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

构建会更新元数据库，并清理本次处理的字段或指标的过期索引记录。首次运行请使用独立测试库与索引。MySQL 元数据先提交，随后更新外部索引。若中途失败，按日志修复对应服务后重新运行，并确认三个存储中的数据都已更新。

## 启动问数前端

使用 Node.js 20.19+（20.x）或 22.12+，在仓库根目录执行以下命令，然后打开 Vite 输出的本地地址。

```sh
cd date-agent-frontend
npm ci
npm run dev
```

开发服务器默认把 `/api` 转发到 `http://localhost:8000`。联调时，在该地址启动提供 `POST /api/query` 的查询服务，或修改 [Vite 代理配置](date-agent-frontend/vite.config.js) 指向已有服务。页面发送 `{"query":"各地区的销售额是多少？"}`，按空行分隔读取 `data:` JSON 事件，支持 `stage`、`result`（对象数组）和 `error`。

在 `date-agent-frontend/` 执行 `npm run build` 生成 `dist/`，执行 `npm run preview` 可在本地预览构建产物。

## 代码入口

- [app/scripts/build_meta_knowledge.py](app/scripts/build_meta_knowledge.py) 接收元知识配置路径并初始化客户端。
- [app/service/meta_knowledge_service.py](app/service/meta_knowledge_service.py) 编排元数据写入、向量化和索引同步。
- [app/repositories/](app/repositories/) 实现 MySQL、Qdrant 和 Elasticsearch 的数据访问。
- [date-agent-frontend/src/App.vue](date-agent-frontend/src/App.vue) 实现问数界面与流式响应处理。

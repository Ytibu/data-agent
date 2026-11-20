from typing import TypedDict
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class DataAgentContext(TypedDict):
    """ runtime中context数据结构定义，存放静态依赖，操作不同数据库持久层对象"""
    meta_mysql_repository: MetaMysqlRepository #元数据库
    dw_mysql_repository: DWMysqlRepository  # 数据仓库

    embedding_client:HuggingFaceEndpointEmbeddings # 向量服务器客户端
    column_qdrant_repository:ColumnQdrantRepository #字段向量库

    value_es_repository:ValueEsRepository # 字段值索引库
    metric_qdrant_repository:MetricQdrantRepository # 指标向量库

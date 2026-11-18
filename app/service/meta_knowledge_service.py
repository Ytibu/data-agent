from pathlib import Path

from langchain_core.embeddings import Embeddings
from omegaconf import OmegaConf

from app.core.log import logger
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.conf.meta_config import MetaConfig
from app.entities.table_info import TableInfo
from app.entities.column_info import ColumnInfo
from app.models.mysql.metric_info_mysql import MetricInfoMySQL


class MetaKnowledgeService:
    """元知识服务业务层"""

    def __init__(
        self,
        meta_mysql_repository: MetaMysqlRepository,
        dw_mysql_repository: DWMysqlRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        embedding_client: Embeddings,
        value_es_repository: ValueEsRepository,
        metric_qdrant_repository: MetricQdrantRepository,
    ) -> None:
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client = embedding_client
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository

    async def build(self, meta_config_path: Path) -> None:
        context = OmegaConf.load(meta_config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config:MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

        async with self.meta_mysql_repository.session.begin():
            await self._save_table_info_to_meta_db(meta_config)
            metrics = [
                MetricInfoMySQL(
                    id=metric.name,
                    name=metric.name,
                    description=metric.description,
                    relevant_columns=metric.relevant_columns,
                    alias=metric.alias,
                )
                for metric in meta_config.metrics or []
            ]
            await self.meta_mysql_repository.save_metric_infos(metrics)
            for metric in metrics:
                await self.meta_mysql_repository.replace_metric_columns(metric.id, metric.relevant_columns)

        logger.info("元数据已写入 MySQL：{}", meta_config_path)

    async def _save_table_info_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfo]:
        """ 构建持久层保存数据表格信息需要的列表对象，调用meta数据库持久层批量新增"""
        table_infos:list[TableInfo] = []
        column_infos:list[ColumnInfo] = []
        if meta_config.tables:
            for table in meta_config.tables:
                table_info = TableInfo(
                    id=table.name,
                    name=table.name,
                    description=table.description,
                    role=table.role
                )
                table_infos.append(table_info)

                column_type:dict[str,str] = await self.dw_mysql_repository.get_column_types(table_info.name)
                for column in table.columns:
                    if column.name not in column_type:
                        raise ValueError(f"数仓表 {table.name} 中找不到字段 {column.name}")
                    examples:list[str] = await self.dw_mysql_repository.get_column_values(table_info.name, column.name)
                    column_info = ColumnInfo(
                        id = f"{table_info.id}.{column.name}",
                        name=column.name,
                        role=column.role,
                        description=column.description,
                        alias=column.alias,
                        table_id=table_info.id,
                        type=column_type[column.name],
                        examples=examples
                    )
                    column_infos.append(column_info)

        await self.meta_mysql_repository.save_table_infos(table_infos)
        await self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos

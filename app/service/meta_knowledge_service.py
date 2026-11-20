import uuid
from contextlib import aclosing
from dataclasses import asdict
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
from app.entities.metric_info import MetricInfo
from app.models.es.value_info_es import ValueInfoES
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


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

        logger.info("开始构建元知识：{}", meta_config_path)

        context = OmegaConf.load(meta_config_path)
        structured = OmegaConf.structured(MetaConfig)
        meta_config:MetaConfig = OmegaConf.to_object(OmegaConf.merge(structured, context))

        if not (meta_config.tables or meta_config.metrics):
            return

        async with self.meta_mysql_repository.build_lock():
            async with self.meta_mysql_repository.session.begin():
                column_infos = await self._save_table_info_to_meta_db(meta_config) if meta_config.tables else []
                metric_infos = await self._save_metric_info_to_meta_db(meta_config) if meta_config.metrics else []
            logger.info("元数据已写入 MySQL：{}", meta_config_path)

            if column_infos:
                await self._save_index_columns_in_qdrant(column_infos)
                await self._save_value_info_to_es(meta_config, column_infos)
                logger.info("字段取值的全文索引已写入 Elasticsearch")

            if metric_infos:
                await self._save_metric_info_to_qdrant(metric_infos)
                logger.info("指标向量索引已写入 Qdrant")


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

    async def _save_index_columns_in_qdrant(self, column_infos: list[ColumnInfo]) -> None:
        """将字段名称、描述和别名写入 Qdrant 向量索引。"""
        ids = []
        embedding_texts = []
        payloads = []
        point_ids_by_entity: dict[str, list[str]] = {}
        for column_info in column_infos:
            payload = asdict(column_info)
            entity_point_ids = point_ids_by_entity.setdefault(column_info.id, [])
            texts = [column_info.name, column_info.description, *column_info.alias]
            for slot, value in enumerate(texts):
                if not value.strip():
                    continue
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{column_info.id}:{slot}"))
                ids.append(point_id)
                entity_point_ids.append(point_id)
                embedding_texts.append(value)
                payloads.append(payload)

        embeddings = []
        batch_size = 10
        for start in range(0, len(embedding_texts), batch_size):
            batch = embedding_texts[start:start + batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch)
            if len(batch_embeddings) != len(batch):
                raise ValueError(
                    f"向量服务返回 {len(batch_embeddings)} 条向量，当前批次有 {len(batch)} 条文本"
                )
            embeddings.extend(batch_embeddings)

        await self.column_qdrant_repository.ensure_index()
        await self.column_qdrant_repository.upsert_embedding(ids, embeddings, payloads)
        await self.column_qdrant_repository.delete_stale_points(point_ids_by_entity)
        logger.info("已写入 Qdrant 字段向量：{} 条", len(ids))

    async def _save_value_info_to_es(self, meta_config: MetaConfig, column_infos: list[ColumnInfo]) -> None:
        """写入开启同步的字段取值，并清理本次配置中遗留的取值。"""
        # 当前构建以配置中的物理表名作为表 ID；SQL 仍使用明确的物理名称。
        sync_columns = {
            (table.name, column.name): table.name
            for table in meta_config.tables or []
            for column in table.columns
            if column.sync
        }
        if sync_columns:
            await self.value_es_repository.ensure_index()

        sync_run = uuid.uuid4().hex
        for column_info in column_infos:
            table_name = sync_columns.get((column_info.table_id, column_info.name))
            if table_name is None:
                continue
            batches = self.dw_mysql_repository.iter_column_value_batches(
                table_name=table_name,
                column_name=column_info.name,
            )
            async with aclosing(batches):
                async for values in batches:
                    value_infos = [
                        ValueInfoES(
                            id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"{column_info.id}:{value}")),
                            value=value,
                            type=column_info.type,
                            column_id=column_info.id,
                            column_name=column_info.name,
                            table_id=column_info.table_id,
                            table_name=table_name,
                        )
                        for value in values
                    ]
                    await self.value_es_repository.upsert_values(value_infos, sync_run=sync_run)

        await self.value_es_repository.delete_stale_values([column.id for column in column_infos], sync_run)

    async def _save_metric_info_to_meta_db(self, meta_config:MetaConfig) -> list[MetricInfo]:
        """构建持久层保存表格信息，需要让列表对象调用Meta数据库持久层批量新增。"""

        metric_infos: list[MetricInfo] = []

        for metric in meta_config.metrics or []:
            metric_info = MetricInfo(
                id = metric.name,
                name = metric.name,
                description = metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)

        await self.meta_mysql_repository.save_metric_info_to_meta_db(metric_infos)
        for metric_info in metric_infos:
            await self.meta_mysql_repository.replace_metric_columns(metric_info.id, metric_info.relevant_columns)

        return metric_infos

    async def _save_metric_info_to_qdrant(self, metric_infos: list[MetricInfo]) -> None:
        ids: list[str] = []
        embedding_texts: list[str] = []
        payloads: list[MetricInfoQdrant] = []
        point_ids_by_entity: dict[str, list[str]] = {}
        for metric_info in metric_infos:
            payload = MetricInfoQdrant(**asdict(metric_info))
            entity_point_ids = point_ids_by_entity.setdefault(metric_info.id, [])
            for slot, text in enumerate([metric_info.name, metric_info.description, *metric_info.alias]):
                if not text.strip():
                    continue
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{metric_info.id}:{slot}"))
                ids.append(point_id)
                entity_point_ids.append(point_id)
                embedding_texts.append(text)
                payloads.append(payload)

        embeddings = []
        batch_size = 10
        for start in range(0, len(embedding_texts), batch_size):
            batch = embedding_texts[start:start + batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch)
            if len(batch_embeddings) != len(batch):
                raise ValueError(f"向量服务返回 {len(batch_embeddings)} 条向量，当前指标批次有 {len(batch)} 条文本")
            embeddings.extend(batch_embeddings)

        await self.metric_qdrant_repository.ensure_index()
        await self.metric_qdrant_repository.upsert_embeddings(ids, embeddings, payloads)
        await self.metric_qdrant_repository.delete_stale_points(point_ids_by_entity)

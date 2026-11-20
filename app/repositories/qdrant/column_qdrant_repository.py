from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.repositories.qdrant.payload_points import delete_stale_points, ensure_keyword_indexes


class ColumnQdrantRepository:
    collection_name = "data-agent-column"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        """
        确保保存列向量的集合存在
        :return:
        """
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name=self.collection_name,
                # 参数一：向量维度 参数二：相似度算法
                vectors_config=VectorParams(size=app_config.qdrant.embedding_size, distance=Distance.COSINE),
            )

    async def ensure_index(self) -> None:
        """确保字段集合及按字段 ID、表 ID 精确过滤的索引存在。"""
        await self.ensure_collection()
        await ensure_keyword_indexes(self.client, self.collection_name, "id", "table_id")

    async def delete_stale_points(self, point_ids_by_entity: dict[str, list[str]]) -> None:
        await delete_stale_points(self.client, self.collection_name, point_ids_by_entity)

    async def upsert_embedding(self, ids: list[str], embeddings: list[list[float]], payloads: list[ColumnInfoQdrant]):
        """
        保存列信息向量数据到qdrant
        :param ids:
        :param embeddings:
        :param payloads:
        :return:
        """
        zipped = list(zip(ids, embeddings, payloads, strict=True))
        batch_size = 512
        for i in range(0, len(zipped), batch_size):
            batch = zipped[i:i + batch_size]
            points = [PointStruct(
                id=pid,
                vector=embedding,
                payload=payload
            ) for pid, embedding, payload in batch]
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

from elasticsearch import AsyncElasticsearch

from app.models.es.value_info_es import ValueInfoES


class ValueEsRepository:
    es_index_name = "data-agent-column"
    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "column_id": {"type": "keyword"},
            "sync_run": {"type": "keyword"},
        }
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """
        确保保存值数据的索引存在
        :return:
        """
        if await self.client.indices.exists(index=self.es_index_name):
            # 已存在的索引也需要为构建标记建立映射。
            await self.client.indices.put_mapping(
                index=self.es_index_name,
                properties={"sync_run": self.es_index_mappings["properties"]["sync_run"]},
            )
            return
        await self.client.indices.create(
            index=self.es_index_name,
            mappings=self.es_index_mappings,
        )

    async def delete_stale_values(self, column_ids: list[str], sync_run: str) -> None:
        """清理本次配置中的字段未写入本轮标记的文档。"""
        if not column_ids or not await self.client.indices.exists(index=self.es_index_name):
            return

        # delete_by_query 使用搜索快照，先让本轮写入对搜索可见。
        await self.client.indices.refresh(index=self.es_index_name)
        for start in range(0, len(column_ids), 512):
            response = await self.client.delete_by_query(
                index=self.es_index_name,
                query={
                    "bool": {
                        "filter": [{"terms": {"column_id": column_ids[start:start + 512]}}],
                        "must_not": [{"term": {"sync_run": sync_run}}],
                    }
                },
                refresh=True,
            )
            if response["timed_out"] or response["version_conflicts"] or response["failures"]:
                raise RuntimeError(f"Elasticsearch 旧取值清理未完成：{response}")

    async def upsert_values(
        self, value_infos: list[ValueInfoES], batch_size: int = 20, *, sync_run: str | None = None
    ) -> None:
        """
        为值数据添加全文索引
        :param batch_size: 每个请求的文档数
        :param sync_run: 本轮构建标记
        :param value_infos:
        :return:
          {
            "index": {
                "_index": "books"
            }
        },
        {
            "name": "Revelation Space",
            "author": "Alastair Reynolds",
            "release_date": "2000-03-15",
            "page_count": 585
        },
        """
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")

        # 循环遍历批量获取处理
        for i in range(0, len(value_infos), batch_size):
            # 定义集合，组成operations
            operations:list = []
            # 获取批次value数据
            batch_value_infos = value_infos[i:i + batch_size]
            # 构建operations
            for batch_value_info in batch_value_infos:
                # 追加索引指定
                operations.append({"index": {"_index": self.es_index_name, "_id": batch_value_info["id"]}})
                # 追加文档值
                document = dict(batch_value_info)
                if sync_run is not None:
                    document["sync_run"] = sync_run
                operations.append(document)
            response = await self.client.bulk(
                operations=operations
            )
            if response["errors"]:
                failures = [
                    (item["index"].get("_id"), item["index"]["status"])
                    for item in response["items"]
                    if item["index"]["status"] >= 300
                ]
                raise RuntimeError(f"Elasticsearch 批量写入失败（文档 ID、状态码）：{failures}")

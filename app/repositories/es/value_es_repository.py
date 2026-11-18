from elasticsearch import AsyncElasticsearch

from app.models.es.value_info_es import ValueInfoEs


class ValueEsRepository:
    es_index_name = "data_agent_values"
    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """
        确保保存值数据的索引存在
        :return:
        """
        # 判断值存储的索引是否存在
        if not await self.client.indices.exists(index=self.es_index_name):
            # 索引不存在，创建索引
            await self.client.indices.create(
                index=self.es_index_name,
                mappings=self.es_index_mappings
            )

    async def upsert_values(self, value_infos: list[ValueInfoEs], batch_size: int = 20):
        """
        为值数据添加全文索引
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
            operations = []
            # 获取批次value数据
            batch_value_infos = value_infos[i:i + batch_size]
            # 构建operations
            for batch_value_info in batch_value_infos:
                # 追加索引指定
                operations.append({"index": {"_index": self.es_index_name, "_id": batch_value_info["id"]}})
                # 追加文档值
                operations.append(batch_value_info)
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

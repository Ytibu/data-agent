from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, FilterSelector, HasIdCondition, MatchAny, PayloadSchemaType


async def ensure_keyword_indexes(client: AsyncQdrantClient, collection_name: str, *field_names: str) -> None:
    collection = await client.get_collection(collection_name)
    for field_name in field_names:
        existing = collection.payload_schema.get(field_name)
        if existing is None:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
        elif existing.data_type != PayloadSchemaType.KEYWORD:
            raise ValueError(
                f"Qdrant 集合 {collection_name} 的 {field_name} 索引应为 keyword，"
                f"当前为 {existing.data_type.value}"
            )


async def delete_stale_points(
    client: AsyncQdrantClient, collection_name: str, point_ids_by_entity: dict[str, list[str]]
) -> None:
    """只清理本次处理的实体，保留本轮生成的向量点。"""
    entity_ids = list(point_ids_by_entity)
    for start in range(0, len(entity_ids), 128):
        batch = entity_ids[start:start + 128]
        keep_ids = [point_id for entity_id in batch for point_id in point_ids_by_entity[entity_id]]
        await client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="id", match=MatchAny(any=batch))],
                    must_not=[HasIdCondition(has_id=keep_ids)] if keep_ids else None,
                )
            ),
            wait=True,
        )

import asyncio
from argparse import ArgumentParser
from contextlib import AsyncExitStack
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMysqlRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMysqlRepository
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.service.meta_knowledge_service import MetaKnowledgeService


async def build(meta_config_path:Path):
    # 按初始化的逆序释放资源，异常时也会执行全部关闭操作。
    async with AsyncExitStack() as stack:
        # 初始化engine和session工厂
        meta_mysql_client_manager.init()
        stack.push_async_callback(meta_mysql_client_manager.close)
        dw_mysql_client_manager.init()
        stack.push_async_callback(dw_mysql_client_manager.close)
        qdrant_client_manager.init()
        stack.push_async_callback(qdrant_client_manager.close)
        embedding_client_manager.init()
        es_client_manager.init()
        stack.push_async_callback(es_client_manager.close)
        # 创建session
        async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
            # 创建meta_repository
            meta_mysql_repository = MetaMysqlRepository(meta_session)
            # 创建dw_repository
            dw_mysql_repository = DWMysqlRepository(dw_session)
            # 创建qdrant客户端对象
            column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
            # 创建embedding客户端对象
            embedding_client=embedding_client_manager.client
            # 创建ValueEsRepository对象
            value_es_repository=ValueEsRepository(es_client_manager.client)
            # 创建MetricQdrantRepository客户端
            metric_qd_repository = MetricQdrantRepository(qdrant_client_manager.client)
            # 创建service对象
            meta_knowledge_service=MetaKnowledgeService(
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository,
                column_qdrant_repository=column_qdrant_repository,
                embedding_client=embedding_client,
                value_es_repository=value_es_repository,
                metric_qdrant_repository=metric_qd_repository
            )
            # 构建知识库
            await meta_knowledge_service.build(meta_config_path)


if __name__ == '__main__':

    # 创建argparse解析器
    parser = ArgumentParser()

    # 设置解析器参数
    parser.add_argument('-c', '--conf', '--config', required=True, type=Path, help='元知识配置文件路径')
    args = parser.parse_args()
    if not args.conf.is_file():
        parser.error(f"找不到配置文件：{args.conf}")
    asyncio.run(build(args.conf))

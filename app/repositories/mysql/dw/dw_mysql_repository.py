from collections.abc import AsyncGenerator

from sqlalchemy import column, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import quoted_name


class DWMysqlRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """ 根据表名称获取表中所有字段的类型"""
        statement = text("""
            SELECT COLUMN_NAME, COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
        """)
        result = await self.session.execute(statement, {"table_name": table_name})
        return dict(result.tuples().all())


    async def get_column_values(self, table_name: str, column_name: str, limit: int = 10) -> list[str]:
        result = await self.session.execute(self._distinct_column_values(table_name, column_name).limit(limit))
        return [str(value) for value in result.scalars()]

    async def iter_column_value_batches(self, table_name: str, column_name: str) -> AsyncGenerator[list[str], None]:
        """分批读取全部去重取值，供全文索引使用。"""
        statement = self._distinct_column_values(table_name, column_name)
        result = await self.session.stream_scalars(statement.execution_options(yield_per=512))
        try:
            async for batch in result.partitions():
                yield [str(value) for value in batch]
        finally:
            await result.close()

    @staticmethod
    def _distinct_column_values(table_name: str, column_name: str):
        source = table(quoted_name(table_name, True), column(quoted_name(column_name, True)))
        return select(source.c[column_name]).distinct()

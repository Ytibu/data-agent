from dataclasses import asdict

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL

from app.entities.table_info import TableInfo
from app.entities.column_info import ColumnInfo

class MetaMysqlRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _upsert(self, model, rows: list[dict]) -> None:
        if not rows:
            return
        table = model.__table__
        statement = insert(table).values(rows)
        updates = {
            column.key: statement.inserted[column.key]
            for column in table.columns if not column.primary_key
        }
        await self.session.execute(statement.on_duplicate_key_update(**updates))

    async def save_table_infos(self, table_infos: list[TableInfo]):
        await self._upsert(TableInfoMySQL, [asdict(info) for info in table_infos])

    async def save_column_infos(self, column_infos: list[ColumnInfo]):
        await self._upsert(ColumnInfoMySQL, [asdict(info) for info in column_infos])

    async def save_metric_infos(self, metric_infos: list[MetricInfoMySQL]):
        await self._upsert(MetricInfoMySQL, [
            {column.key: getattr(info, column.key) for column in MetricInfoMySQL.__table__.columns}
            for info in metric_infos
        ])

    async def replace_metric_columns(self, metric_id: str, column_ids: list[str]) -> None:
        await self.session.execute(
            delete(ColumnMetricMySQL).where(ColumnMetricMySQL.metric_id == metric_id)
        )
        self.session.add_all([
            ColumnMetricMySQL(metric_id=metric_id, column_id=column_id)
            for column_id in dict.fromkeys(column_ids)
        ])

    async def get_column_info_by_id(self, relevant_column: str) -> ColumnInfoMySQL:
        """
        查询根据当前字段的id查询meta库中的column_info
        :param relevant_column:
        :return:
        """
        return await self.session.get(ColumnInfoMySQL, relevant_column)

    async def get_key_column_by_table_id(self, table_id: str) -> list[ColumnInfoMySQL]:
        """
        根据表的id查询当前表的主键和外键
        :param table_id:
        :return:
        """
        # 定义sql
        sql = """ \
              select * \
              from column_info \
              where table_id = :table_id \
                and role in ('primary_key', 'foreign_key') \
             """
        # 定义返回结构的类型结构
        query = select(ColumnInfoMySQL).from_statement(text(sql))
        # 执行语句
        result = await self.session.execute(query, {"table_id": table_id})
        # 处理结构
        return result.scalars().fetchall()

    async def get_table_info_by_id(self, table_id: str) -> TableInfoMySQL:
        """
        根据表id查询表信息
        :param table_id:
        :return:
        """

        # 查询返回结果
        return await self.session.get(TableInfoMySQL, table_id)

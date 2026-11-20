from dataclasses import asdict

from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.entities.column_metric import ColumnMetric


class ColumnMetricMapper:
    @staticmethod
    def to_entity(model: ColumnMetricMySQL) -> ColumnMetric:
        return ColumnMetric(
            column_id = model.column_id,
            metric_id = model.metric_id
        )

    @staticmethod
    def to_model(entity: ColumnMetric):
        return ColumnMetricMySQL(**asdict(entity))
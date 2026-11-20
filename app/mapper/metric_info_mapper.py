from dataclasses import asdict

from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.entities.metric_info import MetricInfo

class MetricInfoMapper:
    @staticmethod
    def to_entity(model: MetricInfoMySQL) -> MetricInfo:
        return MetricInfo(
            id = model.id,
            name = model.name,
            description = model.description,
            relevant_columns = model.relevant_columns,
            alias = model.alias
        )


    @staticmethod
    def to_model(entity: MetricInfo):
        return MetricInfoMySQL(**asdict(entity))
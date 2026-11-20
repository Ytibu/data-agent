from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def filter_metric(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "过滤指标", "status": "running"})

	try:
		writer({"type": "progress", "step": "过滤指标", "status": "success"})
	except Exception as e:
		logger.error(f"过滤指标发生异常：{e}")
		writer({"type": "progress", "step": "过滤指标", "status": "error"})
		raise
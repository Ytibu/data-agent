from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def filter_table(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "过滤表格", "status": "running"})

	try:
		writer({"type": "progress", "step": "过滤表格", "status": "success"})
	except Exception as e:
		logger.error(f"过滤表格发生异常：{e}")
		writer({"type": "progress", "step": "过滤表格", "status": "error"})
		raise
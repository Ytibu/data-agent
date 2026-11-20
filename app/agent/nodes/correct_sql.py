from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def correct_sql(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "矫正SQL", "status": "running"})

	try:
		writer({"type": "progress", "step": "矫正SQL", "status": "success"})
	except Exception as e:
		logger.error(f"矫正SQL发生异常：{e}")
		writer({"type": "progress", "step": "矫正SQL", "status": "error"})
		raise
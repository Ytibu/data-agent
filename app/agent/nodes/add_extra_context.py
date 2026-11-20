from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def add_extra_context(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "添加额外上下文", "status": "running"})

	try:
		writer({"type": "progress", "step": "添加额外上下文", "status": "success"})
	except Exception as e:
		logger.error(f"添加额外上下文发生异常：{e}")
		writer({"type": "progress", "step": "添加额外上下文", "status": "error"})
		raise
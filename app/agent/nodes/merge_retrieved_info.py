from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def merge_retrieved_info(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "合并召回信息", "status": "running"})

	try:
		writer({"type": "progress", "step": "合并召回信息", "status": "success"})
	except Exception as e:
		logger.error(f"合并召回信息发生异常：{e}")
		writer({"type": "progress", "step": "合并召回信息", "status": "error"})
		raise
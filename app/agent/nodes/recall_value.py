from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def recall_value(state:DataAgentState, runtime:Runtime[DataAgentContext]):
	writer = runtime.stream_writer
	writer({"type": "progress", "step": "召回字段取值", "status": "running"})

	try:
		writer({"type": "progress", "step": "召回字段取值", "status": "success"})
	except Exception as e:
		logger.error(f"召回字段取值发生异常：{e}")
		writer({"type": "progress", "step": "召回字段取值", "status": "error"})
		raise
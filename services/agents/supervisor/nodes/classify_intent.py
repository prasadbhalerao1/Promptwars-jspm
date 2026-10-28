from services.agents.supervisor.state import SupervisorState
from services.agents.supervisor.tools.classifier_llm import classify_intent


async def run(state: SupervisorState) -> dict:
    result = await classify_intent(state["raw_request"])
    return {"intent": result["intent"]}

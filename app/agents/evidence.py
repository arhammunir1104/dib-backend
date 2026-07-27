# app/agents/evidence.py
from app.agents.base import BaseAgent
from app.rag.pipeline import RAGPipeline
from app.logging.setup import logger

class EvidenceAgent(BaseAgent):
    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag = rag_pipeline

    async def run(self, state: dict) -> dict:
        observations = state.get("extracted_observations", [])
        logger.info(f"Evidence Agent: checking {len(observations)} observations")
        for obs in observations:
            for field in ["observation_summary", "action_plan_summary", "current_target_date"]:
                value = obs.get(field, "")
                if value:
                    query = f"{obs['observation_number']} {field}"
                    chunks = self.rag.retrieve_context(query, top_k=1)
                    if chunks:
                        obs[f"{field}_evidence"] = chunks[0]["text"]
                        logger.debug(f"Evidence found for {obs['observation_number']}.{field}")
        state["evidence_completed"] = True
        return state
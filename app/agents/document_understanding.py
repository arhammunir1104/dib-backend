from app.agents.base import BaseAgent
from app.services.llm_client import get_llm_client
from app.logging.setup import logger
import json

class DocumentUnderstandingAgent(BaseAgent):
    async def run(self, state: dict) -> dict:
        full_text = state.get("document_text", "")
        logger.info("Running Document Understanding Agent")
        prompt = f"""
        You are an AI assistant at Dubai Islamic Bank.
        Analyze the following bank circular text and produce a JSON with:
        - "document_summary": a concise summary of the circular.
        - "sections": a list of sections (title and brief description).
        - "key_terminology": important banking terms used.

        Circular text:
        {full_text[:10000]}
        """
        messages = [{"role": "system", "content": "You output only valid JSON."},
                    {"role": "user", "content": prompt}]
        client = get_llm_client()
        response = await client.generate(messages, temperature=0.1)

        # Clean code fences if present
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean[:-3]
        try:
            understanding = json.loads(clean)
        except:
            understanding = {"error": "Failed to parse", "raw": response}
        state["document_understanding"] = understanding
        return state
import json
from app.agents.base import BaseAgent
from app.services.llm_client import get_llm_client
from app.logging.setup import logger

class VerificationAgent(BaseAgent):
    async def run(self, state: dict) -> dict:
        observations = state.get("extracted_observations", [])
        if not observations:
            return state
        client = get_llm_client()
        logger.info(f"Verification Agent: verifying {len(observations)} observations")
        for obs in observations:
            num = obs.get("observation_number")
            for field in ["observation_summary", "action_plan_summary", "current_target_date"]:
                value = obs.get(field)
                evidence = obs.get(f"{field}_evidence", "")
                if not value or not evidence:
                    obs[f"{field}_verified"] = False
                    obs[f"{field}_verify_reason"] = "Missing value or evidence"
                    continue
                prompt = (
                    f"Verify if this extracted value '{value}' for field '{field}' "
                    f"is supported by evidence: '{evidence[:200]}'. "
                    "Return JSON: {'verified': true/false, 'reason': ''}"
                )
                try:
                    resp = await client.generate(
                        [{"role": "user", "content": prompt}],
                        temperature=0.0,
                        max_tokens=256
                    )
                    clean = resp.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[-1].rstrip("```")
                    if not clean:
                        raise ValueError("Empty response")
                    result = json.loads(clean)
                except Exception as e:
                    logger.warning(f"Verification failed for {num}.{field}: {e}")
                    result = {"verified": False, "reason": str(e)}
                obs[f"{field}_verified"] = result.get("verified", False)
                obs[f"{field}_verify_reason"] = result.get("reason", "")
        state["extracted_observations"] = observations
        return state
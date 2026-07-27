import json
import asyncio
import hashlib
import re
from app.agents.base import BaseAgent
from app.services.llm_client import get_llm_client
from app.logging.setup import logger


# ============================================================
#  COMPACT PROMPT – all essential rules + example
# ============================================================


COMPACT_PROMPT = (
    "You are a Big 4 internal auditor generating a Risk Control Matrix from an SBP circular.\n"
    "Extract up to 10 controls from the text below. Return a JSON array of objects with these EXACT keys:\n"
    "clause_ref, section, sub_section, sbp_reference, page_number, process, sub_process, "
    "risk_category, risk_description, control_objective, control_description, control_type, "
    "control_nature, frequency, control_owner, audit_test_procedure, evidence_required, "
    "recommendation, severity, source_text, remarks.\n\n"
    "CRITICAL RULES:\n"
    "- Derive controls ONLY from the provided text. Do NOT invent.\n"
    "- Split independent requirements into separate controls (e.g., customer identification, document verification, biometric verification, sanctions screening must each be separate).\n"
    "- Use professional Big 4 audit language. Fill EVERY field with detailed, multi‑sentence content.\n"
    "- For clause_ref, use ONLY proper structured numbers like '1.1.a', '2.3.1.b', 'C.3', 'Table-A'. Do NOT use bare numbers like '1' or '5'.\n"
    "- Use compact JSON (no line breaks) to save space.\n"
    "- Return ONLY the JSON array. NO markdown, NO extra text.\n\n"
    "Example (compact):\n"
    '[{"clause_ref":"C.3","section":"Account Opening","sub_section":"Document Submission","sbp_reference":"Consolidated Onboarding","page_number":"3","process":"Customer Onboarding","sub_process":"Document Collection","risk_category":"Operational Risk","risk_description":"Failure to provide alternative channels may delay onboarding.","control_objective":"To ensure multiple convenient channels for document submission.","control_description":"SBP REs shall enable alternative channels like social apps, email, etc.","control_type":"Detective","control_nature":"Manual","frequency":"Ongoing","control_owner":"Operations / Digital Banking","audit_test_procedure":"Review enabled channels and verify they function.","evidence_required":"List of channels, customer communications.","recommendation":"Implement at least email and portal upload.","severity":"Medium","source_text":"SBP REs shall enable alternative channels...","remarks":"Facilitates customers."}]'
)

REQUIRED_KEYS = [
    "clause_ref", "section", "sub_section", "sbp_reference", "page_number",
    "process", "sub_process", "risk_category", "risk_description",
    "control_objective", "control_description", "control_type", "control_nature",
    "frequency", "control_owner", "audit_test_procedure",
    "evidence_required", "recommendation", "severity",
    "source_text", "remarks"
]

class RCMAgent(BaseAgent):
    async def run(self, state: dict) -> dict:
        full_text = state.get("document_text", "")
        client = get_llm_client()

        logger.info("Starting RCM extraction – compact prompt, up to 10 controls per chunk")

        # Chunks of 5000 chars (≈1250 tokens) + compact prompt (~350 tokens) = ~1600 tokens input.
        # With max_tokens=4096, total stays well under 6000.
        chunk_size = 5000
        overlap = 500
        chunks = []
        start = 0
        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunks.append(full_text[start:end])
            start += chunk_size - overlap

        logger.info(f"Processing {len(chunks)} chunks")

        all_controls = []
        seen_hashes = set()

        for idx, chunk in enumerate(chunks):
            logger.info(f"=== Chunk {idx+1}/{len(chunks)} ({len(chunk)} chars) ===")

            user_msg = f"CIRCULAR TEXT:\n{chunk}\n\nJSON OUTPUT (compact, up to 10 new controls):"
            messages = [
                {"role": "system", "content": COMPACT_PROMPT},
                {"role": "user", "content": user_msg}
            ]

            try:
                response = await client.generate(messages, temperature=0.0, max_tokens=4096)
                logger.info(f"  Response length: {len(response)} chars")
            except Exception as e:
                logger.warning(f"  LLM call failed: {e}")
                if "rate_limit" in str(e).lower() or "413" in str(e):
                    await asyncio.sleep(20)
                continue

            # Clean and parse
            clean = response.strip()
            if clean.startswith("```"): clean = clean.split("\n", 1)[-1].rstrip("```")
            try:
                new_controls = json.loads(clean)
            except json.JSONDecodeError as e:
                logger.warning(f"  JSON parse error: {e}")
                pos = e.pos
                truncated = clean[:pos].rstrip()
                if truncated.endswith(","):
                    truncated = truncated[:-1].rstrip()
                if truncated and not truncated.endswith(']'):
                    truncated += ']'
                try:
                    new_controls = json.loads(truncated)
                except:
                    new_controls = []

            if not isinstance(new_controls, list):
                continue

            added = 0
            for ctrl in new_controls:
                clause = ctrl.get("clause_ref", "").strip()
                if not clause or not re.match(r'^[A-Za-z0-9\.\-\_\(\)\[\]\/\s]+$', clause):
                    continue
                if re.match(r'^\d+$', clause) or re.match(r'^[a-z]\)$', clause, re.I):
                    continue

                uid = (clause + ctrl.get("control_requirement", ""))[:100]
                ctrl_hash = hashlib.md5(uid.encode()).hexdigest()
                if ctrl_hash not in seen_hashes:
                    seen_hashes.add(ctrl_hash)
                    for key in REQUIRED_KEYS:
                        ctrl.setdefault(key, "")
                    all_controls.append(ctrl)
                    added += 1
            logger.info(f"  -> received {len(new_controls)} controls, added {added} unique")

            await asyncio.sleep(0.3)

        # Number them
        for i, ctrl in enumerate(all_controls, start=1):
            ctrl["no"] = str(i)

        logger.info(f"Final total unique controls: {len(all_controls)}")
        if all_controls:
            clause_refs = sorted(set(c["clause_ref"] for c in all_controls))
            logger.info("All clause_refs:\n" + "\n".join(clause_refs))

        state["rcm_controls"] = all_controls
        return state
import json
from app.services.llm_client import get_llm_client
from app.logging.setup import logger

# Full compact prompt – same as before
ROW_COMPLETION_PROMPT = (
    "You are a Senior Banking Internal Auditor, Risk Consultant, and RCM Expert with 20+ years of Big 4 experience.\n"
    "You are given a Control Requirement, its Clause Reference, and the surrounding regulatory text from an SBP circular.\n"
    "Your task is to generate the missing RCM fields for that ONE control.\n\n"
    "Return a JSON object with these exact keys (fill every field with detailed, professional audit language):\n"
    "risk_category, risk, risk_description, control_objective, control_description, control_type, control_nature, "
    "frequency, control_owner, key_control, audit_test_procedure, expected_evidence, testing_method, "
    "recommendation, severity, automation_possible, remarks.\n\n"
    "RULES:\n"
    "- Derive everything from the provided regulatory text and the Control Requirement.\n"
    "- Use professional Big 4 audit language. Avoid generic phrases like 'Ensure...' or 'System should...'.\n"
    "- For risk_category use one of: Operational Risk, Compliance Risk, Information Security, Technology Risk, Business Continuity, Disaster Recovery, Governance, Vendor Risk, Access Management.\n"
    "- For control_type: Preventive, Detective, Corrective, Directive, Compensating.\n"
    "- For control_nature: Manual, Automated, Hybrid.\n"
    "- For frequency: Continuous, Daily, Weekly, Monthly, Quarterly, Semi-Annual, Annual, Event Driven, As Required.\n"
    "- For severity: Low, Medium, High, Critical.\n"
    "- For key_control: true if failure would significantly affect regulatory compliance or operational resilience.\n"
    "- For automation_possible: true if the control could reasonably be monitored/executed through technology.\n"
    "- Provide detailed, multi-sentence audit_test_procedure and expected_evidence.\n"
    "- testing_method: Inspection, Observation, Inquiry, Reperformance, Sampling, Walkthrough, Configuration Review, System Verification, or Combination.\n"
    "- Return ONLY the JSON object. No extra text.\n\n"
    "Example (compact):\n"
    '{"risk_category":"Operational Risk","risk":"Failure to verify customer identity prior to onboarding","risk_description":"Failure to verify customer identity may lead to fraudulent accounts, AML violations, and regulatory penalties.","control_objective":"To ensure only valid customer identities are accepted prior to account opening.","control_description":"Customer identity shall be verified through NADRA Biometric Verification before account activation.","control_type":"Preventive","control_nature":"Automated","frequency":"Per Customer","control_owner":"Operations / Digital Banking","key_control":true,"audit_test_procedure":"Select a sample of 25 accounts opened during the audit period. Verify that NADRA BV was performed and successful before account activation. Review system logs and evidence.","expected_evidence":"NADRA BV logs, account opening forms, system screenshots","testing_method":"Sampling, Inspection","recommendation":"Implement automated BV for all digital onboarding.","severity":"High","automation_possible":true,"remarks":""}'
)

class RCMCompletionAgent:
    async def complete_row(self, clause_ref: str, control_req: str, context_text: str) -> dict:
        client = get_llm_client()

        user_msg = (
            f"Clause Reference: {clause_ref}\n"
            f"Control Requirement: {control_req}\n\n"
            f"Regulatory Context (from the circular):\n{context_text[:3000]}\n\n"
            "Generate the missing RCM fields as a JSON object."
        )
        messages = [
            {"role": "system", "content": ROW_COMPLETION_PROMPT},
            {"role": "user", "content": user_msg}
        ]

        try:
            response = await client.generate(messages, temperature=0.0, max_tokens=2048)
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rstrip("```")
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON for clause {clause_ref}: {e}")
            raise Exception(f"AI response for clause '{clause_ref}' could not be processed. Please retry.") from e
        except Exception as e:
            logger.error(f"Failed to complete row for clause {clause_ref}: {e}")
            raise Exception(f"Unable to complete clause '{clause_ref}' due to a temporary service issue. Please retry later.") from e
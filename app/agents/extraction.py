from app import agents
from app import agents
from app import agents
from app.agents import base
import json
import re
from app.agents.base import BaseAgent
from app.services.llm_client import get_llm_client
from app.rag.pipeline import RAGPipeline
from app.logging.setup import logger

class ExtractionAgent(BaseAgent):
    def __init__(self, rag_pipeline: RAGPipeline):
        self.rag = rag_pipeline

    async def run(self, state: dict) -> dict:
     try:
        full_text = state.get("document_text", "")
        report_issue_date = state.get("report_issue_date", "")
        client = get_llm_client()

        # 1. Remove TOC
        toc_pattern = re.compile(r'TABLE OF CONTENTS.*?(?=\n\d+\.\d+\s)', re.IGNORECASE | re.DOTALL)
        clean_text = toc_pattern.sub('', full_text, count=1)
        if len(clean_text) < 500:
            clean_text = full_text

        # 2. Find all four‑level observation numbers
        obs_numbers = list(set(re.findall(r'\b(2\.\d+\.\d+\.\d+)\b', clean_text)))
        obs_numbers = [n for n in obs_numbers if re.search(rf'^\s*{re.escape(n)}\s', clean_text, re.MULTILINE)]
        obs_numbers.sort(key=lambda x: tuple(int(part) for part in x.split('.')))

        logger.info(f"Found {len(obs_numbers)} unique observation numbers: {obs_numbers}")

        if not obs_numbers:
            state["extracted_observations"] = []
            return state

        # 3. Extract observation_summary and action_plan_summary via regex
        observations = []
        for obs_num in obs_numbers:
            obs_pattern = re.compile(
                rf'^\s*{re.escape(obs_num)}\s*(.*?)(?=\n\s*(?:Root Cause|Risk|Recommendation|Management\s*Action\s*Plan|Action Owner|Target Date|2\.\d+\.\d+\.\d+\s|2\.\d+\.\d+\s|Low\b|Medium\b|High\b|Moderate\b|Critical\b)|\n\s*\n|\Z)',
                re.DOTALL | re.MULTILINE
            )
            obs_match = obs_pattern.search(clean_text)
            obs_summary = obs_match.group(1).strip() if obs_match else ""

            # --- Trim everything after the first appendix reference ---
            # This removes any tables, root-cause sections, etc. that follow the appendix.
            appendix_match = re.search(r'\(Appendix[\s\-]+\d+\.\d+\)', obs_summary)
            if appendix_match:
                # Keep everything up to and including the appendix marker
                obs_summary = obs_summary[:appendix_match.end()].strip()
            

                        
            action_items = []   

            # Locate the management action section: search for "Action Owner" after the observation
            obs_start = clean_text.find(obs_num)
            action_section_start = clean_text.find("Action Owner", obs_start + len(obs_num))
            if action_section_start == -1:
                action_section_start = clean_text.find("Target Date", obs_start + len(obs_num))

            if action_section_start != -1:
                # Take a window of 3000 chars from the start of action table
                action_block = clean_text[action_section_start:action_section_start+3000]

                # Find all action plan numbers that start with the observation number + optional letter
                # e.g., 2.1.1.2, 2.1.1.2a, 2.1.1.2b
                apn_pattern = re.compile(
                    rf'({re.escape(obs_num)}[a-z]?)\s*[–\-]?\s*(.*?)(?=\n\s*(?:{re.escape(obs_num)}[a-z]?|Action Owner|Target Date|\d+\.\d+\.\d+\.\d+)|\Z)',
                    re.DOTALL
                )
                for apn_match in apn_pattern.finditer(action_block):
                    apn_num = apn_match.group(1)
                    apn_desc = apn_match.group(2).strip()
                    # Clean up leading dash/bullet
                    apn_desc = re.sub(r'^[–\-\s]+', '', apn_desc)
                    action_items.append({
                        "number": apn_num,
                        "summary": f"{apn_num} {apn_desc}" if not apn_desc.startswith(apn_num) else apn_desc
                    })

            # If no suffixed action plans found, fall back to original single action plan
            if not action_items:
                first_pos = clean_text.find(obs_num)
                second_pos = clean_text.find(obs_num, first_pos + len(obs_num))
                if second_pos != -1:
                    action_pattern = re.compile(
                        rf'{re.escape(obs_num)}\s*[–\-]?\s*(.*?)(?=\n\s*\d+\.\d+\.\d+\.\d+\s|\n\s*Action Owner|\n\s*Target Date|\n\s*\n|\Z)',
                        re.DOTALL
                    )
                    action_match = action_pattern.search(clean_text, second_pos)
                    if action_match:
                        apn_desc = action_match.group(1).strip()
                        action_items.append({
                            "number": obs_num,
                            "summary": f"{obs_num} {apn_desc}" if not apn_desc.startswith(obs_num) else apn_desc
                        })

            # Now create one observation record for each action plan
            if action_items:
                for ap in action_items:
                    observations.append({
                        "observation_number": obs_num,
                        "observation_summary": obs_summary,
                        "action_plan_summary": ap["summary"],
                        "action_plan_number": ap["number"],   # for enrichment mapping
                        "action_owner": "",
                        "current_target_date": "",
                    })
            else:
                # No action plan found – still record the observation with empty action fields
                observations.append({
                    "observation_number": obs_num,
                    "observation_summary": obs_summary,
                    "action_plan_summary": "",
                    "action_plan_number": obs_num,
                    "action_owner": "",
                    "current_target_date": "",
                })

        logger.info(f"Regex extracted {len(observations)} observations.")
        logger.info("Sample regex output:\n" + json.dumps(observations[:3], indent=2))

        # 4. Get report_code and report_name from LLM (first 2000 chars)
        report_code = ""
        report_name = ""
        try:
            header_text = clean_text[:2000]
            prompt = f"Extract report_code and report_name from this audit report header. Return JSON: {{\"report_code\":\"...\",\"report_name\":\"...\"}}\n\n{header_text}"
            resp = await client.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=256
            )
            clean_resp = resp.strip()
            if clean_resp.startswith("```"):
                clean_resp = clean_resp.split("\n", 1)[-1].rstrip("```")
            info = json.loads(clean_resp)
            report_code = info.get("report_code", "")
            report_name = info.get("report_name", "")
            logger.info(f"Report code: {report_code}, Report name: {report_name}")
        except Exception as e:
            logger.error(f"Failed to extract report header info: {e}")

        # 5. Enrich with auxiliary fields per major section
        section_pattern = re.compile(r'^(2\.\d+)\s', re.MULTILINE)
        section_starts = [(m.start(), m.group(1)) for m in section_pattern.finditer(clean_text)]
        major_sections = []
        if section_starts:
            for i, (start, heading) in enumerate(section_starts):
                end = section_starts[i+1][0] if i+1 < len(section_starts) else len(clean_text)
                major_sections.append((heading, clean_text[start:end]))
        else:
            major_sections = [("all", clean_text)]

        for heading, section_text in major_sections:
            section_obs = [obs for obs in observations if obs["observation_number"] in section_text]
            if not section_obs:
                continue

            obs_nums_str = ", ".join([o["action_plan_number"] for o in section_obs])

                        # --- Extract section title and subtitle from section_text itself ---
            # Section title: the first line that matches the major heading (e.g., "2.1 Business Continuity Plan...")
            title_match = re.match(r'^\s*(\d+\.\d+\s+.+)', section_text, re.MULTILINE)
            sec_title = title_match.group(1).strip() if title_match else heading  # fallback to heading

            # Section subtitle: the first line that matches a three‑level number (e.g., "2.1.1 Weaknesses...")
            sub_match = re.search(r'^\s*(2\.\d+\.\d+\s+.+)', section_text, re.MULTILINE)
            sec_subtitle = sub_match.group(1).strip() if sub_match else ""



            prompt = f"""
            For action plans {obs_nums_str} in this section, extract:
            - department, action_owner, current_target_date (from Management Action Plan)
            - rating (High/Medium/Low from section header)

            Return JSON array, each object with "action_plan_number" and these fields. Use empty string if missing.
            Section text (first 6000 chars):
            {section_text[:6000]}
            """
            messages = [
                {"role": "system", "content": "You are an extraction engine. Output only JSON array."},
                {"role": "user", "content": prompt}
            ]
            try:
                logger.info(f"LLM enrichment for section {heading} ({len(section_obs)} observations)")
                response = await client.generate(messages, temperature=0.0, max_tokens=1024)
                clean = response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1].rstrip("```")
                aux_list = json.loads(clean)



                for aux in aux_list:
                    apn = aux.get("action_plan_number")
                    for obs in section_obs:
                        if obs.get("action_plan_number") == apn:
                            obs["department"] = aux.get("department", "")
                            obs["action_owner"] = aux.get("action_owner", "")
                            obs["current_target_date"] = aux.get("current_target_date", "")
                            obs["rating"] = aux.get("rating", "")
                            obs["section_title"] = sec_title
                            obs["section_subtitle"] = sec_subtitle
                            break


            except Exception as e:
                logger.error(f"LLM enrichment failed for section {heading}: {e}")

        # 6. Add report_code, report_name and final defaults
        for obs in observations:
            obs["report_code"] = report_code
            obs["report_name"] = report_name
            for field in ["observation_summary", "action_plan_summary", "department",
                          "action_owner", "current_target_date", "rating", "section_title",
                          "section_subtitle"]:
                obs.setdefault(field, "")

        # 7. Static fields and date logic
        for i, obs in enumerate(observations, start=1):
            obs["S.No."] = str(i)
            obs["Authority"] = "Internal Audit"
            obs["Group Head"] = "Amir Ali"
            obs["Cycle"] = ""
            obs["Unique Observation No."] = ""
            obs["Sub Department / Area"] = obs.get("department", "")
            obs["Observation Insertion Date"] = report_issue_date
            obs["Report Date"] = report_issue_date
            tgt = str(obs.get("current_target_date", "")).lower()
            if any(w in tgt for w in ["closed", "completed", "closure"]):
                obs["Reporting Status"] = "Closed"
                obs["Closure Date"] = report_issue_date
                obs["current_target_date"] = report_issue_date
            else:
                obs["Reporting Status"] = "Open"
                obs["Closure Date"] = ""
            obs["original_target_date"] = obs["current_target_date"]
            obs["observation_summary"] = f"{obs['observation_number']} {obs['observation_summary']}"

        logger.info(f"Final dataset: {len(observations)} observations.")
        logger.info("Extracted JSON before verification:\n" + json.dumps(observations, indent=2))

        state["extracted_observations"] = observations
        return state

     except Exception as e:
        logger.error(f"Extraction agent failed completely: {e}", exc_info=True)
        state["extracted_observations"] = []
        return state



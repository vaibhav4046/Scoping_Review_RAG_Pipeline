"""LLM-based screening service."""

import logging

from app.ai.llm_client import llm_client
from app.ai.prompts.screening import SCREENING_SYSTEM_PROMPT, build_screening_prompt
from app.schemas.screening import ScreeningDecision

logger = logging.getLogger(__name__)


class ScreeningService:
    """Handles LLM-based title/abstract screening."""

    async def screen_study(
        self,
        title: str,
        abstract: str | None,
        inclusion_criteria: str,
        exclusion_criteria: str,
    ) -> ScreeningDecision:
        """Screen a single study using the primary LLM."""
        prompt = build_screening_prompt(
            title=title,
            abstract=abstract or "",
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
        )

        try:
            result = await llm_client.primary_generate_json(
                prompt=prompt,
                system_prompt=SCREENING_SYSTEM_PROMPT,
            )

            # Validate through Pydantic
            decision = ScreeningDecision(**result)

            # Safety check: if abstract is missing, force uncertain
            if not abstract or abstract.strip() == "":
                if decision.decision != "uncertain":
                    logger.warning(f"Overriding decision to 'uncertain' — abstract missing for: {title[:80]}")
                    decision = ScreeningDecision(
                        decision="uncertain",
                        rationale="Abstract not available. Cannot make a reliable screening decision without reviewing the abstract.",
                        confidence=0.1,
                    )

            return decision

        except Exception as e:
            logger.error(f"Screening failed for '{title[:80]}': {e}")
            # Fail-safe: return uncertain
            return ScreeningDecision(
                decision="uncertain",
                rationale=f"Screening failed due to a processing error: {str(e)}",
                confidence=0.0,
            )


screening_service = ScreeningService()

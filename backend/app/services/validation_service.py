"""Cross-LLM validation service."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.validation import VALIDATION_SYSTEM_PROMPT, build_validation_prompt
from app.schemas.validation import ValidationResult
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)


class ValidationService:
    """Cross-LLM validation of PICO extractions."""

    async def validate_extraction(
        self,
        db: AsyncSession,
        study_id: str,
        title: str,
        original_extraction: dict,
        has_embeddings: bool = False,
    ) -> ValidationResult:
        """Validate an extraction using a second LLM."""
        try:
            # Get text context (same chunks used for original extraction)
            if has_embeddings:
                chunks = await rag_service.retrieve_pico_context(db, study_id)
            else:
                chunks = [original_extraction.get("_abstract", "No text available")]

            prompt = build_validation_prompt(
                title=title,
                text_chunks=chunks,
                original_extraction=original_extraction,
            )

            # Use the VALIDATOR model (different from primary)
            result = await llm_client.validator_generate_json(
                prompt=prompt,
                system_prompt=VALIDATION_SYSTEM_PROMPT,
            )

            # Parse validation result
            validation = self._parse_validation(result)
            return validation

        except Exception as e:
            logger.error(f"Validation failed for study {study_id}: {e}")
            return ValidationResult(
                agreement_score=0.0,
                field_agreements={},
                discrepancies={},
                validator_extractions={},
                needs_human_review=True,
            )

    def _parse_validation(self, result: dict) -> ValidationResult:
        """Parse and normalize the validation result."""
        field_agreements = result.get("field_agreements", {})
        discrepancies = result.get("discrepancies", {})
        independent = result.get("independent_extraction", {})

        # Calculate agreement score
        if field_agreements:
            agreed = sum(1 for v in field_agreements.values() if v)
            total = len(field_agreements)
            agreement_score = agreed / total if total > 0 else 0.0
        else:
            agreement_score = result.get("agreement_score", 0.0)

        needs_review = (
            agreement_score < 0.75
            or result.get("needs_human_review", False)
            or len(discrepancies) >= 3
        )

        return ValidationResult(
            agreement_score=round(agreement_score, 3),
            field_agreements=field_agreements,
            discrepancies=discrepancies,
            validator_extractions=independent,
            needs_human_review=needs_review,
        )

    def compare_fields(
        self, original: dict, validated: dict, fields: list[str]
    ) -> dict[str, bool]:
        """Field-by-field semantic comparison."""
        agreements = {}
        for field in fields:
            orig_val = original.get(field, "Not Reported").strip().lower()
            val_val = validated.get(field, "Not Reported").strip().lower()

            # Both "Not Reported" = agreement
            if orig_val == "not reported" and val_val == "not reported":
                agreements[field] = True
            elif orig_val == "not reported" or val_val == "not reported":
                agreements[field] = False
            else:
                # Check if values are semantically similar (simple substring check)
                agreements[field] = (
                    orig_val in val_val
                    or val_val in orig_val
                    or orig_val == val_val
                )
        return agreements


validation_service = ValidationService()

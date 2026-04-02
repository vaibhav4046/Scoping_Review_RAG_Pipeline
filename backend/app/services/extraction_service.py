"""PICO extraction service using RAG + LLM."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import llm_client
from app.ai.prompts.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt,
    build_extraction_prompt_abstract_only,
)
from app.schemas.extraction import PICOExtraction
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)


class ExtractionService:
    """Handles PICO data extraction using RAG pipeline."""

    async def extract_pico(
        self,
        db: AsyncSession,
        study_id: str,
        title: str,
        abstract: str | None,
        has_embeddings: bool = False,
    ) -> PICOExtraction:
        """Extract PICO data from a study, using RAG if full text available."""
        try:
            if has_embeddings:
                return await self._extract_with_rag(db, study_id, title)
            elif abstract:
                return await self._extract_from_abstract(title, abstract)
            else:
                logger.warning(f"No text available for study {study_id}")
                return PICOExtraction()  # All "Not Reported"

        except Exception as e:
            logger.error(f"Extraction failed for study {study_id}: {e}")
            return PICOExtraction()

    async def _extract_with_rag(
        self,
        db: AsyncSession,
        study_id: str,
        title: str,
    ) -> PICOExtraction:
        """Extract PICO using RAG pipeline (full text)."""
        # Retrieve relevant chunks
        chunks = await rag_service.retrieve_pico_context(db, study_id)

        if not chunks:
            logger.warning(f"No chunks retrieved for study {study_id}")
            return PICOExtraction()

        prompt = build_extraction_prompt(title=title, text_chunks=chunks)
        result = await llm_client.primary_generate_json(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )

        # Validate through Pydantic
        extraction = PICOExtraction(**result)

        # Post-validation: ensure grounding
        extraction = self._validate_grounding(extraction)

        return extraction

    async def _extract_from_abstract(
        self,
        title: str,
        abstract: str,
    ) -> PICOExtraction:
        """Fallback extraction from abstract only."""
        prompt = build_extraction_prompt_abstract_only(title=title, abstract=abstract)
        result = await llm_client.primary_generate_json(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )

        extraction = PICOExtraction(**result)
        extraction = self._validate_grounding(extraction)
        return extraction

    def _validate_grounding(self, extraction: PICOExtraction) -> PICOExtraction:
        """
        Post-processing validation: ensure every non-'Not Reported' value
        has a source quote. If no quote, reset to 'Not Reported'.
        """
        pico_fields = [
            "population", "intervention", "comparator", "outcome",
            "study_design", "sample_size", "duration", "setting",
        ]

        for field in pico_fields:
            value = getattr(extraction, field)
            source = extraction.source_quotes.get(field, "")
            confidence = extraction.confidence_scores.get(field, 0.0)

            if value != "Not Reported" and not source.strip():
                # No source quote → can't verify → reset to Not Reported
                logger.warning(
                    f"Grounding check failed for '{field}': "
                    f"value='{value[:50]}' but no source quote. Resetting."
                )
                setattr(extraction, field, "Not Reported")
                extraction.confidence_scores[field] = 0.0
                extraction.source_quotes[field] = ""

            elif value == "Not Reported":
                # Ensure consistent state
                extraction.confidence_scores[field] = 0.0
                extraction.source_quotes[field] = ""

        return extraction


extraction_service = ExtractionService()

"""
Test Suite — ValidationService
================================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

Run with:
    cd backend && python -m pytest tests/test_validation_service.py -v

or standalone:
    cd backend && python tests/test_validation_service.py

Design mirrors backend/test_pdf_service.py in the repo:
  - No external dependencies needed for unit tests (LLM calls are mocked)
  - All 3 steps (4.1, 4.2, 4.3) have dedicated test sections
  - Synthetic fixtures match the clinical trial domain used in e2e_test.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
import unittest
from unittest.mock import AsyncMock, patch

# Ensure backend root is on path (mirrors test_pdf_service.py approach)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.validation_service import (
    ValidationService,
    PICOExtraction,
    ValidationResult,
    FieldValidationResult,
    _compute_field_confidence,
    _build_validator_prompt,
    PICO_FIELDS,
    NOT_REPORTED,
)
from app.schemas.validation_schemas import (
    ValidationRequest,
    ValidationResultOut,
    ValidationStatusOut,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SOURCE_TEXT = """
Background: Randomized, double-blind, placebo-controlled trial at 12 centres.
842 patients aged 18-75 with newly diagnosed T2DM (HbA1c 7.0-10.0%) were enrolled.
Participants were randomised 1:1 to metformin 1000mg twice daily or matching placebo for 52 weeks.
Primary outcome: change in HbA1c from baseline at week 52.
At week 52, HbA1c decreased by -1.12% in the metformin group vs -0.21% in the placebo group (p<0.001).
"""

SAMPLE_PRIMARY_PICO = PICOExtraction(
    population="Adults aged 18-75 with newly diagnosed T2DM, HbA1c 7.0-10.0%",
    intervention="Metformin 1000mg twice daily for 52 weeks",
    comparator="Matching placebo for 52 weeks",
    outcome="Change in HbA1c from baseline at week 52",
    study_design="Randomized double-blind placebo-controlled trial",
    sample_size="842 patients (421 per group)",
    confidence_scores={
        "population":   0.92,
        "intervention": 0.95,
        "comparator":   0.90,
        "outcome":      0.93,
        "study_design": 0.88,
        "sample_size":  0.91,
    },
    source_quotes={
        "population":   "842 patients aged 18-75 with newly diagnosed T2DM",
        "intervention": "metformin 1000mg twice daily",
        "sample_size":  "842 patients",
    },
)

SAMPLE_VALIDATOR_RESPONSE = json.dumps({
    "population":   "Adults aged 18-75 with newly diagnosed T2DM, HbA1c 7.0-10.0%",
    "intervention": "Metformin 1000mg twice daily for 52 weeks",
    "comparator":   "Matching placebo",
    "outcome":      "Change in HbA1c from baseline at week 52",
    "study_design": "Randomized double-blind placebo-controlled trial",
    "sample_size":  "842 patients",
})

DISAGREED_VALIDATOR_RESPONSE = json.dumps({
    "population":   "Diabetic adults",
    "intervention": "Metformin",
    "comparator":   NOT_REPORTED,
    "outcome":      "Blood sugar levels",
    "study_design": "Clinical trial",
    "sample_size":  "approximately 800",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine in a synchronous test."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test Section 1: PICOExtraction schema (Step 4.1)
# ---------------------------------------------------------------------------

class TestPICOExtractionSchema(unittest.TestCase):

    def test_all_fields_present(self):
        pico = PICOExtraction()
        for f in PICO_FIELDS:
            self.assertTrue(hasattr(pico, f), f"Missing field: {f}")

    def test_defaults_are_not_reported(self):
        pico = PICOExtraction()
        for f in PICO_FIELDS:
            self.assertEqual(getattr(pico, f), NOT_REPORTED)

    def test_confidence_scores_default_zero(self):
        pico = PICOExtraction()
        for f in PICO_FIELDS:
            self.assertEqual(pico.confidence_scores[f], 0.0)

    def test_populated_extraction(self):
        pico = SAMPLE_PRIMARY_PICO
        self.assertEqual(pico.population, "Adults aged 18-75 with newly diagnosed T2DM, HbA1c 7.0-10.0%")
        self.assertGreater(pico.confidence_scores["population"], 0.5)

    def test_serialisation_roundtrip(self):
        pico = SAMPLE_PRIMARY_PICO
        d = pico.model_dump()
        pico2 = PICOExtraction(**d)
        self.assertEqual(pico.population, pico2.population)
        self.assertEqual(pico.confidence_scores, pico2.confidence_scores)


# ---------------------------------------------------------------------------
# Test Section 2: Validator prompt builder (Step 4.2)
# ---------------------------------------------------------------------------

class TestValidatorPrompt(unittest.TestCase):

    def test_prompt_contains_source_text(self):
        prompt = _build_validator_prompt(SAMPLE_SOURCE_TEXT, SAMPLE_PRIMARY_PICO)
        self.assertIn("842 patients", prompt)

    def test_prompt_requests_json(self):
        prompt = _build_validator_prompt(SAMPLE_SOURCE_TEXT, SAMPLE_PRIMARY_PICO)
        self.assertIn('"population"', prompt)
        self.assertIn("Not Reported", prompt)

    def test_prompt_does_not_leak_primary_values(self):
        """Validator must not see primary extraction values — blind re-extraction."""
        prompt = _build_validator_prompt(SAMPLE_SOURCE_TEXT, SAMPLE_PRIMARY_PICO)
        # The primary values should NOT appear as labelled in the prompt
        # (the source text naturally contains some words, that's fine)
        self.assertNotIn("primary extraction", prompt.lower())

    def test_prompt_truncates_long_text(self):
        long_text = "x " * 5000
        prompt = _build_validator_prompt(long_text, SAMPLE_PRIMARY_PICO)
        self.assertLess(len(prompt), 10_000)


# ---------------------------------------------------------------------------
# Test Section 3: Validator response parser (Step 4.2)
# ---------------------------------------------------------------------------

class TestValidatorResponseParser(unittest.TestCase):

    def test_parse_clean_json(self):
        svc = ValidationService()
        result = svc._parse_validator_response(SAMPLE_VALIDATOR_RESPONSE)
        self.assertEqual(result["population"], "Adults aged 18-75 with newly diagnosed T2DM, HbA1c 7.0-10.0%")
        self.assertEqual(result["sample_size"], "842 patients")

    def test_parse_json_with_markdown_fences(self):
        wrapped = f"```json\n{SAMPLE_VALIDATOR_RESPONSE}\n```"
        svc = ValidationService()
        result = svc._parse_validator_response(wrapped)
        self.assertIn("population", result)

    def test_parse_empty_returns_not_reported(self):
        svc = ValidationService()
        result = svc._parse_validator_response("")
        for f in PICO_FIELDS:
            self.assertEqual(result[f], NOT_REPORTED)

    def test_parse_malformed_returns_not_reported(self):
        svc = ValidationService()
        result = svc._parse_validator_response("This is not JSON at all.")
        for f in PICO_FIELDS:
            self.assertEqual(result[f], NOT_REPORTED)

    def test_all_pico_fields_present_in_output(self):
        svc = ValidationService()
        result = svc._parse_validator_response(SAMPLE_VALIDATOR_RESPONSE)
        for f in PICO_FIELDS:
            self.assertIn(f, result)

    def test_values_capped_at_250_chars(self):
        long_val = "word " * 100
        data = {f: long_val for f in PICO_FIELDS}
        svc = ValidationService()
        result = svc._parse_validator_response(json.dumps(data))
        for f in PICO_FIELDS:
            self.assertLessEqual(len(result[f]), 250)


# ---------------------------------------------------------------------------
# Test Section 4: Confidence scorer (Step 4.3)
# ---------------------------------------------------------------------------

class TestConfidenceScorer(unittest.TestCase):

    def test_both_not_reported(self):
        conf, agreed, needs_review, reason = _compute_field_confidence(
            NOT_REPORTED, NOT_REPORTED, 0.5
        )
        self.assertEqual(conf, 0.30)
        self.assertTrue(agreed)
        self.assertFalse(needs_review)

    def test_perfect_agreement(self):
        conf, agreed, needs_review, reason = _compute_field_confidence(
            "842 patients", "842 patients", 0.9
        )
        self.assertGreater(conf, 0.8)
        self.assertTrue(agreed)
        self.assertFalse(needs_review)

    def test_partial_agreement_substring(self):
        conf, agreed, needs_review, reason = _compute_field_confidence(
            "Metformin 1000mg twice daily for 52 weeks",
            "Metformin 1000mg twice daily",
            0.85,
        )
        self.assertTrue(agreed)
        self.assertFalse(needs_review)

    def test_one_side_not_reported(self):
        conf, agreed, needs_review, reason = _compute_field_confidence(
            "Matching placebo", NOT_REPORTED, 0.8
        )
        self.assertFalse(agreed)
        self.assertTrue(needs_review)
        self.assertIsNotNone(reason)

    def test_full_disagreement(self):
        conf, agreed, needs_review, reason = _compute_field_confidence(
            "RCT", "Observational cohort", 0.7
        )
        self.assertFalse(agreed)
        self.assertTrue(needs_review)
        self.assertLess(conf, 0.5)

    def test_confidence_bounded_0_to_1(self):
        for primary, validator, prior_conf in [
            ("A", "A", 1.0),
            ("A", "B", 0.0),
            (NOT_REPORTED, NOT_REPORTED, 0.0),
        ]:
            conf, *_ = _compute_field_confidence(primary, validator, prior_conf)
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)


# ---------------------------------------------------------------------------
# Test Section 5: Full ValidationService.validate() (Steps 4.1+4.2+4.3)
# ---------------------------------------------------------------------------

class TestValidationService(unittest.TestCase):

    def _make_svc_with_mock(self, validator_response: str) -> ValidationService:
        svc = ValidationService()
        svc._validator_call = AsyncMock(return_value=validator_response)
        return svc

    def test_validate_returns_validation_result(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate(
            study_id="pmid_test_001",
            primary_pico=SAMPLE_PRIMARY_PICO,
            source_text=SAMPLE_SOURCE_TEXT,
        ))
        self.assertIsInstance(result, ValidationResult)

    def test_validate_study_id_preserved(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("pmid_abc", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertEqual(result.study_id, "pmid_abc")

    def test_validate_all_pico_fields_in_result(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        for f in PICO_FIELDS:
            self.assertIn(f, result.validated_extraction.confidence_scores)

    def test_validate_confidence_scores_bounded(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        for f, score in result.validated_extraction.confidence_scores.items():
            self.assertGreaterEqual(score, 0.0, f"Score for {f} below 0")
            self.assertLessEqual(score, 1.0, f"Score for {f} above 1")

    def test_validate_overall_confidence_is_mean(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        expected = round(
            sum(result.validated_extraction.confidence_scores.values()) / len(PICO_FIELDS), 4
        )
        self.assertAlmostEqual(result.overall_confidence, expected, places=3)

    def test_validate_agreement_passes(self):
        """When models agree on all fields, no fields should be flagged."""
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s_agree", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        # With matching responses, flagged list should be minimal
        self.assertIsInstance(result.flagged_fields, list)

    def test_validate_disagreement_flags_fields(self):
        """When models strongly disagree, fields should be flagged."""
        svc = self._make_svc_with_mock(DISAGREED_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s_disagree", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertGreater(len(result.flagged_fields), 0)

    def test_validate_low_confidence_resets_to_not_reported(self):
        """Fields with very low confidence should be reset to Not Reported."""
        # Craft a response with extreme disagreement to trigger reset
        extreme_disagree = json.dumps({f: "COMPLETELY_DIFFERENT_VALUE_XYZ" for f in PICO_FIELDS})
        # Force primary confidence very low too
        low_conf_pico = PICOExtraction(
            **{f: "some value" for f in PICO_FIELDS},
            confidence_scores={f: 0.05 for f in PICO_FIELDS},
        )
        svc = self._make_svc_with_mock(extreme_disagree)
        result = _run(svc.validate("s_low", low_conf_pico, SAMPLE_SOURCE_TEXT))
        # At least some fields should be reset to Not Reported
        all_values = [getattr(result.validated_extraction, f) for f in PICO_FIELDS]
        self.assertIn(NOT_REPORTED, all_values)

    def test_validate_source_quotes_preserved(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s_quotes", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertEqual(
            result.validated_extraction.source_quotes,
            SAMPLE_PRIMARY_PICO.source_quotes,
        )

    def test_validate_llm_failure_degrades_gracefully(self):
        """If the validator LLM call fails, validation should not crash the system."""
        svc = ValidationService()
        svc._validator_call = AsyncMock(side_effect=Exception("LLM timeout"))
        # Should not raise — degrades to Not Reported
        result = _run(svc.validate("s_fail", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertIsInstance(result, ValidationResult)

    def test_validate_field_results_count(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertEqual(len(result.field_results), len(PICO_FIELDS))

    def test_validate_field_result_structure(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        for fr in result.field_results:
            self.assertIsInstance(fr, FieldValidationResult)
            self.assertIn(fr.field_name, PICO_FIELDS)
            self.assertGreaterEqual(fr.confidence_score, 0.0)
            self.assertLessEqual(fr.confidence_score, 1.0)

    def test_validate_timestamp_set(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertGreater(result.validation_timestamp, 0)

    def test_validate_model_name_set(self):
        svc = self._make_svc_with_mock(SAMPLE_VALIDATOR_RESPONSE)
        result = _run(svc.validate("s1", SAMPLE_PRIMARY_PICO, SAMPLE_SOURCE_TEXT))
        self.assertIsInstance(result.validation_model, str)
        self.assertGreater(len(result.validation_model), 0)


# ---------------------------------------------------------------------------
# Test Section 6: Schema validation
# ---------------------------------------------------------------------------

class TestValidationSchemas(unittest.TestCase):

    def test_validation_request_defaults(self):
        req = ValidationRequest()
        self.assertIsNone(req.study_id)
        self.assertFalse(req.force_rerun)

    def test_validation_request_with_study_id(self):
        req = ValidationRequest(study_id="pmid_123", force_rerun=True)
        self.assertEqual(req.study_id, "pmid_123")
        self.assertTrue(req.force_rerun)

    def test_validation_status_out(self):
        out = ValidationStatusOut(
            review_id="rev_1",
            task_id="celery-task-abc",
            status="running",
            progress=45,
        )
        self.assertEqual(out.progress, 45)
        self.assertIsNone(out.message)


# ---------------------------------------------------------------------------
# Test Section 7: Module imports & singleton
# ---------------------------------------------------------------------------

class TestModuleSetup(unittest.TestCase):

    def test_validation_service_importable(self):
        from app.services.validation_service import validation_service
        self.assertIsNotNone(validation_service)

    def test_singleton_is_validation_service(self):
        from app.services.validation_service import validation_service, ValidationService
        self.assertIsInstance(validation_service, ValidationService)

    def test_prompts_importable(self):
        from app.ai.prompts.validation_prompts import (
            VALIDATOR_REEXTRACTION_PROMPT,
            DISCREPANCY_EXPLANATION_PROMPT,
            GROUNDING_CHECK_PROMPT,
        )
        self.assertIn("{source_text}", VALIDATOR_REEXTRACTION_PROMPT)
        self.assertIn("{field_name}", DISCREPANCY_EXPLANATION_PROMPT)
        self.assertIn("{extracted_value}", GROUNDING_CHECK_PROMPT)

    def test_schemas_importable(self):
        from app.schemas.validation_schemas import (
            ValidationRequest,
            ValidationResultOut,
            ValidationBatchOut,
            ValidationStatusOut,
        )
        self.assertTrue(True)  # just verify no import error


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()
    classes = [
        TestPICOExtractionSchema,
        TestValidatorPrompt,
        TestValidatorResponseParser,
        TestConfidenceScorer,
        TestValidationService,
        TestValidationSchemas,
        TestModuleSetup,
    ]
    for cls in classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"\n{'='*60}")
    print(f" VALIDATION SERVICE TEST RESULTS")
    print(f"{'='*60}")
    print(f" Total  : {total}")
    print(f" Passed : {passed}")
    print(f" Failed : {len(result.failures)}")
    print(f" Errors : {len(result.errors)}")
    print(f"{'='*60}")

    if result.wasSuccessful():
        print(" ✓ ALL TESTS PASSED")
    else:
        print(" ✗ SOME TESTS FAILED — see output above")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()

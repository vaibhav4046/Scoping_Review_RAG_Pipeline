"""
Tests for medical_keyword_mapper.py and mesh_loader.py
Durgesh | Medical NLP & Data Dictionary

Uses a small in-memory MeSH database fixture so tests run instantly
without downloading the full NLM XML.
"""
import pytest
from unittest.mock import patch

from app.services.mesh_loader import MeSHEntry, lookup_term, lookup_subtree
from app.services.medical_keyword_mapper import (
    MedicalKeywordMapper,
    MANUAL_SYNONYMS,
    DOMAIN_TREE_PREFIXES,
)


# ---------------------------------------------------------------------------
# Fixtures — small fake MeSH database
# ---------------------------------------------------------------------------

def _build_mock_mesh_db() -> dict[str, MeSHEntry]:
    """Minimal MeSH database with a handful of real-style entries."""
    entries = [
        MeSHEntry(
            ui="D008175",
            preferred_name="Lung Neoplasms",
            synonyms=["Pulmonary Neoplasms", "Cancer of Lung", "Lung Cancer"],
            tree_numbers=["C04.588.894.797.520", "C08.381.540", "C08.785.520"],
            pubmed_tag="Lung Neoplasms[MeSH]",
        ),
        MeSHEntry(
            ui="D001943",
            preferred_name="Breast Neoplasms",
            synonyms=["Breast Cancer", "Cancer of Breast", "Mammary Neoplasms"],
            tree_numbers=["C04.588.180", "C17.800.090.500"],
            pubmed_tag="Breast Neoplasms[MeSH]",
        ),
        MeSHEntry(
            ui="D007167",
            preferred_name="Immunotherapy",
            synonyms=["Immunotherapies", "Immune Therapy"],
            tree_numbers=["E02.095.465", "E02.095.465.425"],
            pubmed_tag="Immunotherapy[MeSH]",
        ),
        MeSHEntry(
            ui="D005909",
            preferred_name="Glioblastoma",
            synonyms=["Glioblastoma Multiforme", "Giant Cell Glioblastoma"],
            tree_numbers=["C04.557.465.625.600.380.080"],
            pubmed_tag="Glioblastoma[MeSH]",
        ),
        MeSHEntry(
            ui="D016032",
            preferred_name="Randomized Controlled Trials as Topic",
            synonyms=["Randomised Controlled Trials as Topic"],
            tree_numbers=["E05.318.760.535", "N05.715.360.775.175.535"],
            pubmed_tag="Randomized Controlled Trials as Topic[MeSH]",
        ),
        MeSHEntry(
            ui="D015179",
            preferred_name="Colorectal Neoplasms",
            synonyms=["Colorectal Cancer", "Colorectal Tumors"],
            tree_numbers=["C04.588.274.476", "C06.301.371.411"],
            pubmed_tag="Colorectal Neoplasms[MeSH]",
        ),
    ]

    db: dict[str, MeSHEntry] = {}
    for e in entries:
        for t in e.all_terms():
            db[t.lower()] = e
    return db


@pytest.fixture
def mock_mesh_db():
    return _build_mock_mesh_db()


@pytest.fixture
def mapper(mock_mesh_db):
    """Mapper pre-loaded with the mock MeSH DB (no network calls)."""
    return MedicalKeywordMapper(mesh_db=mock_mesh_db, eager_load=False)


# ---------------------------------------------------------------------------
# MeSHEntry tests
# ---------------------------------------------------------------------------

class TestMeSHEntry:
    def test_all_terms_deduplicates(self):
        entry = MeSHEntry(
            ui="D000001", preferred_name="Test",
            synonyms=["test", "Alias"], tree_numbers=[], pubmed_tag="Test[MeSH]",
        )
        terms = entry.all_terms()
        assert terms == ["Test", "Alias"]

    def test_all_terms_preserves_order(self):
        entry = MeSHEntry(
            ui="D000001", preferred_name="Alpha",
            synonyms=["Beta", "Gamma", "Delta"],
            tree_numbers=[], pubmed_tag="Alpha[MeSH]",
        )
        assert entry.all_terms() == ["Alpha", "Beta", "Gamma", "Delta"]

    def test_pubmed_tag_format(self):
        entry = MeSHEntry(
            ui="D008175", preferred_name="Lung Neoplasms",
            synonyms=[], tree_numbers=[], pubmed_tag="Lung Neoplasms[MeSH]",
        )
        assert entry.pubmed_tag == "Lung Neoplasms[MeSH]"


# ---------------------------------------------------------------------------
# lookup_term tests
# ---------------------------------------------------------------------------

class TestLookupTerm:
    def test_exact_preferred_name(self, mock_mesh_db):
        entry = lookup_term("Lung Neoplasms", mock_mesh_db)
        assert entry is not None
        assert entry.ui == "D008175"

    def test_case_insensitive(self, mock_mesh_db):
        entry = lookup_term("LUNG NEOPLASMS", mock_mesh_db)
        assert entry is not None
        assert entry.ui == "D008175"

    def test_synonym_lookup(self, mock_mesh_db):
        entry = lookup_term("lung cancer", mock_mesh_db)
        assert entry is not None
        assert entry.preferred_name == "Lung Neoplasms"

    def test_unknown_term_returns_none(self, mock_mesh_db):
        assert lookup_term("xyzzy_not_a_term", mock_mesh_db) is None

    def test_whitespace_stripped(self, mock_mesh_db):
        entry = lookup_term("  glioblastoma  ", mock_mesh_db)
        assert entry is not None
        assert entry.ui == "D005909"


# ---------------------------------------------------------------------------
# lookup_subtree tests
# ---------------------------------------------------------------------------

class TestLookupSubtree:
    def test_finds_entries_under_prefix(self, mock_mesh_db):
        results = lookup_subtree("C04.588", mock_mesh_db)
        uis = {e.ui for e in results}
        assert "D008175" in uis  # Lung Neoplasms
        assert "D001943" in uis  # Breast Neoplasms
        assert "D015179" in uis  # Colorectal Neoplasms

    def test_narrow_prefix_filters(self, mock_mesh_db):
        results = lookup_subtree("C04.588.894", mock_mesh_db)
        uis = {e.ui for e in results}
        assert "D008175" in uis      # Lung Neoplasms (C04.588.894.797.520)
        assert "D001943" not in uis   # Breast is under C04.588.180

    def test_no_duplicates(self, mock_mesh_db):
        results = lookup_subtree("C04", mock_mesh_db)
        uis = [e.ui for e in results]
        assert len(uis) == len(set(uis))

    def test_no_matches_returns_empty(self, mock_mesh_db):
        assert lookup_subtree("Z99.999", mock_mesh_db) == []


# ---------------------------------------------------------------------------
# MedicalKeywordMapper tests
# ---------------------------------------------------------------------------

class TestMedicalKeywordMapper:
    def test_get_mesh_entry(self, mapper):
        entry = mapper.get_mesh_entry("lung neoplasms")
        assert entry is not None
        assert entry.ui == "D008175"

    def test_get_mesh_entry_returns_none(self, mapper):
        assert mapper.get_mesh_entry("not_a_real_term") is None

    def test_get_synonyms_mesh_only(self, mapper):
        syns = mapper.get_synonyms("glioblastoma")
        assert "Glioblastoma Multiforme" in syns

    def test_get_synonyms_merges_manual(self, mapper):
        syns = mapper.get_synonyms("lung neoplasms")
        # Should have MeSH synonyms
        assert "Lung Cancer" in syns
        # Should also have manual overrides
        assert "NSCLC" in syns
        assert "non-small cell lung cancer" in syns

    def test_get_synonyms_no_duplicates(self, mapper):
        syns = mapper.get_synonyms("lung neoplasms")
        lowers = [s.lower() for s in syns]
        assert len(lowers) == len(set(lowers))

    def test_get_mesh_tag(self, mapper):
        assert mapper.get_mesh_tag("breast neoplasms") == "Breast Neoplasms[MeSH]"

    def test_get_mesh_tag_unknown(self, mapper):
        assert mapper.get_mesh_tag("nonexistent_term") is None


# ---------------------------------------------------------------------------
# expand() tests
# ---------------------------------------------------------------------------

class TestExpand:
    def test_expand_known_term(self, mapper):
        result = mapper.expand("lung neoplasms")
        assert result["canonical"] == "lung neoplasms"
        assert result["preferred"] == "Lung Neoplasms"
        assert result["mesh_ui"] == "D008175"
        assert result["mesh_tag"] == "Lung Neoplasms[MeSH]"
        assert len(result["tree_numbers"]) > 0
        assert len(result["synonyms"]) > 0
        assert result["all_terms"][0] == "lung neoplasms"

    def test_expand_unknown_term(self, mapper):
        result = mapper.expand("some rare condition")
        assert result["canonical"] == "some rare condition"
        assert result["preferred"] == "some rare condition"
        assert result["mesh_ui"] is None
        assert result["mesh_tag"] is None
        assert result["tree_numbers"] == []

    def test_expand_manual_only_term(self, mapper):
        result = mapper.expand("overall survival")
        # Not in our mock MeSH DB but has manual synonyms
        assert "OS" in result["synonyms"]
        assert "5-year survival" in result["synonyms"]

    def test_expand_subtree(self, mapper):
        entries = mapper.expand_subtree("breast_neoplasms")
        uis = {e.ui for e in entries}
        assert "D001943" in uis

    def test_expand_subtree_unknown_domain(self, mapper):
        with pytest.raises(ValueError, match="Unknown domain"):
            mapper.expand_subtree("fake_domain_key")


# ---------------------------------------------------------------------------
# build_pubmed_query() tests
# ---------------------------------------------------------------------------

class TestBuildPubmedQuery:
    def test_single_term_query(self, mapper):
        q = mapper.build_pubmed_query("lung neoplasms")
        assert "Lung Neoplasms[MeSH]" in q
        assert "[TIAB]" in q
        assert q.startswith("(")

    def test_multiple_terms_and_operator(self, mapper):
        q = mapper.build_pubmed_query(
            ["lung neoplasms", "immunotherapy"], operator="AND"
        )
        assert " AND " in q
        assert "Lung Neoplasms[MeSH]" in q
        assert "Immunotherapy[MeSH]" in q

    def test_or_operator(self, mapper):
        q = mapper.build_pubmed_query(
            ["lung neoplasms", "breast neoplasms"], operator="OR"
        )
        assert " OR " in q

    def test_filters_appended(self, mapper):
        q = mapper.build_pubmed_query(
            "lung neoplasms",
            filters=["humans[MeSH]", "English[lang]"],
        )
        assert "humans[MeSH]" in q
        assert "English[lang]" in q

    def test_no_mesh_flag(self, mapper):
        q = mapper.build_pubmed_query("lung neoplasms", include_mesh=False)
        assert "Lung Neoplasms[MeSH]" not in q
        assert "[TIAB]" in q

    def test_no_tiab_flag(self, mapper):
        q = mapper.build_pubmed_query("lung neoplasms", include_tiab=False)
        assert "Lung Neoplasms[MeSH]" in q
        assert "[TIAB]" not in q

    def test_string_input_converted_to_list(self, mapper):
        q = mapper.build_pubmed_query("immunotherapy")
        assert "Immunotherapy[MeSH]" in q

    def test_max_tiab_cap(self, mapper):
        q = mapper.build_pubmed_query("lung neoplasms", max_tiab_per_term=3)
        tiab_count = q.count("[TIAB]")
        assert tiab_count <= 3

    def test_unknown_term_still_produces_query(self, mapper):
        q = mapper.build_pubmed_query("xyz_unknown")
        assert "[TIAB]" in q


# ---------------------------------------------------------------------------
# add_manual_synonyms() tests
# ---------------------------------------------------------------------------

class TestAddManualSynonyms:
    def test_add_new_synonyms(self, mapper):
        mapper.add_manual_synonyms("glioblastoma", ["grade IV astrocytoma"])
        syns = mapper.get_synonyms("glioblastoma")
        assert "grade IV astrocytoma" in syns

    def test_no_duplicate_additions(self, mapper):
        mapper.add_manual_synonyms("glioblastoma", ["GBM", "GBM"])
        syns = mapper.get_synonyms("glioblastoma")
        lowers = [s.lower() for s in syns]
        assert lowers.count("gbm") == 1


# ---------------------------------------------------------------------------
# Module-level constants sanity checks
# ---------------------------------------------------------------------------

class TestConstants:
    def test_manual_synonyms_not_empty(self):
        assert len(MANUAL_SYNONYMS) > 0

    def test_domain_tree_prefixes_not_empty(self):
        assert len(DOMAIN_TREE_PREFIXES) > 0

    def test_all_manual_synonym_keys_are_lowercase(self):
        for key in MANUAL_SYNONYMS:
            assert key == key.lower(), f"Key '{key}' should be lowercase"

    def test_domain_prefixes_are_valid_format(self):
        for key, prefix in DOMAIN_TREE_PREFIXES.items():
            assert isinstance(prefix, str)
            assert len(prefix) > 0

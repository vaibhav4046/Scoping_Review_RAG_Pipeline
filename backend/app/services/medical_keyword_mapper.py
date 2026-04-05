"""
Step 3.2 — Medical Keyword Mapper  (MeSH-powered edition)
Durgesh | Medical NLP & Data Dictionary

Synonyms and MeSH headings are now sourced at runtime from the official
NLM MeSH Descriptor XML hosted at:

  https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml

This replaces the hardcoded synonym dictionary in the previous version.
A local JSON cache (~8 MB) is written to MESH_CACHE_PATH (default /tmp/)
and refreshed every 30 days.

Backward compatibility: build_pubmed_query() and expand() have the same
signatures as before, so Harmeet's search module needs no changes.
"""

from __future__ import annotations

import logging
from typing import Union

from app.services.mesh_loader import MeSHEntry, load_mesh, lookup_term

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Manual overrides / project-specific supplements
# These are MERGED with MeSH data — use for abbreviations, brand names,
# or domain terms that MeSH doesn't carry (e.g. "NSCLC", "TNBC", "CAR-T").
# ---------------------------------------------------------------------------

MANUAL_SYNONYMS: dict[str, list[str]] = {
    "lung neoplasms": [
        "NSCLC", "non-small cell lung cancer",
        "SCLC", "small cell lung cancer",
        "bronchogenic carcinoma",
    ],
    "breast neoplasms": [
        "TNBC", "triple-negative breast cancer",
        "HER2-positive breast cancer", "ER-positive breast cancer",
    ],
    "immunotherapy": [
        "PD-1 inhibitor", "PD-L1 inhibitor", "CTLA-4 inhibitor",
        "nivolumab", "pembrolizumab", "atezolizumab",
        "CAR-T therapy", "CAR-T cell therapy",
    ],
    "glioblastoma": ["GBM", "glioblastoma multiforme", "grade IV glioma"],
    "leukemia":     ["AML", "ALL", "CLL", "CML"],
    "colorectal neoplasms": ["CRC", "colorectal cancer", "colon cancer", "rectal cancer"],
    "radiotherapy":  ["EBRT", "IMRT", "SBRT", "SRS", "stereotactic body radiotherapy"],
    "progression-free survival": ["PFS", "TTP", "time to progression"],
    "overall survival": ["OS", "5-year survival", "all-cause mortality"],
    "disease-free survival": ["DFS", "RFS", "relapse-free survival"],
    "objective response rate": ["ORR", "tumour response", "tumor response"],
    "randomized controlled trial": ["RCT", "randomised controlled trial"],
    "meta-analysis as topic": ["systematic review", "NMA", "network meta-analysis", "pooled analysis"],
}

# MeSH tree-number prefixes for common scoping-review domains.
# Used by expand_subtree() to pull an entire MeSH category at once.
DOMAIN_TREE_PREFIXES: dict[str, str] = {
    "all_neoplasms":          "C04",
    "malignant_neoplasms":    "C04.588",
    "lung_neoplasms":         "C04.588.894.797",
    "breast_neoplasms":       "C04.588.180",
    "colorectal_neoplasms":   "C04.588.274.476",
    "leukemias":              "C04.557.337",
    "antineoplastic_agents":  "D",    # broad - use sparingly
    "immunologic_techniques": "E05.478",
    "clinical_trials":        "E05.318.760",
    "survival_analysis":      "E05.318.760.750",
}


# ---------------------------------------------------------------------------
# Core mapper
# ---------------------------------------------------------------------------

class MedicalKeywordMapper:
    """
    Keyword mapper backed by live NLM MeSH data.

    On first use the MeSH XML (~50 MB) is downloaded from NLM and cached
    locally as a compact JSON. All subsequent startups use the cache.

    Parameters
    ----------
    mesh_db      : pre-loaded MeSH lookup (pass to reuse across mappers)
    eager_load   : if True, load MeSH immediately; otherwise on first use
    manual_synonyms : project-specific term extensions (merged with MeSH)
    """

    def __init__(
        self,
        mesh_db: dict[str, MeSHEntry] | None = None,
        eager_load: bool = True,
        manual_synonyms: dict[str, list[str]] = MANUAL_SYNONYMS,
    ):
        self._mesh_db: dict[str, MeSHEntry] | None = mesh_db
        self._manual: dict[str, list[str]] = {
            k.lower(): v for k, v in manual_synonyms.items()
        }
        if eager_load and self._mesh_db is None:
            self._ensure_loaded()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._mesh_db is None:
            log.info("Loading MeSH database ...")
            self._mesh_db = load_mesh()

    # ------------------------------------------------------------------
    # Public look-ups
    # ------------------------------------------------------------------

    def get_mesh_entry(self, term: str) -> MeSHEntry | None:
        """Return the full MeSHEntry for a term, or None."""
        self._ensure_loaded()
        return lookup_term(term, self._mesh_db)

    def get_synonyms(self, term: str) -> list[str]:
        """
        All synonyms for a term - MeSH synonyms + manual overrides,
        with duplicates removed.
        """
        self._ensure_loaded()
        synonyms: list[str] = []

        entry = lookup_term(term, self._mesh_db)
        if entry:
            synonyms.extend(entry.synonyms)

        manual = self._manual.get(term.strip().lower(), [])
        for s in manual:
            if s.lower() not in {x.lower() for x in synonyms}:
                synonyms.append(s)

        return synonyms

    def get_mesh_tag(self, term: str) -> str | None:
        """
        Return the PubMed-ready MeSH tag, e.g. "Lung Neoplasms[MeSH]".
        """
        self._ensure_loaded()
        entry = lookup_term(term, self._mesh_db)
        return entry.pubmed_tag if entry else None

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def expand(self, term: str) -> dict:
        """
        Full expansion of a single term.

        Returns
        -------
        dict with keys:
            canonical    - normalised input string
            preferred    - MeSH preferred name (or canonical if not found)
            mesh_ui      - MeSH Unique Identifier (e.g. "D008175")
            mesh_tag     - PubMed-ready tag (e.g. "Lung Neoplasms[MeSH]")
            tree_numbers - MeSH tree numbers (empty list if not found)
            synonyms     - all aliases (MeSH + manual)
            all_terms    - canonical + synonyms combined
        """
        self._ensure_loaded()
        canonical = term.strip().lower()
        synonyms  = self.get_synonyms(canonical)
        entry     = lookup_term(canonical, self._mesh_db)

        return {
            "canonical":    canonical,
            "preferred":    entry.preferred_name if entry else term.strip(),
            "mesh_ui":      entry.ui if entry else None,
            "mesh_tag":     entry.pubmed_tag if entry else None,
            "tree_numbers": entry.tree_numbers if entry else [],
            "synonyms":     synonyms,
            "all_terms":    [canonical] + synonyms,
        }

    def expand_subtree(self, domain_key: str) -> list[MeSHEntry]:
        """
        Return all MeSH entries under a named domain tree prefix.

        e.g. expand_subtree("lung_neoplasms") returns all lung neoplasm descriptors.
        """
        from app.services.mesh_loader import lookup_subtree
        self._ensure_loaded()
        prefix = DOMAIN_TREE_PREFIXES.get(domain_key)
        if not prefix:
            raise ValueError(
                f"Unknown domain '{domain_key}'. "
                f"Available: {list(DOMAIN_TREE_PREFIXES.keys())}"
            )
        return lookup_subtree(prefix, self._mesh_db)

    # ------------------------------------------------------------------
    # PubMed query builder
    # ------------------------------------------------------------------

    def build_pubmed_query(
        self,
        terms: Union[str, list[str]],
        filters: list[str] | None = None,
        operator: str = "AND",
        include_mesh: bool = True,
        include_tiab: bool = True,
        max_tiab_per_term: int = 15,
    ) -> str:
        """
        Build a PubMed-ready Boolean query string.

        Parameters
        ----------
        terms            : one term or a list of terms
        filters          : e.g. ["humans[MeSH]", "English[lang]", "2015:2025[dp]"]
        operator         : "AND" (default) or "OR" to join term groups
        include_mesh     : include the MeSH tag when available
        include_tiab     : include [TIAB] free-text synonyms
        max_tiab_per_term: cap TIAB aliases per term (avoid query length limits)

        Returns
        -------
        str - copy-paste ready PubMed query
        """
        if isinstance(terms, str):
            terms = [terms]

        groups: list[str] = []

        for term in terms:
            expanded = self.expand(term)
            parts: list[str] = []

            # 1. MeSH heading (highest precision)
            if include_mesh and expanded["mesh_tag"]:
                parts.append(expanded["mesh_tag"])

            # 2. Free-text synonyms in Title/Abstract
            if include_tiab:
                tiab_terms = expanded["all_terms"][:max_tiab_per_term]
                for alias in tiab_terms:
                    tag = f'"{alias}"[TIAB]'
                    if tag not in parts:
                        parts.append(tag)

            if not parts:
                parts.append(f'"{term.strip()}"[TIAB]')

            groups.append("(" + " OR ".join(parts) + ")")

        query = f" {operator} ".join(groups)

        if filters:
            query += " AND " + " AND ".join(filters)

        return query

    # ------------------------------------------------------------------
    # Runtime extension
    # ------------------------------------------------------------------

    def add_manual_synonyms(self, term: str, synonyms: list[str]) -> None:
        """
        Add project-specific synonyms that MeSH doesn't carry.
        Changes are session-only; edit MANUAL_SYNONYMS for persistence.
        """
        key = term.lower()
        existing = set(s.lower() for s in self._manual.get(key, []))
        new = [s for s in synonyms if s.lower() not in existing]
        self._manual[key] = self._manual.get(key, []) + new


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------

_shared_mapper: MedicalKeywordMapper | None = None


def get_mapper(eager_load: bool = True) -> MedicalKeywordMapper:
    """
    Return a shared MedicalKeywordMapper instance (lazy-initialised).
    Reuses the in-memory MeSH database across callers.
    """
    global _shared_mapper
    if _shared_mapper is None:
        _shared_mapper = MedicalKeywordMapper(eager_load=eager_load)
    return _shared_mapper


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    term = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "lung neoplasms"
    print(f"\n=== Expanding: '{term}' ===")

    mapper = MedicalKeywordMapper()
    info = mapper.expand(term)
    for k, v in info.items():
        print(f"  {k}: {v}")

    print("\n=== PubMed query ===")
    query = mapper.build_pubmed_query(
        terms=[term, "immunotherapy"],
        filters=["humans[MeSH]", "English[lang]", "2018:2026[dp]"],
    )
    print(query)

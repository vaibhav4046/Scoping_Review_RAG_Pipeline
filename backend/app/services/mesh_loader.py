"""
mesh_loader.py
Durgesh | Medical NLP & Data Dictionary

Downloads and parses the official NLM MeSH Descriptor XML
(desc2026.xml) from:
  https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/

Builds a fast lookup table:
  canonical_lower_name → MeSHEntry(ui, preferred_name, synonyms, tree_numbers, pubmed_tag)

The file is ~50 MB. We cache the parsed result as a compact JSON
(~8 MB) at CACHE_PATH so subsequent startups are instant (<200 ms).
The cache is auto-refreshed when it is older than CACHE_TTL_DAYS.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MESH_XML_URL  = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml"
MESH_GZ_URL   = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.gz"
CACHE_PATH    = Path(os.getenv("MESH_CACHE_PATH", "/tmp/mesh_cache_2026.json"))
CACHE_TTL_DAYS = 30          # re-download after this many days
DOWNLOAD_TIMEOUT_SEC = 120   # generous for large file
LOG_EVERY_N   = 5_000        # progress log interval


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MeSHEntry:
    ui:             str          # e.g. "D008175"
    preferred_name: str          # e.g. "Lung Neoplasms"
    synonyms:       list[str]    # all Term strings from all Concepts
    tree_numbers:   list[str]    # e.g. ["C04.588.894.797.520"]
    pubmed_tag:     str          # ready-to-use: "Lung Neoplasms[MeSH]"

    def all_terms(self) -> list[str]:
        """Deduplicated list of preferred name + synonyms."""
        seen: set[str] = set()
        result: list[str] = []
        for t in [self.preferred_name] + self.synonyms:
            low = t.lower()
            if low not in seen:
                seen.add(low)
                result.append(t)
        return result


# ---------------------------------------------------------------------------
# Internal XML iterparse
# ---------------------------------------------------------------------------

def _iter_descriptors(source) -> Iterator[MeSHEntry]:
    """
    Streaming parse of MeSH descriptor XML.

    `source` can be a file path (str/Path) or a readable binary stream.
    Uses iterparse so the full tree is never in memory.
    """
    context = ET.iterparse(source, events=("end",))
    entry: dict = {}
    synonyms: list[str] = []
    tree_numbers: list[str] = []

    for event, elem in context:
        tag = elem.tag

        if tag == "DescriptorRecord":
            # Extract UI
            ui_el = elem.find("DescriptorUI")
            ui = ui_el.text.strip() if ui_el is not None else ""

            # Preferred name
            dn_el = elem.find("DescriptorName/String")
            preferred = dn_el.text.strip() if dn_el is not None else ""

            # All term strings across all concepts
            all_terms: list[str] = []
            for term_el in elem.iter("Term"):
                s_el = term_el.find("String")
                if s_el is not None and s_el.text:
                    t = s_el.text.strip()
                    if t and t.lower() != preferred.lower():
                        all_terms.append(t)

            # Tree numbers
            tns = [tn.text.strip() for tn in elem.findall("TreeNumberList/TreeNumber") if tn.text]

            if ui and preferred:
                yield MeSHEntry(
                    ui=ui,
                    preferred_name=preferred,
                    synonyms=list(dict.fromkeys(all_terms)),   # deduplicate order-preserving
                    tree_numbers=tns,
                    pubmed_tag=f"{preferred}[MeSH]",
                )

            # Free memory immediately — critical for 60k descriptors
            elem.clear()


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_xml(url: str, gz_url: str) -> bytes:
    """Try gzip URL first (smaller), fall back to plain XML."""
    for fetch_url, compressed in ((gz_url, True), (url, False)):
        try:
            log.info("Downloading MeSH from %s …", fetch_url)
            req = urllib.request.Request(
                fetch_url,
                headers={"User-Agent": "scoping-review-nlp/1.0 (research project)"},
            )
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SEC) as resp:
                raw = resp.read()
            if compressed:
                raw = gzip.decompress(raw)
            log.info("Downloaded %.1f MB", len(raw) / 1_048_576)
            return raw
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", fetch_url, exc)

    raise RuntimeError(
        "Could not download MeSH XML from NLM. "
        "Check network access or set MESH_CACHE_PATH to a pre-populated cache."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_mesh(
    force_refresh: bool = False,
    cache_path: Path = CACHE_PATH,
) -> dict[str, MeSHEntry]:
    """
    Return a dict mapping every lowercase term → MeSHEntry.

    Strategy
    --------
    1. If a fresh cache exists at `cache_path`, deserialise and return it.
    2. Otherwise download desc2026.xml from NLM, parse with iterparse,
       build the lookup, serialise to JSON cache, then return.

    Parameters
    ----------
    force_refresh : bool
        Ignore the cache and re-download even if it is fresh.
    cache_path : Path
        Where to read/write the JSON cache.

    Returns
    -------
    dict[str, MeSHEntry]
        Keys are lower-cased term strings (preferred names AND synonyms).
        Multiple keys can map to the same MeSHEntry object.
    """
    if not force_refresh and _cache_is_fresh(cache_path):
        log.info("Loading MeSH from cache: %s", cache_path)
        return _load_cache(cache_path)

    log.info("Fetching fresh MeSH data from NLM …")
    xml_bytes = _download_xml(MESH_XML_URL, MESH_GZ_URL)

    import io
    lookup: dict[str, MeSHEntry] = {}
    count = 0

    for entry in _iter_descriptors(io.BytesIO(xml_bytes)):
        count += 1
        if count % LOG_EVERY_N == 0:
            log.info("  Parsed %d MeSH descriptors …", count)

        # Index by every term (preferred + synonyms), all lower-cased
        for term in entry.all_terms():
            lookup[term.lower()] = entry

    log.info("Parsed %d MeSH descriptors → %d term keys", count, len(lookup))
    _save_cache(lookup, cache_path)
    return lookup


def lookup_term(term: str, mesh_db: dict[str, MeSHEntry]) -> MeSHEntry | None:
    """Case-insensitive lookup of any term in the MeSH database."""
    return mesh_db.get(term.strip().lower())


def lookup_subtree(
    tree_prefix: str, mesh_db: dict[str, MeSHEntry]
) -> list[MeSHEntry]:
    """
    Return all entries whose tree numbers start with `tree_prefix`.

    Useful for fetching an entire MeSH category, e.g.:
        C04   → all neoplasms
        C04.5 → malignant neoplasms
        C04.588.894 → lung/respiratory neoplasms
    """
    seen_uis: set[str] = set()
    results: list[MeSHEntry] = []
    for entry in mesh_db.values():
        if entry.ui not in seen_uis:
            for tn in entry.tree_numbers:
                if tn.startswith(tree_prefix):
                    seen_uis.add(entry.ui)
                    results.append(entry)
                    break
    return results


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86_400
    return age_days < CACHE_TTL_DAYS


def _save_cache(lookup: dict[str, MeSHEntry], path: Path) -> None:
    """Serialise lookup → JSON. Entries are deduplicated by UI."""
    unique: dict[str, dict] = {}
    term_to_ui: dict[str, str] = {}
    for term, entry in lookup.items():
        unique[entry.ui] = asdict(entry)
        term_to_ui[term] = entry.ui

    payload = {"entries": unique, "term_index": term_to_ui}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    log.info("MeSH cache saved → %s (%.1f MB)", path, path.stat().st_size / 1_048_576)


def _load_cache(path: Path) -> dict[str, MeSHEntry]:
    payload = json.loads(path.read_text())
    entries: dict[str, MeSHEntry] = {
        ui: MeSHEntry(**data) for ui, data in payload["entries"].items()
    }
    return {term: entries[ui] for term, ui in payload["term_index"].items()}

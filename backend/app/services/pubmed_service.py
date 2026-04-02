"""PubMed E-utilities search service."""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Optional

import aiohttp

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_OA_BASE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa.cgi"


class PubMedService:
    """Client for NCBI E-utilities API."""

    def __init__(self):
        self.email = settings.pubmed_email
        self.rate_limit = settings.pubmed_rate_limit
        self._semaphore = asyncio.Semaphore(self.rate_limit)

    async def search(self, query: str, max_results: int = 100) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "email": self.email,
        }

        async with aiohttp.ClientSession() as session:
            async with self._semaphore:
                async with session.get(f"{EUTILS_BASE}/esearch.fcgi", params=params) as resp:
                    data = await resp.json()

        id_list = data.get("esearchresult", {}).get("idlist", [])
        total_count = int(data.get("esearchresult", {}).get("count", 0))
        logger.info(f"PubMed search '{query}': {total_count} total, returning {len(id_list)}")
        return id_list

    async def fetch_details(self, pmids: list[str]) -> list[dict]:
        """Fetch article details for a list of PMIDs."""
        if not pmids:
            return []

        results = []
        # Process in batches of 200 (NCBI limit)
        for i in range(0, len(pmids), 200):
            batch = pmids[i:i + 200]
            batch_results = await self._fetch_batch(batch)
            results.extend(batch_results)
            # Rate limiting
            if i + 200 < len(pmids):
                await asyncio.sleep(1.0 / self.rate_limit)

        return results

    async def _fetch_batch(self, pmids: list[str]) -> list[dict]:
        """Fetch details for a batch of PMIDs."""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email,
        }

        async with aiohttp.ClientSession() as session:
            async with self._semaphore:
                async with session.get(f"{EUTILS_BASE}/efetch.fcgi", params=params) as resp:
                    xml_text = await resp.text()

        return self._parse_pubmed_xml(xml_text)

    def _parse_pubmed_xml(self, xml_text: str) -> list[dict]:
        """Parse PubMed XML response into structured dicts."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            for article_elem in root.findall(".//PubmedArticle"):
                article = self._parse_article(article_elem)
                if article:
                    articles.append(article)
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
        return articles

    def _parse_article(self, elem) -> Optional[dict]:
        """Parse a single PubmedArticle element."""
        try:
            medline = elem.find(".//MedlineCitation")
            article = medline.find(".//Article")
            if article is None:
                return None

            # PMID
            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # Title
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "Untitled"

            # Abstract
            abstract_parts = []
            for abs_text in article.findall(".//Abstract/AbstractText"):
                label = abs_text.get("Label", "")
                text = abs_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else None

            # Authors
            authors = []
            for author in article.findall(".//AuthorList/Author"):
                last = author.find("LastName")
                first = author.find("ForeName")
                if last is not None:
                    name = last.text
                    if first is not None:
                        name = f"{last.text} {first.text}"
                    authors.append(name)
            authors_str = "; ".join(authors) if authors else None

            # Journal
            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else None

            # DOI
            doi = None
            for id_elem in elem.findall(".//ArticleIdList/ArticleId"):
                if id_elem.get("IdType") == "doi":
                    doi = id_elem.text
                    break

            # PMCID
            pmcid = None
            for id_elem in elem.findall(".//ArticleIdList/ArticleId"):
                if id_elem.get("IdType") == "pmc":
                    pmcid = id_elem.text
                    break

            # Publication date
            pub_date_elem = article.find(".//Journal/JournalIssue/PubDate")
            pub_date = None
            if pub_date_elem is not None:
                year = pub_date_elem.find("Year")
                month = pub_date_elem.find("Month")
                day = pub_date_elem.find("Day")
                parts = []
                if year is not None:
                    parts.append(year.text)
                if month is not None:
                    parts.append(month.text)
                if day is not None:
                    parts.append(day.text)
                pub_date = "-".join(parts) if parts else None

            # MeSH terms
            mesh_terms = []
            for mesh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
                if mesh.text:
                    mesh_terms.append(mesh.text)
            mesh_str = "; ".join(mesh_terms) if mesh_terms else None

            return {
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": authors_str,
                "journal": journal,
                "publication_date": pub_date,
                "mesh_terms": mesh_str,
            }
        except Exception as e:
            logger.error(f"Failed to parse article: {e}")
            return None

    async def check_pmc_availability(self, pmcid: str) -> Optional[str]:
        """Check if a PMC article has an open-access PDF available."""
        if not pmcid:
            return None

        params = {"id": pmcid, "format": "json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(PMC_OA_BASE, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        records = data.get("records", [])
                        if records:
                            pdf_link = records[0].get("href")
                            return pdf_link
        except Exception as e:
            logger.warning(f"PMC OA check failed for {pmcid}: {e}")
        return None

    async def download_pdf(self, url: str, save_path: str) -> bool:
        """Download a PDF from a URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200 and "pdf" in resp.content_type:
                        with open(save_path, "wb") as f:
                            f.write(await resp.read())
                        return True
        except Exception as e:
            logger.error(f"PDF download failed: {e}")
        return False


pubmed_service = PubMedService()

"""Tests for PDF extraction service — Vaibhav's module."""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Test the dataclass structures
from app.services.pdf_service import (
    PDFService, BlockInfo, PageExtraction, DocumentExtraction,
    pdf_service,
)


class TestBlockInfo:
    def test_creation(self):
        block = BlockInfo(
            text="Test block",
            block_type="text",
            page_number=1,
        )
        assert block.text == "Test block"
        assert block.block_type == "text"
        assert block.is_bold is False

    def test_heading_block(self):
        block = BlockInfo(
            text="Introduction",
            block_type="heading",
            font_size=14.0,
            is_bold=True,
            page_number=1,
        )
        assert block.block_type == "heading"
        assert block.is_bold is True


class TestPageExtraction:
    def test_creation(self):
        page = PageExtraction(
            page_number=1,
            raw_text="Sample text",
            cleaned_text="Sample text",
            blocks=[],
            section_hints=[],
            has_tables=False,
            word_count=2,
        )
        assert page.page_number == 1
        assert page.word_count == 2


class TestPDFService:
    def test_singleton_exists(self):
        assert pdf_service is not None
        assert isinstance(pdf_service, PDFService)

    def test_default_config(self):
        svc = PDFService()
        assert svc.chunk_size == 1000
        assert svc.chunk_overlap == 200

    def test_custom_config(self):
        svc = PDFService(chunk_size=500, chunk_overlap=100)
        assert svc.chunk_size == 500
        assert svc.chunk_overlap == 100

    def test_extract_text_missing_file(self):
        result = pdf_service.extract_text("/nonexistent/file.pdf")
        assert result is None

    def test_chunk_text_empty(self):
        result = pdf_service.chunk_text("")
        assert result == []

    def test_chunk_text_basic(self):
        text = " ".join([f"word{i}" for i in range(100)])
        chunks = pdf_service.chunk_text(text)
        assert len(chunks) > 0
        assert "text" in chunks[0]
        assert "index" in chunks[0]

    def test_extract_and_chunk_missing_file(self):
        result = pdf_service.extract_and_chunk("/nonexistent/file.pdf")
        assert result == []

    def test_extract_document_missing_file(self):
        """extract_document should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            pdf_service.extract_document("/nonexistent/file.pdf")

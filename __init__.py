"""
Modul 02: Thesis Citation & Bibliography Integrity Verifier
Structured Regex Parser and Graph In-Text Reference Matcher.
Detects Phantom Citations, Orphan References, and Validates CrossRef DOIs.
"""

from .models import CitationIssue, CitationAuditResult, InTextCitation, BibliographyEntry
from .parser import parse_docx_manuscript, parse_pdf_manuscript, parse_raw_text_manuscript
from .verifier_engine import ThesisIntegrityVerifier
from .doi_validator import validate_doi_format, verify_doi_crossref

"""
models.py - Data entities for Thesis Citation & Bibliography Integrity Verifier
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


class IssueType(str, Enum):
    PHANTOM_CITATION = "Phantom Citation"   # Cited in body text, missing from bibliography
    ORPHAN_REFERENCE = "Orphan Reference"   # Listed in bibliography, never cited in body text
    INVALID_DOI = "Invalid DOI"             # DOI syntax or lookup failure
    FORMAT_ANOMALY = "Format Anomaly"       # Inconsistent citation style


@dataclass
class InTextCitation:
    raw_citation: str                       # e.g., "[1]", "(Pratama, 2023)"
    citation_type: str                      # "numeric" or "author_year"
    keys: List[str]                         # e.g., ["1"] or ["Pratama", "2023"]
    paragraph_index: int                    # 1-based paragraph position
    context_snippet: str                    # Surrounding text snippet
    page_number: Optional[int] = None       # 1-based page number if available (e.g., from PDF)



@dataclass
class BibliographyEntry:
    raw_text: str                           # Full entry string
    entry_number: Optional[int] = None      # e.g., 1 for [1]
    authors: List[str] = field(default_factory=list)
    year: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None
    is_doi_valid: Optional[bool] = None


@dataclass
class CitationIssue:
    issue_type: IssueType
    identifier: str                         # Reference key or citation text
    location_desc: str                      # e.g., "Paragraf 14" or "Daftar Pustaka Entri #3"
    detail: str                             # Actionable explanation
    severity: str = "Peringatan"            # "Kritis" or "Peringatan"


@dataclass
class CitationAuditResult:
    total_intext_citations: int
    total_bib_entries: int
    matched_pairs: int
    phantom_citations: List[CitationIssue] = field(default_factory=list)
    orphan_references: List[CitationIssue] = field(default_factory=list)
    doi_issues: List[CitationIssue] = field(default_factory=list)
    integrity_score: float = 100.0          # 0.0 to 100.0%
    execution_time_ms: float = 0.0

    @property
    def total_issues_count(self) -> int:
        return len(self.phantom_citations) + len(self.orphan_references) + len(self.doi_issues)

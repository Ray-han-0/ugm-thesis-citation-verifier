"""
verifier_engine.py - Core Graph Bipartite Reference Matcher
Audits thesis manuscripts for Phantom Citations, Orphan References, and Broken DOIs.
"""

import time
from typing import List, Dict, Set, Tuple

try:
    from .models import (
        InTextCitation, BibliographyEntry, CitationIssue, CitationAuditResult, IssueType
    )
    from .doi_validator import verify_doi_crossref, validate_doi_format
except ImportError:
    from models import (
        InTextCitation, BibliographyEntry, CitationIssue, CitationAuditResult, IssueType
    )
    from doi_validator import verify_doi_crossref, validate_doi_format


class ThesisIntegrityVerifier:
    def __init__(self, intext_citations: List[InTextCitation], bib_entries: List[BibliographyEntry]):
        self.intext_citations = intext_citations
        self.bib_entries = bib_entries

    def audit(self, check_doi_online: bool = False) -> CitationAuditResult:
        start_time = time.perf_counter()

        phantom_issues: List[CitationIssue] = []
        orphan_issues: List[CitationIssue] = []
        doi_issues: List[CitationIssue] = []

        # 1. Index bibliography entries
        numeric_bib_map: Dict[int, BibliographyEntry] = {}
        author_year_bib_map: Dict[str, BibliographyEntry] = {}

        for idx, entry in enumerate(self.bib_entries, start=1):
            effective_num = entry.entry_number if entry.entry_number is not None else idx
            numeric_bib_map[effective_num] = entry

            if entry.authors and entry.year:
                author_key = f"{entry.authors[0].lower()}_{entry.year}"
                author_year_bib_map[author_key] = entry

        # 2. Track cited bibliography items
        cited_numeric_keys: Set[int] = set()
        cited_author_keys: Set[str] = set()
        matched_pairs_count = 0

        # 3. Match In-Text Citations -> Bibliography (Detect Phantom Citations)
        for citation in self.intext_citations:
            if citation.citation_type == "numeric":
                for key_str in citation.keys:
                    try:
                        k_int = int(key_str)
                    except ValueError:
                        continue

                    if k_int in numeric_bib_map:
                        cited_numeric_keys.add(k_int)
                        matched_pairs_count += 1
                    else:
                        loc = f"Halaman {citation.page_number}, Paragraf #{citation.paragraph_index}" if citation.page_number else f"Paragraf #{citation.paragraph_index}"
                        phantom_issues.append(CitationIssue(
                            issue_type=IssueType.PHANTOM_CITATION,
                            identifier=f"[{key_str}]",
                            location_desc=loc,
                            detail=f"Sitasi numerik [{key_str}] tertulis di teks tetapi tidak tercantum pada Daftar Pustaka. Konteks: \"{citation.context_snippet}\"",
                            severity="Kritis"
                        ))
            elif citation.citation_type == "author_year":
                for key_str in citation.keys:
                    matched = False
                    # Check exact key
                    if key_str in author_year_bib_map:
                        cited_author_keys.add(key_str)
                        matched_pairs_count += 1
                        matched = True
                    else:
                        # Fuzzy match: author token and year
                        parts = key_str.split("_")
                        if len(parts) == 2:
                            author_sub, year_sub = parts[0], parts[1]
                            for bib_k, bib_entry in author_year_bib_map.items():
                                if author_sub in bib_k and year_sub in bib_k:
                                    cited_author_keys.add(bib_k)
                                    matched_pairs_count += 1
                                    matched = True
                                    break

                    if not matched:
                        loc = f"Halaman {citation.page_number}, Paragraf #{citation.paragraph_index}" if citation.page_number else f"Paragraf #{citation.paragraph_index}"
                        phantom_issues.append(CitationIssue(
                            issue_type=IssueType.PHANTOM_CITATION,
                            identifier=citation.raw_citation,
                            location_desc=loc,
                            detail=f"Sitasi {citation.raw_citation} tidak ditemukan dalam Daftar Pustaka. Konteks: \"{citation.context_snippet}\"",
                            severity="Kritis"
                        ))


        # 4. Detect Orphan References (Bibliography items never cited)
        for idx, entry in enumerate(self.bib_entries, start=1):
            effective_num = entry.entry_number if entry.entry_number is not None else idx
            is_cited = False

            if effective_num in cited_numeric_keys:
                is_cited = True
            elif entry.authors and entry.year:
                author_k = f"{entry.authors[0].lower()}_{entry.year}"
                if author_k in cited_author_keys:
                    is_cited = True
                else:
                    # Check partial matches
                    for c_k in cited_author_keys:
                        if entry.authors[0].lower() in c_k:
                            is_cited = True
                            break

            if not is_cited:
                ident = f"[{effective_num}]" if entry.entry_number else f"Entri #{idx}"
                orphan_issues.append(CitationIssue(
                    issue_type=IssueType.ORPHAN_REFERENCE,
                    identifier=ident,
                    location_desc=f"Daftar Pustaka Baris #{idx}",
                    detail=f"Rujukan '{entry.raw_text[:70]}...' tercantum di Daftar Pustaka namun tidak pernah disitasi di tubuh naskah.",
                    severity="Peringatan"
                ))

        # 5. Validate DOIs
        for idx, entry in enumerate(self.bib_entries, start=1):
            if entry.doi:
                is_valid, msg = verify_doi_crossref(entry.doi, use_network=check_doi_online)
                entry.is_doi_valid = is_valid
                if not is_valid:
                    doi_issues.append(CitationIssue(
                        issue_type=IssueType.INVALID_DOI,
                        identifier=entry.doi,
                        location_desc=f"Daftar Pustaka Baris #{idx}",
                        detail=f"DOI '{entry.doi}' bermasalah: {msg}",
                        severity="Peringatan"
                    ))

        # 6. Calculate Integrity Score (0.0 to 100.0%)
        # Penalty: 15% per phantom, 5% per orphan, 10% per broken DOI
        penalty = (len(phantom_issues) * 15.0) + (len(orphan_issues) * 5.0) + (len(doi_issues) * 10.0)
        score = max(0.0, round(100.0 - penalty, 1))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return CitationAuditResult(
            total_intext_citations=len(self.intext_citations),
            total_bib_entries=len(self.bib_entries),
            matched_pairs=matched_pairs_count,
            phantom_citations=phantom_issues,
            orphan_references=orphan_issues,
            doi_issues=doi_issues,
            integrity_score=score,
            execution_time_ms=elapsed_ms
        )

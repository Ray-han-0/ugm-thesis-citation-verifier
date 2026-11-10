"""
exporter.py - Bibliography correction exporter and audit report formatter
Generates clean bibliography files and audit summary tables for academic theses.
"""

import os
import re
from typing import List, Optional
try:
    from .models import CitationAuditResult, BibliographyEntry, IssueType
except ImportError:
    from models import CitationAuditResult, BibliographyEntry, IssueType


def format_audit_table(audit: CitationAuditResult) -> str:
    """
    Renders an ASCII audit report table detailing all problematic references and page/paragraph locations.
    """
    lines = []
    lines.append("=" * 86)
    lines.append(f" AUDIT INTEGRITAS SITASI & BIBLIOGRAFI (Skor: {audit.integrity_score}% | Waktu: {audit.execution_time_ms:.1f}ms)")
    lines.append("=" * 86)
    lines.append(f"Total Sitasi Tubuh: {audit.total_intext_citations} | Total Entri Pustaka: {audit.total_bib_entries} | Cocok: {audit.matched_pairs}")
    lines.append(f"Phantom Citations: {len(audit.phantom_citations)} | Orphan References: {len(audit.orphan_references)} | DOI Bermasalah: {len(audit.doi_issues)}")
    lines.append("-" * 86)
    lines.append(f"{'Tipe Isu':<18} | {'Identifikasi':<12} | {'Lokasi Naskah':<24} | {'Tingkat':<8}")
    lines.append("-" * 86)

    all_issues = audit.phantom_citations + audit.orphan_references + audit.doi_issues
    if not all_issues:
        lines.append("  [+] Tidak ditemukan anomali sitasi. Naskah memenuhi standar integritas 100%.")
    else:
        for iss in all_issues:
            loc = iss.location_desc[:24]
            lines.append(f"{iss.issue_type.value:<18} | {iss.identifier:<12} | {loc:<24} | {iss.severity:<8}")
            lines.append(f"   -> Detail: {iss.detail}")
    lines.append("=" * 86)
    return "\n".join(lines)


def export_corrected_bibliography(audit: CitationAuditResult,
                                  bib_entries: List[BibliographyEntry],
                                  output_filepath: Optional[str] = None) -> str:
    """
    Exports a sanitized, corrected bibliography file:
    - Retains only validated, actually cited bibliography entries (removes orphans).
    - Lists phantom citations that must be added by the author.
    - Appends DOI validation notes.
    """
    orphan_texts = {o.identifier for o in audit.orphan_references}
    # Map entry numbers or texts of orphans
    lines = [
        "# ==========================================================================",
        "# DAFTAR PUSTAKA HASIL KOREKSI OTOMATIS (SANITIZED BIBLIOGRAPHY)",
        "# UGM Thesis Citation Integrity Verifier",
        f"# Status: Skor Integritas {audit.integrity_score}%",
        "# ==========================================================================\n",
        "DAFTAR PUSTAKA\n"
    ]

    valid_counter = 1
    for idx, entry in enumerate(bib_entries, start=1):
        effective_num = entry.entry_number if entry.entry_number is not None else idx
        ident = f"[{effective_num}]"

        # If it is an orphan, mark it as removed
        is_orphan = any(ident == o.identifier or f"Entri #{idx}" == o.identifier for o in audit.orphan_references)
        if is_orphan:
            lines.append(f"# [DIELIMINASI - ORPHAN REFERENCE TIDAK DISITASI]: {entry.raw_text}")
        else:
            # Clean entry to avoid duplicate bracketed numbers like [1] [1]
            clean_entry = re.sub(r"^\[?\d+\]?[\.\s]*", "", entry.raw_text).strip()
            lines.append(f"[{valid_counter}] {clean_entry}")
            valid_counter += 1

    if audit.phantom_citations:
        lines.append("\n# ==========================================================================")
        lines.append("# CATATAN KOREKSI: SITASI HANTU (PHANTOM CITATION) YANG WAJIB DITAMBAHKAN")
        lines.append("# ==========================================================================")
        for p in audit.phantom_citations:
            lines.append(f"# - Sitasi {p.identifier} di {p.location_desc}: Belum ada pustakanya!")

    content = "\n".join(lines)

    if output_filepath:
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(content)

    return content

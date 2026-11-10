"""
parser.py - Manuscript ingestion and structured regex citation parser
Supports DOCX, PDF, and plain text manuscripts.
Extracts in-text citation markers and structured bibliography entries.
"""

import re
import os
from typing import List, Tuple, Dict, Any, Optional

try:
    from .models import InTextCitation, BibliographyEntry
except ImportError:
    from models import InTextCitation, BibliographyEntry


BIB_HEADER_PATTERNS = [
    re.compile(r"^(?:DAFTAR\s+PUSTAKA|Daftar\s+Pustaka|DAFTAR\s+REFERENSI|REFERENSI|Referensi|REFERENCES|References|BIBLIOGRAPHY|Bibliography)$", re.IGNORECASE),
    re.compile(r"^\s*(?:BAB\s+[IVXLCDM]+\s*[:\.]?\s*)?(?:DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENSI|REFERENCES|BIBLIOGRAPHY)\s*$", re.IGNORECASE)
]

NUMERIC_CITATION_REGEX = re.compile(r"\[\s*(\d+(?:\s*[,-]\s*\d+)*)\s*\]")
AUTHOR_YEAR_PAREN_REGEX = re.compile(
    r"\(\s*([A-Z][a-zA-Z\s\.\-&]+?(?:,\s*(?:dkk\.?|et\s+al\.?))?)\s*,\s*(\d{4}[a-z]?)\s*\)"
)
AUTHOR_YEAR_NARRATIVE_REGEX = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+(?:dan|and|&)\s+[A-Z][a-zA-Z]+|\s+et\s+al\.?|\s+dkk\.?)?)\s*\(\s*(\d{4}[a-z]?)\s*\)"
)
DOI_REGEX = re.compile(r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.IGNORECASE)


def expand_numeric_range(citation_str: str) -> List[str]:
    """
    Expands strings like '1, 2', '1-3', '4, 6-8' into ['1', '2', '3', '4', '6', '7', '8'].
    """
    keys = []
    tokens = [t.strip() for t in citation_str.split(",")]
    for token in tokens:
        if "-" in token:
            parts = token.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start, end = int(parts[0]), int(parts[1])
                for num in range(start, end + 1):
                    keys.append(str(num))
                continue
        if token.isdigit():
            keys.append(token)
    return keys


def extract_intext_citations_from_paragraphs(paragraphs: List[Any]) -> List[InTextCitation]:
    """
    Scans a list of body paragraphs and returns all InTextCitation occurrences.
    paragraphs can be a list of str or a list of tuples: (text, page_number).
    """
    citations: List[InTextCitation] = []

    for p_idx, item in enumerate(paragraphs, start=1):
        if isinstance(item, tuple):
            text, page_num = item
        else:
            text, page_num = item, None

        if not text:
            continue

        # 1. Numeric bracket citations [1], [1, 2], [1-3]
        for match in NUMERIC_CITATION_REGEX.finditer(text):
            raw = match.group(0)
            inner = match.group(1)
            keys = expand_numeric_range(inner)
            start_pos = max(0, match.start() - 30)
            end_pos = min(len(text), match.end() + 30)
            snippet = text[start_pos:end_pos].strip()

            citations.append(InTextCitation(
                raw_citation=raw,
                citation_type="numeric",
                keys=keys,
                paragraph_index=p_idx,
                context_snippet=snippet,
                page_number=page_num
            ))

        # 2. Author-Year parenthetical citations (Pratama, 2023)
        for match in AUTHOR_YEAR_PAREN_REGEX.finditer(text):
            author = match.group(1).strip()
            year = match.group(2).strip()
            start_pos = max(0, match.start() - 30)
            end_pos = min(len(text), match.end() + 30)
            snippet = text[start_pos:end_pos].strip()

            # Clean primary author surname
            primary_author = author.split()[0].replace(",", "")
            citations.append(InTextCitation(
                raw_citation=match.group(0),
                citation_type="author_year",
                keys=[f"{primary_author.lower()}_{year}"],
                paragraph_index=p_idx,
                context_snippet=snippet,
                page_number=page_num
            ))

        # 3. Narrative citations: Russell et al. (2020)
        for match in AUTHOR_YEAR_NARRATIVE_REGEX.finditer(text):
            author = match.group(1).strip()
            year = match.group(2).strip()
            start_pos = max(0, match.start() - 30)
            end_pos = min(len(text), match.end() + 30)
            snippet = text[start_pos:end_pos].strip()

            primary_author = author.split()[0].replace(",", "")
            citations.append(InTextCitation(
                raw_citation=f"{author} ({year})",
                citation_type="author_year",
                keys=[f"{primary_author.lower()}_{year}"],
                paragraph_index=p_idx,
                context_snippet=snippet,
                page_number=page_num
            ))

    return citations



def parse_bibliography_entries(bib_lines: List[str]) -> List[BibliographyEntry]:
    """
    Parses bibliography section into individual structured BibliographyEntry objects.
    """
    entries: List[BibliographyEntry] = []
    current_entry_lines = []

    def commit_entry(lines: List[str]):
        if not lines:
            return
        full_text = " ".join(lines).strip()
        if not full_text:
            return

        # Check numeric prefix: "[1]" or "1."
        entry_num = None
        num_match = re.match(r"^\[?(\d+)\]?[\.\s]", full_text)
        if num_match:
            entry_num = int(num_match.group(1))

        # Extract DOI if present
        doi = None
        doi_match = DOI_REGEX.search(full_text)
        if doi_match:
            doi = doi_match.group(1).strip()

        # Extract year
        year_match = re.search(r"\((\d{4}[a-z]?)\)|\b(19\d\d|20\d\d)\b", full_text)
        year = year_match.group(1) or year_match.group(2) if year_match else None

        # Extract author guess (first token before year or punctuation)
        clean_prefix = re.sub(r"^\[?\d+\]?[\.\s]*", "", full_text)
        author_tokens = clean_prefix.split(",")[0].split()[0] if clean_prefix else "Unknown"

        entries.append(BibliographyEntry(
            raw_text=full_text,
            entry_number=entry_num,
            authors=[author_tokens],
            year=year,
            doi=doi
        ))

    for line in bib_lines:
        line_s = line.strip()
        if not line_s:
            continue

        # Detect start of new bibliography item
        is_new_entry = False
        if re.match(r"^\[?\d+\]?[\.\s]", line_s):
            is_new_entry = True
        elif len(line_s) > 0 and line_s[0].isupper() and ("," in line_s or "(" in line_s):
            # Author-year style: if preceding line ended with period or URL
            if current_entry_lines and (current_entry_lines[-1].endswith(".") or "http" in current_entry_lines[-1]):
                is_new_entry = True

        if is_new_entry and current_entry_lines:
            commit_entry(current_entry_lines)
            current_entry_lines = [line_s]
        else:
            current_entry_lines.append(line_s)

    if current_entry_lines:
        commit_entry(current_entry_lines)

    return entries


BIB_HEADER_REGEX = re.compile(
    r"(?:\n|\A)\s*(?:BAB\s+[IVXLCDM]+\s*[:\.]?\s*)?(?:DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENSI|REFERENCES|BIBLIOGRAPHY)\s*(?:\n|\Z)",
    re.IGNORECASE
)


def split_body_and_bibliography_text(full_text: str) -> Tuple[str, str]:
    """
    Finds the boundary between manuscript body text and Daftar Pustaka using regex search.
    """
    match = BIB_HEADER_REGEX.search(full_text)
    if match:
        body_text = full_text[:match.start()].strip()
        bib_text = full_text[match.end():].strip()
        return body_text, bib_text
    return full_text.strip(), ""


def parse_raw_text_manuscript(raw_text: str) -> Tuple[List[InTextCitation], List[BibliographyEntry]]:
    """
    Parses plain text document string into in-text citations and bibliography entries.
    """
    body_text, bib_text = split_body_and_bibliography_text(raw_text)

    # Paragraphs for body text
    body_paras = [p.strip() for p in body_text.split("\n\n") if p.strip()]
    if not body_paras and body_text:
        body_paras = [l.strip() for l in body_text.split("\n") if l.strip()]

    # Lines for bibliography
    bib_lines = [l.strip() for l in bib_text.split("\n") if l.strip()]

    intext_citations = extract_intext_citations_from_paragraphs(body_paras)
    bib_entries = parse_bibliography_entries(bib_lines)

    return intext_citations, bib_entries


def parse_docx_manuscript(filepath: str) -> Tuple[List[InTextCitation], List[BibliographyEntry]]:
    """
    Parses DOCX document using python-docx.
    """
    from docx import Document
    doc = Document(filepath)
    full_text = "\n\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    return parse_raw_text_manuscript(full_text)


def extract_linearized_pdf_page_text(page) -> str:
    """
    Extracts text from a PDF page while accurately linearizing multi-column layouts
    (e.g., IEEE/ACM 2-column format) by analyzing coordinate geometry via visitor_text.
    Falls back gracefully to standard extract_text() if coordinates are unavailable.
    """
    elements = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text and text.strip():
            if cm and len(cm) >= 6 and tm and len(tm) >= 6:
                dev_x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
                dev_y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            elif tm and len(tm) >= 6:
                dev_x = tm[4]
                dev_y = tm[5]
            else:
                dev_x, dev_y = 0.0, 0.0
            elements.append((float(dev_x), float(dev_y), text))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        return page.extract_text() or ""

    if not elements:
        return page.extract_text() or ""

    try:
        page_width = float(page.mediabox.width)
    except Exception:
        page_width = 595.0

    mid_x = page_width / 2.0

    left_elems = [e for e in elements if e[0] < mid_x - 10]
    right_elems = [e for e in elements if e[0] >= mid_x - 10]

    # Check for two-column overlap in vertical y span
    is_multi_col = False
    if len(left_elems) >= 2 and len(right_elems) >= 2:
        left_y_min, left_y_max = min(e[1] for e in left_elems), max(e[1] for e in left_elems)
        right_y_min, right_y_max = min(e[1] for e in right_elems), max(e[1] for e in right_elems)
        overlap_min = max(left_y_min, right_y_min)
        overlap_max = min(left_y_max, right_y_max)
        if overlap_max >= overlap_min + 10.0:
            is_multi_col = True

    def cluster_into_lines(elem_list):
        if not elem_list:
            return []
        sorted_by_y = sorted(elem_list, key=lambda e: -e[1])
        lines = []
        curr_line = [sorted_by_y[0]]
        for e in sorted_by_y[1:]:
            if abs(e[1] - curr_line[0][1]) <= 3.5:
                curr_line.append(e)
            else:
                curr_line.sort(key=lambda x: x[0])
                line_str = " ".join(item[2].strip() for item in curr_line if item[2].strip())
                if line_str:
                    lines.append(line_str)
                curr_line = [e]
        if curr_line:
            curr_line.sort(key=lambda x: x[0])
            line_str = " ".join(item[2].strip() for item in curr_line if item[2].strip())
            if line_str:
                lines.append(line_str)
        return lines

    if not is_multi_col:
        lines = cluster_into_lines(elements)
        return "\n".join(lines)
    else:
        # Multi-column: separate header, two columns, and footer
        header_elems = [e for e in elements if e[1] > overlap_max + 8.0]
        footer_elems = [e for e in elements if e[1] < overlap_min - 8.0]
        body_left = [e for e in left_elems if overlap_min - 8.0 <= e[1] <= overlap_max + 8.0]
        body_right = [e for e in right_elems if overlap_min - 8.0 <= e[1] <= overlap_max + 8.0]

        h_lines = cluster_into_lines(header_elems)
        l_lines = cluster_into_lines(body_left)
        r_lines = cluster_into_lines(body_right)
        f_lines = cluster_into_lines(footer_elems)

        all_lines = h_lines + l_lines + r_lines + f_lines
        return "\n".join(all_lines)


def parse_pdf_manuscript(filepath: str) -> Tuple[List[InTextCitation], List[BibliographyEntry]]:
    """
    Parses PDF document using pypdf, tracking page numbers for each paragraph.
    Handles multi-column layouts via coordinate-based reading order linearization.
    """
    import pypdf
    reader = pypdf.PdfReader(filepath)

    bib_found = False
    bib_lines = []
    body_items = []

    for page_idx, page in enumerate(reader.pages, start=1):
        t = extract_linearized_pdf_page_text(page)
        if not t:
            continue

        if not bib_found:
            match = BIB_HEADER_REGEX.search(t)
            if match:
                bib_found = True
                body_part = t[:match.start()].strip()
                bib_part = t[match.end():].strip()
                if body_part:
                    for p in body_part.split("\n\n"):
                        if p.strip():
                            body_items.append((p.strip(), page_idx))
                if bib_part:
                    for l in bib_part.split("\n"):
                        if l.strip():
                            bib_lines.append(l.strip())
            else:
                for p in t.split("\n\n"):
                    if p.strip():
                        body_items.append((p.strip(), page_idx))
        else:
            for l in t.split("\n"):
                if l.strip():
                    bib_lines.append(l.strip())

    intext_citations = extract_intext_citations_from_paragraphs(body_items)
    bib_entries = parse_bibliography_entries(bib_lines)
    return intext_citations, bib_entries


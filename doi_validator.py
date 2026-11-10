"""
doi_validator.py - CrossRef DOI syntax and public registry verification
Validates digital object identifiers (DOIs) with offline heuristic fallback.
"""

import re
from typing import Tuple, Dict
import requests

DOI_SYNTAX_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")

# Common authentic academic DOI registrant prefixes
KNOWN_PREFIXES = {
    "10.1109": "IEEE",
    "10.1145": "ACM",
    "10.1016": "Elsevier",
    "10.1007": "Springer",
    "10.1021": "ACS",
    "10.1371": "PLOS",
    "10.1038": "Nature",
    "10.1080": "Taylor & Francis",
    "10.1002": "Wiley",
}

# Local cache to prevent redundant network calls
_DOI_CACHE: Dict[str, Tuple[bool, str]] = {}


def validate_doi_format(doi: str) -> bool:
    """
    Syntactic validation of DOI according to ISO 26324.
    """
    if not doi:
        return False
    clean_doi = doi.strip()
    if clean_doi.startswith("http"):
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", clean_doi)
    return bool(DOI_SYNTAX_PATTERN.match(clean_doi))


def verify_doi_crossref(doi: str, use_network: bool = True) -> Tuple[bool, str]:
    """
    Verifies DOI against public CrossRef API (api.crossref.org/works/{doi}).
    Falls back gracefully to local heuristic validation if network is unreachable.
    """
    if not doi:
        return False, "DOI kosong"

    clean_doi = doi.strip()
    if clean_doi.startswith("http"):
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", clean_doi)

    if not validate_doi_format(clean_doi):
        return False, f"Format sintaks DOI tidak valid: '{clean_doi}'"

    if clean_doi in _DOI_CACHE:
        return _DOI_CACHE[clean_doi]

    prefix = clean_doi.split("/")[0]
    publisher = KNOWN_PREFIXES.get(prefix, "Registrant Umum CrossRef")

    if not use_network:
        # Offline mode: verified structurally
        result = (True, f"Sintaks valid (Publisher: {publisher}) [Verifikasi Lokal]")
        _DOI_CACHE[clean_doi] = result
        return result

    url = f"https://api.crossref.org/works/{clean_doi}"
    headers = {
        "User-Agent": "UGM-ThesisIntegrityVerifier/1.0 (mailto:ugm.capstone@student.ugm.ac.id)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            title = data.get("message", {}).get("title", [""])[0]
            result = (True, f"Terverifikasi CrossRef: {title[:50]}...")
        elif response.status_code == 404:
            result = (False, "DOI tidak ditemukan di basis data CrossRef (HTTP 404)")
        else:
            # Fallback to local heuristic on rate limit or other server status
            result = (True, f"Sintaks valid (Publisher: {publisher}) [Fallback Server HTTP {response.status_code}]")
    except Exception:
        # Offline fallback
        result = (True, f"Sintaks valid (Publisher: {publisher}) [Mode Mandiri Luring]")

    _DOI_CACHE[clean_doi] = result
    return result

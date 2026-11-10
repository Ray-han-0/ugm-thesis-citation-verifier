"""
cli.py - Command Line User Interface for Thesis Citation Verifier
Scans DOCX or PDF thesis manuscripts for phantom citations and orphan references.
"""

import argparse
import os
import sys

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if CURR_DIR not in sys.path:
    sys.path.insert(0, CURR_DIR)

from parser import parse_docx_manuscript, parse_pdf_manuscript, parse_raw_text_manuscript
from verifier_engine import ThesisIntegrityVerifier
from exporter import format_audit_table, export_corrected_bibliography


def get_demo_manuscript() -> str:
    return (
        "BAB 1 PENDAHULUAN\n\n"
        "Kecerdasan buatan mengalami akselerasi luar biasa pada sistem komputasi modern [1]. "
        "Arsitektur deep learning mentransformasi paradigma analisis citra dan teks [2]. "
        "Namun optimasi lokal seringkali terjebak pada minimum lokal sebagaimana dicatat oleh [3]. "
        "Sebuah temuan mutakhir memaparkan metode pembelajaran mandiri tanpa anotasi manusia [99].\n\n"
        "DAFTAR PUSTAKA\n"
        "[1] Russell, S., & Norvig, P. (2020). Artificial Intelligence: A Modern Approach. Pearson.\n"
        "[2] Goodfellow, I., Bengio, Y., & Courville, A. (2016). Deep Learning. MIT Press.\n"
        "[3] Sutton, R. S., & Barto, A. G. (2018). Reinforcement Learning: An Introduction. MIT Press.\n"
        "[4] Goldberg, D. E. (1989). Genetic Algorithms in Search and Optimization. Addison-Wesley.\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Thesis Citation & Bibliography Integrity Verifier UGM")
    parser.add_argument("--input", "-i", type=str, help="Jalur berkas naskah skripsi (.docx, .pdf, atau .txt)")
    parser.add_argument("--check-doi", action="store_true", help="Validasi daring DOI ke public CrossRef API")
    parser.add_argument("--export-bib", "-o", type=str, help="Jalur berkas ekspor koreksi bibliografi (.txt)")
    args = parser.parse_args()

    if args.input:
        if not os.path.exists(args.input):
            print(f"[Error] Berkas tidak ditemukan: {args.input}")
            sys.exit(1)
        ext = os.path.splitext(args.input)[1].lower()
        if ext == ".docx":
            print(f"[*] Membaca naskah skripsi DOCX: {args.input}")
            intext, bib = parse_docx_manuscript(args.input)
        elif ext == ".pdf":
            print(f"[*] Membaca naskah skripsi PDF: {args.input}")
            intext, bib = parse_pdf_manuscript(args.input)
        else:
            with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            intext, bib = parse_raw_text_manuscript(content)
    else:
        print("[*] Mode Demo: Menggunakan contoh naskah skripsi dengan 1 phantom citation ([99]) dan 1 orphan reference ([4])")
        content = get_demo_manuscript()
        intext, bib = parse_raw_text_manuscript(content)

    print(f"[*] Ditemukan {len(intext)} sitasi di tubuh teks dan {len(bib)} entri Daftar Pustaka.")
    verifier = ThesisIntegrityVerifier(intext, bib)
    audit = verifier.audit(check_doi_online=args.check_doi)

    print("\n" + format_audit_table(audit))

    if args.export_bib:
        export_corrected_bibliography(audit, bib, args.export_bib)
        print(f"\n[+] Berkas koreksi bibliografi berhasil disimpan ke: {args.export_bib}")


if __name__ == "__main__":
    main()

"""
test_verifier.py - Unit & Integration Tests for Thesis Citation Verifier
Tests phantom citation detection, orphan references, DOI validation, and benchmark metrics.
"""

import unittest
import os
import sys

# Ensure current directory is on sys.path
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
if CURR_DIR not in sys.path:
    sys.path.insert(0, CURR_DIR)

from models import InTextCitation, BibliographyEntry, IssueType
from parser import (
    parse_raw_text_manuscript, expand_numeric_range, extract_intext_citations_from_paragraphs,
    parse_pdf_manuscript, extract_linearized_pdf_page_text
)
from verifier_engine import ThesisIntegrityVerifier
from doi_validator import validate_doi_format, verify_doi_crossref
from exporter import export_corrected_bibliography, format_audit_table



class TestThesisVerifier(unittest.TestCase):
    def test_expand_numeric_range(self):
        self.assertEqual(expand_numeric_range("1"), ["1"])
        self.assertEqual(expand_numeric_range("1, 2, 4"), ["1", "2", "4"])
        self.assertEqual(expand_numeric_range("1-3"), ["1", "2", "3"])
        self.assertEqual(expand_numeric_range("2, 5-7, 9"), ["2", "5", "6", "7", "9"])

    def test_phantom_citation_detection(self):
        sample_text = (
            "Kecerdasan buatan berkembang pesat dalam dekade terakhir [1]. "
            "Namun demikian, pendekatan konvensional masih memiliki keterbatasan [2]. "
            "Sebuah studi terbaru menunjukkan anomali yang belum terpecahkan [99].\n\n"
            "DAFTAR PUSTAKA\n"
            "[1] Russell, S., & Norvig, P. (2020). Artificial Intelligence. Pearson.\n"
            "[2] Goodfellow, I., et al. (2016). Deep Learning. MIT Press.\n"
        )
        intext, bib = parse_raw_text_manuscript(sample_text)
        verifier = ThesisIntegrityVerifier(intext, bib)
        result = verifier.audit(check_doi_online=False)

        # [99] must be flagged as phantom citation
        self.assertEqual(len(result.phantom_citations), 1)
        self.assertEqual(result.phantom_citations[0].identifier, "[99]")
        self.assertEqual(len(result.orphan_references), 0)
        self.assertLess(result.integrity_score, 100.0)

    def test_orphan_reference_detection(self):
        sample_text = (
            "Algoritma genetika sering digunakan untuk optimasi global [1].\n\n"
            "DAFTAR PUSTAKA\n"
            "[1] Goldberg, D. E. (1989). Genetic Algorithms. Addison-Wesley.\n"
            "[2] Holland, J. H. (1992). Adaptation in Natural and Artificial Systems. MIT Press.\n"
            "[3] Koza, J. R. (1992). Genetic Programming. MIT Press.\n"
        )
        intext, bib = parse_raw_text_manuscript(sample_text)
        verifier = ThesisIntegrityVerifier(intext, bib)
        result = verifier.audit(check_doi_online=False)

        # [2] and [3] must be flagged as orphan references
        self.assertEqual(len(result.phantom_citations), 0)
        self.assertEqual(len(result.orphan_references), 2)
        orphan_ids = [o.identifier for o in result.orphan_references]
        self.assertIn("[2]", orphan_ids)
        self.assertIn("[3]", orphan_ids)

    def test_author_year_matching(self):
        sample_text = (
            "Metode ini pertama kali diajukan oleh (Pratama, 2023) dalam konteks jaringan kampus. "
            "Penelitian lain oleh (Suryanto, 2021) menunjukkan efisiensi tinggi. "
            "Namun klaim (Unknown, 2099) tidak didukung data empiris.\n\n"
            "DAFTAR PUSTAKA\n"
            "Pratama, A. (2023). Analisis Optimasi Jaringan Nirkabel Kampus. Jurnal UGM, 5(1), 10-20.\n"
            "Suryanto, B. (2021). Komputasi Terdistribusi Mandiri. Prosiding Nasional, 44-52.\n"
        )
        intext, bib = parse_raw_text_manuscript(sample_text)
        verifier = ThesisIntegrityVerifier(intext, bib)
        result = verifier.audit(check_doi_online=False)

        # (Unknown, 2099) must be flagged as phantom
        self.assertEqual(len(result.phantom_citations), 1)
        self.assertIn("Unknown", result.phantom_citations[0].identifier)

    def test_doi_syntax_validation(self):
        valid_doi = "10.1145/3290605.3300233"
        invalid_doi = "not-a-valid-doi"
        valid_url_doi = "https://doi.org/10.1109/TSE.2020.2987654"

        self.assertTrue(validate_doi_format(valid_doi))
        self.assertFalse(validate_doi_format(invalid_doi))
        self.assertTrue(validate_doi_format(valid_url_doi))

    def test_precision_recall_benchmark(self):
        """
        Tests precision and recall on a synthetic benchmark manuscript with 10 total citations:
        - 7 valid citations
        - 3 intentional phantom citations
        - 2 intentional orphan references in bibliography
        """
        ground_truth_phantoms = {"[101]", "[102]", "[103]"}
        ground_truth_orphans = {"[8]", "[9]"}

        body = (
            "Bab 1 membahas teori dasar [1] dan arsitektur [2]. "
            "Model diperluas dengan jaringan saraf [3, 4] dan pembelajaran terarah [5]. "
            "Eksperimen awal dicatat oleh [6] serta validasi silang oleh [7]. "
            "Namun terdapat klaim rujukan hilang [101] dan sitasi fiktif [102, 103].\n\n"
            "DAFTAR PUSTAKA\n"
            "[1] Author One. (2020). Foundation. DOI: 10.1109/A.2020.1\n"
            "[2] Author Two. (2021). Architecture. DOI: 10.1145/B.2021.2\n"
            "[3] Author Three. (2019). Neural Networks.\n"
            "[4] Author Four. (2022). Supervised Learning.\n"
            "[5] Author Five. (2023). Empirical Studies.\n"
            "[6] Author Six. (2018). Preliminary Notes.\n"
            "[7] Author Seven. (2020). Cross Validation.\n"
            "[8] Author Eight. (2017). Orphan Reference One.\n"
            "[9] Author Nine. (2016). Orphan Reference Two.\n"
        )
        intext, bib = parse_raw_text_manuscript(body)
        verifier = ThesisIntegrityVerifier(intext, bib)
        audit = verifier.audit(check_doi_online=False)

        detected_phantoms = {p.identifier for p in audit.phantom_citations}
        detected_orphans = {o.identifier for o in audit.orphan_references}

        # Calculate Precision and Recall for Phantom Citations
        tp_phantom = len(detected_phantoms.intersection(ground_truth_phantoms))
        fp_phantom = len(detected_phantoms - ground_truth_phantoms)
        fn_phantom = len(ground_truth_phantoms - detected_phantoms)

        precision = tp_phantom / (tp_phantom + fp_phantom) if (tp_phantom + fp_phantom) > 0 else 0
        recall = tp_phantom / (tp_phantom + fn_phantom) if (tp_phantom + fn_phantom) > 0 else 0

        self.assertEqual(precision, 1.0, "Phantom detection precision should be 100%")
        self.assertEqual(recall, 1.0, "Phantom detection recall should be 100%")
        self.assertEqual(detected_orphans, ground_truth_orphans, "Orphan detection must match ground truth exactly")

    def test_export_corrected_bibliography_and_audit_table(self):
        sample = (
            "Model pembelajaran mesin [1] divalidasi pada klaster [2]. Rujukan fiktif [99].\n\n"
            "DAFTAR PUSTAKA\n"
            "[1] Valid Reference One (2020).\n"
            "[2] Valid Reference Two (2021).\n"
            "[3] Orphan Reference Three (2019).\n"
        )
        intext, bib = parse_raw_text_manuscript(sample)
        verifier = ThesisIntegrityVerifier(intext, bib)
        audit = verifier.audit()

        table_str = format_audit_table(audit)
        self.assertIn("AUDIT INTEGRITAS SITASI", table_str)
        self.assertIn("[99]", table_str)
        self.assertIn("[3]", table_str)

        corrected = export_corrected_bibliography(audit, bib)
        self.assertIn("[1] Valid Reference One", corrected)
        self.assertIn("[2] Valid Reference Two", corrected)
        # Ensure no double-bracketed formatting like [1] [1]
        self.assertNotIn("[1] [1]", corrected)
        self.assertNotIn("[2] [2]", corrected)
        self.assertIn("DIELIMINASI - ORPHAN REFERENCE", corrected)
        self.assertIn("SITASI HANTU", corrected)

    def test_parse_pdf_manuscript_with_page_numbers(self):
        import tempfile
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            temp_pdf = tf.name

        try:
            doc = SimpleDocTemplate(temp_pdf, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [
                Paragraph("Halaman 1 membahas algoritma genetika [1].", styles['Normal']),
                PageBreak(),
                Paragraph("Halaman 2 membahas sitasi phantom tanpa pustaka [88].", styles['Normal']),
                PageBreak(),
                Paragraph("DAFTAR PUSTAKA", styles['Heading1']),
                Paragraph("[1] Holland, J. H. (1992). Adaptation in Natural Systems. MIT Press.", styles['Normal']),
            ]
            doc.build(story)

            intext, bib = parse_pdf_manuscript(temp_pdf)
            self.assertEqual(len(intext), 2)
            self.assertEqual(len(bib), 1)

            # Check page numbers
            cit_page1 = next(c for c in intext if "[1]" in c.raw_citation)
            cit_page2 = next(c for c in intext if "[88]" in c.raw_citation)
            self.assertEqual(cit_page1.page_number, 1)
            self.assertEqual(cit_page2.page_number, 2)

            # Audit should report exact page number
            verifier = ThesisIntegrityVerifier(intext, bib)
            audit = verifier.audit()
            phantom_issue = audit.phantom_citations[0]
            self.assertIn("Halaman 2", phantom_issue.location_desc)
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)

    def test_parse_multicolumn_pdf_linearization(self):
        """
        Tests multi-column PDF reading order linearization.
        Verifies that text in left column is extracted prior to text in right column,
        even if elements are drawn interwoven line-by-line in the PDF stream.
        """
        import tempfile
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        import pypdf

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            temp_pdf = tf.name

        try:
            c = canvas.Canvas(temp_pdf, pagesize=letter)
            # Full-width Title at top
            c.drawString(150, 750, "Judul Artikel Dua Kolom")
            # Interwoven lines in PDF content stream:
            # y=700: left column item 1, then right column item 1
            c.drawString(50, 700, "Kolom kiri membahas sitasi awal [1].")
            c.drawString(350, 700, "Kolom kanan membahas temuan kedua [2].")
            # y=670: left column item 2, then right column item 2
            c.drawString(50, 670, "Kelanjutan narasi kolom kiri tanpa putus.")
            c.drawString(350, 670, "Kelanjutan narasi kolom kanan tanpa putus.")
            # Footer
            c.drawString(250, 40, "Halaman 1")
            c.showPage()
            c.save()

            reader = pypdf.PdfReader(temp_pdf)
            linearized = extract_linearized_pdf_page_text(reader.pages[0])

            # Left column sentences must appear before right column sentences
            pos_left_1 = linearized.find("Kolom kiri membahas sitasi awal [1].")
            pos_left_2 = linearized.find("Kelanjutan narasi kolom kiri tanpa putus.")
            pos_right_1 = linearized.find("Kolom kanan membahas temuan kedua [2].")
            pos_right_2 = linearized.find("Kelanjutan narasi kolom kanan tanpa putus.")

            self.assertNotEqual(pos_left_1, -1)
            self.assertNotEqual(pos_left_2, -1)
            self.assertNotEqual(pos_right_1, -1)
            self.assertNotEqual(pos_right_2, -1)

            # Strict linear reading order: left column block before right column block
            self.assertLess(pos_left_1, pos_left_2)
            self.assertLess(pos_left_2, pos_right_1)
            self.assertLess(pos_right_1, pos_right_2)
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)

    def test_english_references_header(self):
        sample = (
            "Machine learning enables automated theorem proving [1].\n\n"
            "REFERENCES\n"
            "[1] Deep Learning Author (2022). Deep Learning Systems.\n"
        )
        intext, bib = parse_raw_text_manuscript(sample)
        self.assertEqual(len(intext), 1)
        self.assertEqual(len(bib), 1)
        verifier = ThesisIntegrityVerifier(intext, bib)
        audit = verifier.audit()
        self.assertEqual(len(audit.phantom_citations), 0)
        self.assertEqual(len(audit.orphan_references), 0)
        self.assertEqual(audit.integrity_score, 100.0)


if __name__ == "__main__":
    unittest.main()



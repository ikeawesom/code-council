"""PDF/DOCX -> plain text with structure hints.

pdfplumber for PDF, python-docx for DOCX. Scanned/image-only PDFs are detected
(no extractable text layer) and reported at ingest rather than silently
producing an empty document - OCR is explicitly out of scope for the demo.
"""
# TODO(M1): parse_document(path) -> ParsedDoc(title, blocks[])

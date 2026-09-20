"""
Document Processing Service for Agentic AI Tutor.

Handles extraction and chunking of text from various document formats:
- PDF files
- Text files (TXT, MD)
- Word documents (DOCX, DOC)

Prepares documents for RAG ingestion.
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Process documents for RAG ingestion.

    Extracts text from various formats and chunks it appropriately
    for embedding and retrieval.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize document processor.

        Args:
            chunk_size: Target size for text chunks (in characters)
            chunk_overlap: Overlap between chunks for context continuity
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Try to import optional dependencies
        self._pdf_available = self._check_pdf_support()
        self._docx_available = self._check_docx_support()

    def _check_pdf_support(self) -> bool:
        """Check if PDF processing is available"""
        try:
            import PyPDF2

            return True
        except ImportError:
            logger.warning(
                "PyPDF2 not available. PDF processing disabled. Install: pip install PyPDF2"
            )
            return False

    def _check_docx_support(self) -> bool:
        """Check if DOCX processing is available"""
        try:
            import docx

            return True
        except ImportError:
            logger.warning(
                "python-docx not available. DOCX processing disabled. Install: pip install python-docx"
            )
            return False

    def process_document(
        self, file_path: str, filename: str, student_id: str, subject: str = "General"
    ) -> List[Dict[str, Any]]:
        """
        Process a document and return chunked text.

        Args:
            file_path: Path to the document file
            filename: Original filename
            student_id: Student ID for metadata
            subject: Subject/topic classification

        Returns:
            List of text chunks with metadata
        """
        # Determine file type
        file_ext = Path(filename).suffix.lower()

        # Extract text based on file type
        if file_ext == ".pdf":
            text = self._extract_pdf(file_path)
        elif file_ext in [".txt", ".md"]:
            text = self._extract_text(file_path)
        elif file_ext in [".docx", ".doc"]:
            text = self._extract_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        if not text or len(text.strip()) < 10:
            raise ValueError("Could not extract meaningful text from document")

        # Chunk the text
        chunks = self._chunk_text(text)

        # Add metadata to each chunk
        processed_chunks = []
        for i, chunk_text in enumerate(chunks):
            processed_chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        "student_id": student_id,
                        "filename": filename,
                        "subject": subject,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    },
                }
            )

        logger.info(f"Processed {filename}: extracted {len(text)} chars -> {len(chunks)} chunks")
        return processed_chunks

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        if not self._pdf_available:
            raise RuntimeError("PDF support not available. Install PyPDF2: pip install PyPDF2")

        import PyPDF2

        text = []
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                    logger.debug(f"Extracted {len(page_text)} chars from page {page_num + 1}")

            return "\n\n".join(text)

        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
            raise ValueError(f"Could not read PDF file: {str(e)}")

    def _extract_text(self, file_path: str) -> str:
        """Extract text from plain text file"""
        try:
            # Try UTF-8 first
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    return file.read()
            except UnicodeDecodeError:
                # Fallback to latin-1
                with open(file_path, "r", encoding="latin-1") as file:
                    return file.read()

        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            raise ValueError(f"Could not read text file: {str(e)}")

    def _extract_docx(self, file_path: str) -> str:
        """
        Extract text from DOCX file.

        Covers the body in document order, the contents of every table, and
        the headers and footers. ``doc.paragraphs`` alone sees none of the
        table text, so a worksheet or assignment laid out as a table - which
        is how most of them are written - used to come through as nothing but
        its cover lines.
        """
        if not self._docx_available:
            raise RuntimeError(
                "DOCX support not available. Install python-docx: pip install python-docx"
            )

        import docx

        try:
            doc = docx.Document(file_path)

            parts = self._docx_section_text(doc, header=True)
            parts.extend(self._docx_body_text(doc))
            parts.extend(self._docx_section_text(doc, header=False))

            return "\n\n".join(parts)

        except Exception as e:
            logger.error(f"Error extracting DOCX {file_path}: {e}")
            raise ValueError(f"Could not read DOCX file: {str(e)}")

    def _docx_body_text(self, doc) -> List[str]:
        """Read a document body in order, interleaving paragraphs and tables"""
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        parts = []
        for child in doc.element.body.iterchildren():
            if child.tag == qn("w:p"):
                text = Paragraph(child, doc).text.strip()
                if text:
                    parts.append(text)
            elif child.tag == qn("w:tbl"):
                parts.extend(self._docx_table_text(Table(child, doc)))

        return parts

    def _docx_table_text(self, table) -> List[str]:
        """Read a table one row at a time, so the columns stay together"""
        rows = []
        for row in table.rows:
            cells = []
            for cell in row.cells:
                cell_text = " ".join(cell.text.split())
                if cell_text and cell_text not in cells:
                    # A merged cell is repeated across the span it covers.
                    cells.append(cell_text)
            if cells:
                rows.append(" | ".join(cells))

        return rows

    def _docx_section_text(self, doc, header: bool) -> List[str]:
        """
        Read the headers or the footers of every section.

        Sections usually repeat the same header, and a document with a
        distinct first-page header carries both, so identical text is only
        kept once.
        """
        parts = []
        for section in doc.sections:
            area = section.header if header else section.footer
            try:
                for paragraph in area.paragraphs:
                    text = paragraph.text.strip()
                    if text and text not in parts:
                        parts.append(text)
                for table in area.tables:
                    for row in self._docx_table_text(table):
                        if row not in parts:
                            parts.append(row)
            except Exception as e:
                # A malformed header should not cost us the document body.
                logger.warning(f"Could not read a DOCX {'header' if header else 'footer'}: {e}")

        return parts

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into pieces no larger than one chunk.

        Lines are split before sentences so that table rows, which rarely end
        in a full stop, do not run together into a single oversized segment.
        """
        segments = []
        for line in text.splitlines():
            for sentence in line.split(". "):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sentence) <= self.chunk_size:
                    segments.append(sentence)
                else:
                    segments.extend(self._split_on_words(sentence))

        return segments

    def _split_on_words(self, sentence: str) -> List[str]:
        """Break a segment longer than a chunk apart at word boundaries"""
        pieces = []
        current = []
        size = 0

        for word in sentence.split():
            # +1 for the space that will rejoin them.
            if size + len(word) + 1 > self.chunk_size and current:
                pieces.append(" ".join(current))
                current, size = [], 0
            current.append(word)
            size += len(word) + 1

        if current:
            pieces.append(" ".join(current))

        return pieces

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Uses sentence-aware splitting to avoid breaking mid-sentence.

        Args:
            text: Full text to chunk

        Returns:
            List of text chunks
        """
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_size = len(sentence)

            # If adding this sentence exceeds chunk size, save current chunk
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunks.append(". ".join(current_chunk) + ".")

                # Keep last sentence for overlap
                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_size = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_size

        # Add remaining chunk
        if current_chunk:
            chunks.append(". ".join(current_chunk) + ".")

        return chunks

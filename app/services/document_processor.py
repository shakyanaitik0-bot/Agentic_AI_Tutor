"""
Document Processing Service for Agentic AI Tutor.

Handles extraction and chunking of text from various document formats:
- PDF files
- Text files (TXT, MD)
- Word documents (DOCX, DOC)

Prepares documents for RAG ingestion.
"""
import logging
import os
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
            logger.warning("PyPDF2 not available. PDF processing disabled. Install: pip install PyPDF2")
            return False

    def _check_docx_support(self) -> bool:
        """Check if DOCX processing is available"""
        try:
            import docx
            return True
        except ImportError:
            logger.warning("python-docx not available. DOCX processing disabled. Install: pip install python-docx")
            return False

    def process_document(
        self,
        file_path: str,
        filename: str,
        student_id: str,
        subject: str = "General"
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
        if file_ext == '.pdf':
            text = self._extract_pdf(file_path)
        elif file_ext in ['.txt', '.md']:
            text = self._extract_text(file_path)
        elif file_ext in ['.docx', '.doc']:
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
            processed_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "student_id": student_id,
                    "filename": filename,
                    "subject": subject,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            })

        logger.info(f"Processed {filename}: extracted {len(text)} chars -> {len(chunks)} chunks")
        return processed_chunks

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        if not self._pdf_available:
            raise RuntimeError("PDF support not available. Install PyPDF2: pip install PyPDF2")

        import PyPDF2

        text = []
        try:
            with open(file_path, 'rb') as file:
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
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            except UnicodeDecodeError:
                # Fallback to latin-1
                with open(file_path, 'r', encoding='latin-1') as file:
                    return file.read()

        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            raise ValueError(f"Could not read text file: {str(e)}")

    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if not self._docx_available:
            raise RuntimeError("DOCX support not available. Install python-docx: pip install python-docx")

        import docx

        try:
            doc = docx.Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs)

        except Exception as e:
            logger.error(f"Error extracting DOCX {file_path}: {e}")
            raise ValueError(f"Could not read DOCX file: {str(e)}")

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Uses sentence-aware splitting to avoid breaking mid-sentence.

        Args:
            text: Full text to chunk

        Returns:
            List of text chunks
        """
        # Simple sentence splitting (can be improved with NLTK)
        sentences = text.replace('\n', ' ').split('. ')
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
                chunks.append('. '.join(current_chunk) + '.')

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
            chunks.append('. '.join(current_chunk) + '.')

        return chunks

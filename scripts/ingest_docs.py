"""
Document Ingestion Pipeline for Agentic AI Tutor.

Ingests learning materials (PDFs, text files) into Pinecone vector database.
Supports metadata tagging for intelligent retrieval.

Usage:
    python scripts/ingest_docs.py --input data/documents --exam-type JEE --topic Physics
"""
import sys
import os
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.rag_service import RAGService, Document

logger = logging.getLogger(__name__)


class DocumentIngester:
    """
    Handles ingestion of educational documents into vector database.

    Features:
    - PDF text extraction
    - Metadata extraction from filenames
    - Batch processing
    - Progress tracking
    """

    def __init__(self, rag_service: Optional[RAGService] = None):
        """Initialize document ingester"""
        self.rag = rag_service or RAGService()
        self.supported_extensions = {'.pdf', '.txt', '.md'}

    def extract_metadata_from_filename(self, filepath: Path) -> Dict[str, Any]:
        """
        Extract metadata from filename pattern.

        Expected patterns:
        - {exam_type}_{subject}_{topic}.pdf (e.g., JEE_Physics_Mechanics.pdf)
        - {subject}_{topic}.pdf (e.g., Physics_Thermodynamics.pdf)
        - {topic}.pdf (e.g., Calculus.pdf)

        Args:
            filepath: Path to document

        Returns:
            Dict: Extracted metadata
        """
        filename = filepath.stem  # filename without extension
        parts = filename.split('_')

        metadata = {
            "filename": filepath.name,
            "source": str(filepath)
        }

        # Parse filename components
        if len(parts) >= 3:
            metadata["exam_type"] = parts[0]
            metadata["subject"] = parts[1]
            metadata["topic"] = '_'.join(parts[2:])
        elif len(parts) == 2:
            metadata["subject"] = parts[0]
            metadata["topic"] = parts[1]
        else:
            metadata["topic"] = filename

        return metadata

    def extract_text_from_pdf(self, filepath: Path) -> str:
        """
        Extract text from PDF file.

        Args:
            filepath: Path to PDF

        Returns:
            str: Extracted text
        """
        try:
            from pypdf import PdfReader

            with open(filepath, 'rb') as file:
                pdf_reader = PdfReader(file)
                text_parts = []

                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(text)

                return '\n\n'.join(text_parts)

        except ImportError:
            logger.error("pypdf not installed. Install with: uv sync")
            raise
        except Exception as e:
            logger.error(f"Failed to extract text from {filepath}: {e}")
            return ""

    def extract_text_from_txt(self, filepath: Path) -> str:
        """
        Extract text from text file.

        Args:
            filepath: Path to text file

        Returns:
            str: File contents
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return ""

    def extract_text(self, filepath: Path) -> str:
        """
        Extract text from document based on file type.

        Args:
            filepath: Path to document

        Returns:
            str: Extracted text
        """
        ext = filepath.suffix.lower()

        if ext == '.pdf':
            return self.extract_text_from_pdf(filepath)
        elif ext in {'.txt', '.md'}:
            return self.extract_text_from_txt(filepath)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return ""

    def ingest_file(
        self,
        filepath: Path,
        metadata_override: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest a single document file.

        Args:
            filepath: Path to document
            metadata_override: Optional metadata to override filename parsing
            namespace: Optional Pinecone namespace

        Returns:
            Dict: Ingestion statistics
        """
        logger.info(f"Processing: {filepath.name}")

        # Extract text
        text = self.extract_text(filepath)
        if not text or len(text.strip()) < 50:
            logger.warning(f"Insufficient content in {filepath.name} (< 50 chars)")
            return {"success": False, "chunks": 0, "reason": "insufficient_content"}

        # Get metadata
        metadata = self.extract_metadata_from_filename(filepath)
        if metadata_override:
            metadata.update(metadata_override)

        # Chunk document
        chunks = self.rag.chunk_text(text, metadata=metadata)

        if not chunks:
            logger.warning(f"No chunks created from {filepath.name}")
            return {"success": False, "chunks": 0, "reason": "no_chunks"}

        # Upload to Pinecone
        upload_stats = self.rag.upload_documents(chunks, namespace=namespace)

        logger.info(
            f"Ingested {filepath.name}: {upload_stats['uploaded']} chunks uploaded"
        )

        return {
            "success": upload_stats['uploaded'] > 0,
            "chunks": upload_stats['uploaded'],
            "failed": upload_stats['failed'],
            "metadata": metadata
        }

    def ingest_directory(
        self,
        directory: Path,
        metadata_override: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest all documents from a directory.

        Args:
            directory: Path to directory
            metadata_override: Optional metadata for all files
            namespace: Optional Pinecone namespace
            recursive: Whether to search subdirectories

        Returns:
            Dict: Ingestion statistics
        """
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return {"success": False, "files_processed": 0}

        # Find all supported files
        files = []
        if recursive:
            for ext in self.supported_extensions:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in self.supported_extensions:
                files.extend(directory.glob(f"*{ext}"))

        if not files:
            logger.warning(f"No supported files found in {directory}")
            return {"success": False, "files_processed": 0}

        logger.info(f"Found {len(files)} files to process")

        # Process each file
        total_chunks = 0
        total_failed = 0
        successful_files = 0

        for filepath in files:
            result = self.ingest_file(filepath, metadata_override, namespace)
            if result["success"]:
                successful_files += 1
                total_chunks += result["chunks"]
            total_failed += result.get("failed", 0)

        logger.info(
            f"Ingestion complete: {successful_files}/{len(files)} files, "
            f"{total_chunks} total chunks"
        )

        return {
            "success": successful_files > 0,
            "files_processed": len(files),
            "successful_files": successful_files,
            "total_chunks": total_chunks,
            "total_failed": total_failed
        }


def main():
    """Main ingestion script"""
    parser = argparse.ArgumentParser(
        description="Ingest educational documents into vector database"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help="Input directory or file path"
    )
    parser.add_argument(
        '--exam-type',
        type=str,
        help="Exam type (JEE, SAT, GRE, etc.)"
    )
    parser.add_argument(
        '--subject',
        type=str,
        help="Subject (Physics, Math, Chemistry, etc.)"
    )
    parser.add_argument(
        '--topic',
        type=str,
        help="Topic name"
    )
    parser.add_argument(
        '--difficulty',
        type=str,
        choices=['easy', 'medium', 'hard'],
        help="Difficulty level"
    )
    parser.add_argument(
        '--namespace',
        type=str,
        default='',
        help="Pinecone namespace (default: empty)"
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help="Don't search subdirectories"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Build metadata override
    metadata_override = {}
    if args.exam_type:
        metadata_override['exam_type'] = args.exam_type
    if args.subject:
        metadata_override['subject'] = args.subject
    if args.topic:
        metadata_override['topic'] = args.topic
    if args.difficulty:
        metadata_override['difficulty'] = args.difficulty

    # Initialize ingester
    print("\n" + "="*70)
    print("Document Ingestion Pipeline")
    print("="*70)

    ingester = DocumentIngester()

    # Process input
    input_path = Path(args.input)

    if input_path.is_file():
        # Single file
        result = ingester.ingest_file(
            input_path,
            metadata_override=metadata_override if metadata_override else None,
            namespace=args.namespace or None
        )

        if result["success"]:
            print(f"\n[SUCCESS] Ingested {result['chunks']} chunks from {input_path.name}")
        else:
            print(f"\n[FAILED] Could not ingest {input_path.name}: {result.get('reason', 'unknown')}")

    elif input_path.is_dir():
        # Directory
        result = ingester.ingest_directory(
            input_path,
            metadata_override=metadata_override if metadata_override else None,
            namespace=args.namespace or None,
            recursive=not args.no_recursive
        )

        if result["success"]:
            print(f"\n[SUCCESS] Processed {result['successful_files']}/{result['files_processed']} files")
            print(f"Total chunks uploaded: {result['total_chunks']}")
        else:
            print(f"\n[FAILED] Could not process directory {input_path}")
    else:
        print(f"\n[ERROR] Invalid input path: {input_path}")
        sys.exit(1)

    # Show index stats
    print("\n" + "="*70)
    print("Pinecone Index Statistics")
    print("="*70)
    stats = ingester.rag.get_stats()
    print(f"Total vectors: {stats.get('total_vectors', 0)}")
    print(f"Dimension: {stats.get('dimension', 0)}")
    print(f"Index fullness: {stats.get('index_fullness', 0):.2%}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

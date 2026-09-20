"""Extraction has to see everything a document puts on the page."""

import pytest

from app.services.document_processor import DocumentProcessor

docx = pytest.importorskip("docx")


QUESTIONS = [
    ("Q1", "Explain Newton's three laws of motion with examples"),
    ("Q2", "Derive the equation of motion v = u + at"),
    ("Q3", "A body moves with uniform acceleration; find the displacement"),
]


@pytest.fixture
def assignment(tmp_path):
    """
    An assignment sheet shaped like the one the student actually uploaded:
    a cover line or two, and every question inside a table.
    """
    document = docx.Document()
    document.add_paragraph("ASSIGNMENT 1")
    document.add_paragraph("Name: Naitik    Roll No: 22BCE1234")

    table = document.add_table(rows=len(QUESTIONS), cols=2)
    for row, (number, question) in zip(table.rows, QUESTIONS):
        row.cells[0].text = number
        row.cells[1].text = question

    section = document.sections[0]
    section.header.paragraphs[0].text = "Department of Physics"
    section.footer.paragraphs[0].text = "Submission deadline: 30 September"

    path = tmp_path / "ASSISMENT 1.docx"
    document.save(str(path))
    return str(path)


def test_table_contents_are_extracted(assignment):
    """The reported bug: only the cover lines were indexed, so the tutor had
    nothing to say about a document it could see the name of."""
    text = DocumentProcessor()._extract_docx(assignment)

    for number, question in QUESTIONS:
        assert question in text, f"{number} was dropped: it lives in a table"


def test_headers_and_footers_are_extracted(assignment):
    text = DocumentProcessor()._extract_docx(assignment)

    assert "Department of Physics" in text
    assert "Submission deadline: 30 September" in text


def test_body_text_still_comes_first(assignment):
    """Table support must not cost us the ordinary paragraphs."""
    text = DocumentProcessor()._extract_docx(assignment)

    assert "ASSIGNMENT 1" in text
    assert "Roll No: 22BCE1234" in text
    assert text.index("ASSIGNMENT 1") < text.index("Explain Newton's")


def test_a_document_that_is_only_a_table_still_processes(tmp_path):
    """Before, this raised 'Could not extract meaningful text'."""
    document = docx.Document()
    table = document.add_table(rows=len(QUESTIONS), cols=2)
    for row, (number, question) in zip(table.rows, QUESTIONS):
        row.cells[0].text = number
        row.cells[1].text = question

    path = tmp_path / "questions.docx"
    document.save(str(path))

    chunks = DocumentProcessor().process_document(
        file_path=str(path), filename="questions.docx", student_id="s1"
    )

    assert chunks
    assert "Derive the equation of motion" in " ".join(c["text"] for c in chunks)


def test_a_merged_cell_is_not_repeated(tmp_path):
    """python-docx returns a merged cell once per column it spans."""
    document = docx.Document()
    table = document.add_table(rows=1, cols=3)
    merged = table.rows[0].cells[0].merge(table.rows[0].cells[2])
    merged.text = "Answer all three questions"

    path = tmp_path / "merged.docx"
    document.save(str(path))

    text = DocumentProcessor()._extract_docx(str(path))

    assert text.count("Answer all three questions") == 1


def test_a_long_table_row_is_split_into_chunk_sized_pieces():
    """A row rarely ends in a full stop, so sentence splitting alone left it
    whole however long it was."""
    processor = DocumentProcessor(chunk_size=100, chunk_overlap=0)
    row = " | ".join(f"cell number {i} of a very wide table" for i in range(40))

    chunks = processor._chunk_text(row)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks), [len(c) for c in chunks]

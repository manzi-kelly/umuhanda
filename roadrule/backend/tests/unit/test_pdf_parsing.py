import pymupdf
import pytest

from app.services.pdf.parsing import NumberedChoiceStrategy, page_lines
from app.services.pdf.probe import inspect_pdf
from app.services.pdf.storage import PdfError, PdfStorage
from tests.pdf_fixtures import bulk_pdf, sample_pdf


def parse(data, settings):
    parser = NumberedChoiceStrategy(
        settings.pdf_question_pattern, settings.pdf_option_pattern, settings.pdf_max_questions
    )
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for page in pdf:
            parser.page = page.number + 1
            parser.feed(
                page_lines(page, settings.pdf_max_page_chars), page.rect.width, page.rect.height
            )
    return parser.finish(), parser.diagnostics


def test_multiline_crosspage_options_and_explicit_evidence(settings):
    questions, diagnostics = parse(sample_pdf(), settings)
    assert not diagnostics and len(questions) == 2
    assert questions[0].text == "Iki ni ikibazo cy'igerageza?\nUyu ni umurongo wa kabiri."
    assert questions[1].options[1].text == "Igisubizo gikomeza\nkuri uyu murongo."
    assert questions[1].options[1].lines[0].page == 2
    assert questions[0].selected_label == "A"
    assert questions[0].answers[0].text == "1. A" and questions[0].answers[0].page == 3
    assert questions[0].status == "EXTRACTED_UNVERIFIED"


def test_missing_answers_are_not_inferred(settings):
    questions, _ = parse(sample_pdf(answers=False), settings)
    assert all(q.status == "ANSWER_NOT_FOUND" and q.selected_label is None for q in questions)


def test_conflicting_answers_are_never_selected(settings):
    questions, _ = parse(sample_pdf(ambiguous=True), settings)
    assert questions[0].status == "NEEDS_REVIEW" and questions[0].selected_label is None
    assert len(questions[0].answers) == 2


def test_four_hundred_is_measured_from_actual_fixture(settings):
    questions, _ = parse(bulk_pdf(), settings)
    assert len(questions) == 400
    assert questions[-1].number == "400"
    assert all(len(q.options) == 2 and q.selected_label is None for q in questions)


def test_unstructured_and_scanned_pages_are_not_questions(settings):
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((40, 60), "Some arbitrary text is not a question")
    pdf.new_page()
    questions, diagnostics = parse(pdf.tobytes(), settings)
    pdf.close()
    assert questions == [] and diagnostics == [{"code": "OCR_REQUIRED_UNAVAILABLE", "page": 2}]


def test_duplicate_question_numbers_block_answer_association(settings):
    pdf = pymupdf.open()
    page = pdf.new_page()
    for i, line in enumerate(
        ["1. First?", "A. One", "B. Two", "1. Again?", "A. One", "B. Two", "Ibisubizo", "1. A"]
    ):
        page.insert_text((40, 40 + i * 22), line)
    questions, _ = parse(pdf.tobytes(), settings)
    pdf.close()
    assert len(questions) == 2
    assert all(q.selected_label is None and q.status == "NEEDS_REVIEW" for q in questions)


@pytest.mark.parametrize(
    "key", ["../secret", "/etc/passwd", "sources/../../x.pdf", "assets/bad.png"]
)
def test_storage_rejects_arbitrary_paths(settings, tmp_path, key):
    storage = PdfStorage(settings.model_copy(update={"pdf_storage_root": tmp_path}))
    with pytest.raises(PdfError):
        storage.path(key)


def test_structural_page_and_encryption_limits(tmp_path):
    path = tmp_path / "fixture.pdf"
    path.write_bytes(sample_pdf())
    assert inspect_pdf(path, 2, 2000)["error"] == "PAGE_LIMIT"
    assert inspect_pdf(path, 10, 100)["error"] == "PAGE_DIMENSION_LIMIT"
    pdf = pymupdf.open(stream=sample_pdf(), filetype="pdf")
    path.write_bytes(
        pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="synthetic-only",
            user_pw="synthetic-only",
        )
    )
    pdf.close()
    assert inspect_pdf(path, 10, 2000)["error"] == "ENCRYPTED_OR_MALFORMED_PDF"


def test_rejected_duplicate_question_number_still_makes_key_ambiguous(settings):
    pdf = pymupdf.open()
    page = pdf.new_page()
    lines = ["1. First?", "A. One", "B. Two", "1. Incomplete?", "A. One", "Ibisubizo", "1. A"]
    for index, line in enumerate(lines):
        page.insert_text((40, 40 + index * 22), line)
    questions, diagnostics = parse(pdf.tobytes(), settings)
    pdf.close()
    assert len(questions) == 1 and diagnostics
    assert questions[0].selected_label is None and questions[0].status == "NEEDS_REVIEW"

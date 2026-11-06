"""Optional local Tesseract data via MuPDF. OCR evidence always requires review."""

from app.services.pdf.parsing import page_lines


def ocr_lines(page, settings):
    directory = settings.pdf_ocr_tessdata
    if directory is None:
        return []
    if any(
        not (directory / f"{language}.traineddata").is_file()
        for language in settings.pdf_ocr_language.split("+")
    ):
        return []
    try:
        textpage = page.get_textpage_ocr(
            language=settings.pdf_ocr_language,
            dpi=144,
            full=True,
            tessdata=str(directory.resolve()),
        )
        return page_lines(page, settings.pdf_max_page_chars, textpage=textpage)
    except Exception:
        return []

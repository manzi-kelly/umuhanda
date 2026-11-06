"""Isolated structural validation and bounded page rendering; never prints PDF contents."""

import json
import sys

import pymupdf


def inspect_pdf(path, max_pages, max_points):
    with open(path, "rb") as stream:
        if stream.read(5) != b"%PDF-":
            return {"error": "INVALID_PDF"}
    with pymupdf.open(path) as pdf:
        if (
            not pdf.is_pdf
            or pdf.is_repaired
            or pdf.needs_pass
            or pdf.is_encrypted
            or pdf.xref_get_key(-1, "Encrypt")[0] != "null"
        ):
            return {"error": "ENCRYPTED_OR_MALFORMED_PDF"}
        if not 0 < len(pdf) <= max_pages:
            return {"error": "PAGE_LIMIT"}
        if pdf.xref_length() > 200000:
            return {"error": "DOCUMENT_COMPLEXITY_LIMIT"}
        if pdf.embfile_count() or pdf.is_form_pdf:
            return {"error": "UNSUPPORTED_ACTIVE_DOCUMENT"}
        if pdf.xref_get_key(-1, "Root")[0] == "null":
            return {"error": "INVALID_PDF"}
        # Reject action-bearing PDFs without ever executing their actions.
        for xref in range(1, pdf.xref_length()):
            if pdf.xref_get_key(xref, "S")[1] in {
                "/Launch",
                "/JavaScript",
                "/SubmitForm",
                "/ImportData",
                "/RichMediaExecute",
            }:
                return {"error": "UNSUPPORTED_ACTIVE_DOCUMENT"}
            for key in ("JS", "JavaScript", "Launch", "AA", "OpenAction"):
                if pdf.xref_get_key(xref, key)[0] != "null":
                    return {"error": "UNSUPPORTED_ACTIVE_DOCUMENT"}
        for page in pdf:
            if page.rect.is_empty or max(page.rect.width, page.rect.height) > max_points:
                return {"error": "PAGE_DIMENSION_LIMIT"}
        return {"pageCount": len(pdf)}


def main():
    try:
        from app.services.pdf.limits import limit_memory

        limit_memory(int(sys.argv[4]))
        pymupdf.TOOLS.mupdf_display_errors(False)
        pymupdf.TOOLS.mupdf_display_warnings(False)
        result = inspect_pdf(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
        if len(sys.argv) == 7 and "error" not in result:
            with pymupdf.open(sys.argv[1]) as pdf:
                page = pdf[int(sys.argv[5]) - 1]
                scale = min(1.5, 1400 / max(page.rect.width, page.rect.height))
                page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(sys.argv[6])
        print(json.dumps(result))
    except Exception:
        print(json.dumps({"error": "INVALID_PDF"}))


if __name__ == "__main__":
    main()
